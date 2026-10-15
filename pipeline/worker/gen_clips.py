"""GPU worker: render every shot of every plan in a batch with LTX-2.5 DistilledPipeline.

usage: python gen_clips.py batch_dir -- <shared LTX CLI flags>
batch_dir/<slug>/plan.json in, batch_dir/<slug>/clips/shot_NN.mp4 out.
Shared flags are the model paths plus --height/--width/--num-frames/--frame-rate/--quantization.

Why it is fast: LTX normally rebuilds Gemma and the 22B transformer from disk for every clip
(and with --offload cpu streams the transformer layer by layer). Here Gemma runs once for all
prompts and is freed, then the transformer is built once and stays on the GPU for every clip.
Written against LTX-2 commit be6d6d0 (pinned in job.sh); it uses a few private hooks.
"""
import contextlib
import json
import os
import pathlib
import sys
import time
import zlib

import torch

batch = pathlib.Path(sys.argv[1])
base = sys.argv[sys.argv.index("--") + 1:]
GE = pathlib.Path(__file__).resolve().parents[1]
ENCODE_BATCH = 4  # Gemma keeps every hidden layer (~385 MB per prompt), so encode a few at a time

videos = [(d, json.loads((d / "plan.json").read_text())) for d in sorted(batch.iterdir()) if (d / "plan.json").exists()]


def prompt_of(plan, shot):
    """The plan's style leads every prompt except the product shot, which starts from a real photo."""
    style = "" if shot.get("product_image") else (plan.get("style") or "").strip()
    return f"{style} {shot['prompt']}".strip()


def shot_args(d, plan, i, shot):
    seed = zlib.crc32(plan["slug"].encode()) % 100000 + i
    a = ["--prompt", prompt_of(plan, shot), "--seed", str(seed), "--output-path", str(d / "clips" / f"shot_{i:02d}.mp4")]
    if shot.get("product_image") and plan.get("image"):  # run.py sets the product's render as first frame
        a += ["--image", str(GE / plan["image"]), "0", "0.85"]
    return a


@torch.inference_mode()
def main():
    from ltx_pipelines import distilled as D
    from ltx_pipelines.utils.gpu_model import gpu_model

    assert torch.cuda.is_available(), "no usable GPU (driver too old for this torch?)"
    d0, p0 = videos[0]
    # LTX picks its model-version defaults by pre-parsing sys.argv, so give it the real flags
    sys.argv = [sys.argv[0], *base, *shot_args(d0, p0, 0, p0["shots"][0])]
    params = D.resolve_cli_params(distilled=True)
    parser = D.add_chunk_layout_args(D.add_keyframe_decode_arg(D.add_generated_keyframes_arg(
        D.default_2_stage_distilled_arg_parser(params=params, supports_auto_duration=True))))
    first = parser.parse_args(sys.argv[1:])
    pipe = D.DistilledPipeline(
        model_paths=first.model_paths,
        spatial_upsampler_path=first.spatial_upsampler_path,
        loras=tuple(first.lora) if first.lora else (),
        quantization=first.quantization,
        compilation_config=first.compile,
        offload_mode=first.offload_mode,
        prompt_enhancer_gemma_root=first.prompt_enhancer_gemma_root,
        diffvae_optimization=first.diffvae_optimization,
    )

    # 1. every prompt through Gemma once; keep the small embeddings on the CPU
    t = time.time()
    prompts = list(dict.fromkeys(prompt_of(p, s) for _, p in videos for s in p["shots"]))
    enc, cache = pipe.prompt_encoder, {}
    with enc._text_encoder_ctx() as te, gpu_model(enc._build_embeddings_processor()) as ep:
        for k in range(0, len(prompts), ENCODE_BATCH):
            chunk = prompts[k:k + ENCODE_BATCH]
            for prompt, (hs, mask) in zip(chunk, te.encode(chunk)):
                out = ep.process_hidden_states(hs, mask)
                cache[prompt] = out._replace(**{f: (v.cpu() if v is not None else None) for f, v in out._asdict().items()})
    print(f"encoded {len(prompts)} prompts in {time.time() - t:.0f}s; Gemma freed", flush=True)

    def cached_encoder(batch_prompts, **_):
        return [cache[p]._replace(**{f: (v.to(pipe.device) if v is not None else None)
                                     for f, v in cache[p]._asdict().items()}) for p in batch_prompts]
    pipe.prompt_encoder = cached_encoder

    # 2. build the transformer once and keep it resident (the stage would otherwise rebuild it per pass)
    t = time.time()
    resident = pipe.stage._build_transformer()
    pipe.stage._transformer_ctx = lambda **_: contextlib.nullcontext(resident)
    print(f"transformer resident in {time.time() - t:.0f}s, "
          f"{torch.cuda.memory_allocated() / 2**30:.1f} GB allocated", flush=True)

    # 3. render; one broken video must not sink the rest of the batch
    total, finished = sum(len(p["shots"]) for _, p in videos), 0

    def progress():  # the orchestrator treats an unchanged STAGE as a stall, so report every clip
        if os.environ.get("STAGE_FILE"):
            pathlib.Path(os.environ["STAGE_FILE"]).write_text(f"clips: render {finished}/{total}\n")

    progress()
    for d, plan in videos:
        (d / "clips").mkdir(exist_ok=True)
        try:
            for i, shot in enumerate(plan["shots"]):
                dst = d / "clips" / f"shot_{i:02d}.mp4"
                if dst.exists():
                    continue
                t = time.time()
                args = parser.parse_args(base + shot_args(d, plan, i, shot))
                chunks, num_frames, tiling = pipe.stream_chunks(
                    prompt=args.prompt, seed=args.seed, height=args.height, width=args.width,
                    num_frames=args.num_frames, frame_rate=args.frame_rate, images=args.images,
                    vae_dtype=torch.bfloat16, color_space=None, enhance_prompt=False, enhance_static_cache=False,
                    tiling_config=D.AUTO_TILING, generated_keyframes=0, decode_with_keyframes=False, chunk_config=None)
                res = D.pipeline_output_from_chunks(chunks, num_frames=num_frames, tiling_config=tiling)
                D.encode_video(video=res.video, fps=args.frame_rate, audio=res.audio, output_path=str(dst),
                               video_chunks_number=D.get_video_chunks_number(res.num_frames, res.tiling_config),
                               color_space=None, audio_sampling_rate=None)
                print(f"{plan['slug']} shot {i} done in {time.time() - t:.0f}s", flush=True)
                finished += 1
                progress()
        except Exception as e:  # noqa: BLE001
            print(f"{plan['slug']} FAILED: {type(e).__name__}: {e}", flush=True)
            torch.cuda.empty_cache()


main()
