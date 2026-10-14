"""GPU worker: render every shot in the plan with LTX-2.5 DistilledPipeline, loading the models once.

usage: python gen_clips.py plan.json out_dir product_image.jpg -- <shared LTX CLI flags>
Shared flags are the model paths plus --height/--width/--num-frames/--frame-rate/--quantization.
Falls back to one CLI call per shot if the Python API changes underneath us.
"""
import json
import pathlib
import subprocess
import sys

import torch

plan = json.loads(pathlib.Path(sys.argv[1]).read_text())
out = pathlib.Path(sys.argv[2])
product_image = sys.argv[3]
base = sys.argv[sys.argv.index("--") + 1:]
out.mkdir(parents=True, exist_ok=True)


def shot_args(i, shot):
    a = ["--prompt", shot["prompt"], "--seed", str(4200 + i), "--output-path", str(out / f"shot_{i:02d}.mp4")]
    if shot.get("product_image"):
        a += ["--image", product_image, "0", "0.85"]
    return a


@torch.inference_mode()
def python_api():
    from ltx_pipelines import distilled as D

    # LTX picks its model-version defaults by pre-parsing sys.argv, so give it the real flags
    sys.argv = [sys.argv[0], *base, *shot_args(0, plan["shots"][0])]
    params = D.resolve_cli_params(distilled=True)
    parser = D.add_chunk_layout_args(D.add_keyframe_decode_arg(D.add_generated_keyframes_arg(
        D.default_2_stage_distilled_arg_parser(params=params, supports_auto_duration=True))))
    first = parser.parse_args(base + shot_args(0, plan["shots"][0]))
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
    for i, shot in enumerate(plan["shots"]):
        dst = out / f"shot_{i:02d}.mp4"
        if dst.exists():
            continue
        args = parser.parse_args(base + shot_args(i, shot))
        chunks, num_frames, tiling = pipe.stream_chunks(
            prompt=args.prompt, seed=args.seed, height=args.height, width=args.width,
            num_frames=args.num_frames, frame_rate=args.frame_rate, images=args.images,
            vae_dtype=torch.bfloat16, color_space=None, enhance_prompt=False, enhance_static_cache=False,
            tiling_config=D.AUTO_TILING, generated_keyframes=0, decode_with_keyframes=False, chunk_config=None)
        res = D.pipeline_output_from_chunks(chunks, num_frames=num_frames, tiling_config=tiling)
        D.encode_video(video=res.video, fps=args.frame_rate, audio=res.audio, output_path=str(dst),
                       video_chunks_number=D.get_video_chunks_number(res.num_frames, res.tiling_config),
                       color_space=None, audio_sampling_rate=None)
        print(f"shot {i} done -> {dst}", flush=True)


def cli_fallback():
    for i, shot in enumerate(plan["shots"]):
        dst = out / f"shot_{i:02d}.mp4"
        if dst.exists():
            continue
        subprocess.run([sys.executable, "-m", "ltx_pipelines.distilled", *base, *shot_args(i, shot)], check=True)
        print(f"shot {i} done (cli) -> {dst}", flush=True)


try:
    python_api()
except Exception as e:  # noqa: BLE001
    print(f"python API failed ({type(e).__name__}: {e}); falling back to CLI per shot", flush=True)
    cli_fallback()
