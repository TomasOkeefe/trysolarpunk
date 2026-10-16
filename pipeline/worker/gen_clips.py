"""GPU worker: render every shot of every plan in a batch with LTX-2.5.

usage: python gen_clips.py batch_dir -- <shared LTX CLI flags>
batch_dir/<slug>/plan.json in, batch_dir/<slug>/clips/shot_NN.mp4 out.
Shared flags are the model paths plus --height/--width/--num-frames/--frame-rate/--quantization
(and --detailing-lora in dfr mode).

Two modes (RENDER_MODE):
- "distilled": DistilledPipeline, the fastest.
- "dfr": LTX's production path (DFRPipeline): half-res base with generated keyframes, then a full-res
  re-render with the detailing IC-LoRA. Fewer artifacts, about twice the GPU time. The two passes use
  differently fused transformers, so every shot does pass 1 first (state saved to shot_NN.s1.pt),
  then the detailing transformer is built once for every pass 2. A "sing" shot is rendered against
  the song's isolated vocals (audio frozen in pass 1), so the character lip-syncs the line. Real
  vocals pull LTX toward live-action singers (Moss turned into a man in a hoodie), so a sing shot
  first renders its scene without the vocals and uses that first frame as the anchor frame.

With batch_dir/<slug>/timeline.json (ge.timeline) every clip is rendered at the length its cut needs.

Why it is fast: LTX normally rebuilds Gemma and the 22B transformer from disk for every clip
(and with --offload cpu streams the transformer layer by layer). Here Gemma runs once for all
prompts and is freed, then the transformer is built once and stays on the GPU for every clip.
Written against LTX-2 commit be6d6d0 (pinned in job.sh); it uses a few private hooks.
"""
import contextlib
import gc
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
if torch.cuda.is_available() and torch.cuda.get_device_properties(0).total_memory < 40 * 2**30:
    ENCODE_BATCH = 1  # 32 GB cards: bf16 Gemma leaves room for one prompt's hidden states at a time
PROBE_SHOTS = int(os.environ.get("PROBE_SHOTS", 0))  # GPU probe: render only the first N shots
CLIPS = os.environ.get("CLIPS_SUBDIR", "clips")
MODE = os.environ.get("RENDER_MODE", "distilled")

videos = [(d, json.loads((d / "plan.json").read_text())) for d in sorted(batch.iterdir()) if (d / "plan.json").exists()]


def timeline(d):
    p = d / "timeline.json"
    return json.loads(p.read_text()) if p.exists() else None


def prompt_of(plan, shot):
    """The plan's style leads every prompt except the product shot, which starts from a real photo."""
    style = "" if shot.get("product_image") else (plan.get("style") or "").strip()
    return f"{style} {shot['prompt']}".strip()


def shot_args(d, plan, i, shot):
    seed = zlib.crc32(plan["slug"].encode()) % 100000 + i
    a = ["--prompt", prompt_of(plan, shot), "--seed", str(seed), "--output-path", str(d / CLIPS / f"shot_{i:02d}.mp4")]
    tl = timeline(d)
    if tl and i < len(tl["shots"]):  # the cut decides the length
        a += ["--num-frames", str(tl["shots"][i]["frames"])]
    if shot.get("product_image") and plan.get("image"):  # run.py sets the product's render as first frame
        a += ["--image", str(GE / plan["image"]), "0", "0.85"]
    return a


def sing_audio(d, i):
    """(audio file, start second) for a singing shot: the stretch of vocals its cut plays over."""
    tl = timeline(d)
    if not tl or i >= len(tl["shots"]) or not tl["shots"][i].get("sing"):
        return None
    src = d / "vocals.wav" if (d / "vocals.wav").exists() else d / "song.flac"
    return str(src), tl["offset"] + tl["shots"][i]["start"]


@torch.inference_mode()
def main():
    from ltx_pipelines import distilled as D
    from ltx_pipelines.utils.gpu_model import gpu_model

    assert torch.cuda.is_available(), "no usable GPU (driver too old for this torch?)"
    d0, p0 = videos[0]
    # LTX picks its model-version defaults by pre-parsing sys.argv, so give it the real flags
    sys.argv = [sys.argv[0], *base, *shot_args(d0, p0, 0, p0["shots"][0])]
    params = D.resolve_cli_params(distilled=True)
    if MODE == "dfr":
        from ltx_pipelines import dfr_pipeline as F
        parser = F.add_dfr_cli_args(D.default_2_stage_distilled_arg_parser(params=params, supports_auto_duration=True))
        first = parser.parse_args(sys.argv[1:])
        pipe = F.DFRPipeline(
            model_paths=first.model_paths,
            spatial_upsampler_path=first.spatial_upsampler_path,
            loras=tuple(first.lora) if first.lora else (),
            detailing_lora=first.detailing_lora,
            quantization=first.quantization,
            compilation_config=first.compile,
            offload_mode=first.offload_mode,
            diffvae_optimization=first.diffvae_optimization,
        )
    else:
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

    def encoded(prompt):
        return cache[prompt]._replace(**{f: (v.to(pipe.device) if v is not None else None)
                                         for f, v in cache[prompt]._asdict().items()})
    pipe.prompt_encoder = lambda batch_prompts, **_: [encoded(p) for p in batch_prompts]

    # 2. build the transformer once and keep it resident (the stage would otherwise rebuild it per pass).
    # With --offload (small cards) LTX streams it from CPU RAM layer by layer instead.
    def make_resident(stage):
        if first.offload_mode != D.OffloadMode.NONE:
            print(f"offload {first.offload_mode.value}: transformer streams from CPU", flush=True)
            return None
        t = time.time()
        model = stage._build_transformer()
        stage._transformer_ctx = lambda **_: contextlib.nullcontext(model)
        print(f"transformer resident in {time.time() - t:.0f}s, "
              f"{torch.cuda.memory_allocated() / 2**30:.1f} GB allocated", flush=True)
        return model

    shots_of = lambda p: p["shots"][:PROBE_SHOTS] if PROBE_SHOTS else p["shots"]
    passes = 2 if MODE == "dfr" else 1
    total, finished = passes * sum(len(shots_of(p)) for _, p in videos), 0

    def progress():  # the orchestrator treats an unchanged STAGE as a stall, so report every clip
        if os.environ.get("STAGE_FILE"):
            pathlib.Path(os.environ["STAGE_FILE"]).write_text(f"clips: render {finished}/{total}\n")

    def each_shot(fn, label):
        """Run fn(d, plan, i, shot, args) over every shot; one broken video must not sink the rest."""
        nonlocal finished
        progress()
        for d, plan in videos:
            (d / CLIPS).mkdir(exist_ok=True)
            try:
                for i, shot in enumerate(shots_of(plan)):
                    t = time.time()
                    if fn(d, plan, i, shot, parser.parse_args(base + shot_args(d, plan, i, shot))):
                        print(f"{plan['slug']} shot {i} {label} done in {time.time() - t:.0f}s, "
                              f"peak {torch.cuda.max_memory_allocated() / 2**30:.1f} GB", flush=True)
                    finished += 1
                    progress()
            except Exception as e:  # noqa: BLE001
                print(f"{plan['slug']} FAILED: {type(e).__name__}: {e}", flush=True)
                torch.cuda.empty_cache()

    if MODE != "dfr":
        make_resident(pipe.stage)

        def render(d, plan, i, shot, args):
            dst = pathlib.Path(args.output_path)
            if dst.exists():
                return False
            chunks, num_frames, tiling = pipe.stream_chunks(
                prompt=args.prompt, seed=args.seed, height=args.height, width=args.width,
                num_frames=args.num_frames, frame_rate=args.frame_rate, images=args.images,
                vae_dtype=torch.bfloat16, color_space=None, enhance_prompt=False, enhance_static_cache=False,
                tiling_config=D.AUTO_TILING, generated_keyframes=0, decode_with_keyframes=False, chunk_config=None)
            res = D.pipeline_output_from_chunks(chunks, num_frames=num_frames, tiling_config=tiling)
            D.encode_video(video=res.video, fps=args.frame_rate, audio=res.audio, output_path=str(dst),
                           video_chunks_number=D.get_video_chunks_number(res.num_frames, res.tiling_config),
                           color_space=None, audio_sampling_rate=None)
            return True
        each_shot(render, "")
        return

    # ---- dfr: pass 1 (base transformer) for every shot, then pass 2 (detailing transformer) ----
    from ltx_core.components.noisers import GaussianNoiser
    from ltx_core.model.audio_vae import encode_audio
    from ltx_core.model.video_vae import AUTO_TILING, get_video_chunks_number
    from ltx_core.types import VIDEO_SCALE_FACTORS, Audio, AudioLatentShape, VideoPixelShape
    from ltx_pipelines.dfr_helpers.layout import resolve_canvas
    from ltx_pipelines.dfr_helpers.ops import trim_video_to_requested_frames
    from ltx_pipelines.dfr_stages import denoise_stage1, denoise_stage2
    from ltx_pipelines.utils.blocks import AudioConditioner
    from ltx_pipelines.utils.constants import DISTILLED_SIGMAS, STAGE_2_DISTILLED_SIGMAS
    from ltx_pipelines.utils.helpers import decode_keyframes_from_slots, ensure_tiling_config, tiling_scale_factors_for_vae
    from ltx_pipelines.utils.media_io import decode_audio_from_file, encode_video
    from ltx_pipelines.utils.types import ImageConditioningInput, ModalitySpec
    from PIL import Image

    audio_conditioner = AudioConditioner(first.model_paths.audio_vae(), torch.bfloat16, pipe.device)
    s1_of = lambda args: pathlib.Path(args.output_path).with_suffix(".s1.pt")

    def vocal_latent(path, start, seconds):
        """The song's vocals from `start` as a frozen audio latent `seconds` long (silence-padded)."""
        audio = decode_audio_from_file(path, pipe.device, start, seconds)
        need = round(seconds * audio.sampling_rate) + audio.sampling_rate // 10
        wav = audio.waveform
        if wav.shape[-1] < need:
            wav = torch.nn.functional.pad(wav, (0, need - wav.shape[-1]))
        lat = audio_conditioner(lambda e: encode_audio(Audio(waveform=wav, sampling_rate=audio.sampling_rate), e, None))
        frames = AudioLatentShape.from_duration(batch=1, duration=seconds).frames
        return lat[:, :, :frames].to(torch.bfloat16)

    def decode(latent, keyframes, nf, requested, height, width, fps, gen):
        latent, n = trim_video_to_requested_frames(latent, canvas_frames=nf, requested_frames=requested,
                                                   temporal_upscalings=0, temporal_scale=VIDEO_SCALE_FACTORS.time)
        kf = decode_keyframes_from_slots(torch.cat(list(keyframes.values()), dim=2), list(keyframes), n)
        vae = pipe.video_decoder
        tiling = ensure_tiling_config(
            AUTO_TILING, scale_factors=tiling_scale_factors_for_vae(vae.checkpoint_path), vae_checkpoint_path=vae.checkpoint_path,
            video_shape=VideoPixelShape(batch=1, frames=n, height=height, width=width, fps=fps),
            diffvae_optimization=vae.diffvae_optimization, device=pipe.device, keyframes=kf is not None)
        return vae(latent, tiling, gen, keyframes=kf), n, tiling

    def stage1(args, ctx, images, audio_spec, gen, nf, positions):
        return denoise_stage1(
            stage=pipe.stage, image_conditioner=pipe.image_conditioner, images=images,
            video_shape=VideoPixelShape(batch=1, frames=nf, height=args.height // 2, width=args.width // 2, fps=args.frame_rate),
            positions=positions, video_context=ctx.video_encoding, audio_context=ctx.audio_encoding,
            sigmas=DISTILLED_SIGMAS, noiser=GaussianNoiser(generator=gen), device=pipe.device, dtype=torch.bfloat16,
            audio_spec=audio_spec, **pipe._sampler_kwargs(args.seed, D.ANCESTRAL_NOISE_SEED_OFFSET))

    def pass1(d, plan, i, shot, args):
        if pathlib.Path(args.output_path).exists() or s1_of(args).exists():
            return False
        ctx = encoded(args.prompt)
        nf, _, positions = resolve_canvas(args.num_frames)
        images = pipe.image_conditioner.resolve_crf(args.images)
        audio_spec, anchored = None, False
        sing = sing_audio(d, i)
        if sing:
            if not images:  # the scene without vocals first: its first frame keeps the look
                g = torch.Generator(device=pipe.device).manual_seed(args.seed)
                plain = stage1(args, ctx, images, None, g, nf, positions)
                video, _, _ = decode(plain.video_state.latent[:1], plain.keyframes, nf, args.num_frames,
                                     args.height // 2, args.width // 2, args.frame_rate, g)
                frame = list(video)[0][0].float()  # drain the iterator so the decoder is freed
                frame = frame.clamp(0, 1).mul(255).byte().cpu().numpy()
                anchor = pathlib.Path(args.output_path).with_suffix(".anchor.png")
                Image.fromarray(frame).save(anchor)
                images = pipe.image_conditioner.resolve_crf([ImageConditioningInput(str(anchor), 0, 1.0)])
                anchored = True
            audio_spec = ModalitySpec(latent=vocal_latent(*sing, nf / args.frame_rate), conditioning_fps=args.frame_rate,
                                      context=ctx.audio_encoding, frozen=True, noise_scale=0.0)
        gen = torch.Generator(device=pipe.device).manual_seed(args.seed)
        s1 = stage1(args, ctx, images, audio_spec, gen, nf, positions)
        torch.save({"ref": s1.video_state.latent[:1].cpu(), "kf": {k: v.cpu() for k, v in s1.keyframes.items()},
                    "audio": s1.audio_state.latent.cpu(), "frames": nf, "requested": args.num_frames,
                    "anchored": anchored, "gen": gen.get_state()}, s1_of(args))
        return True

    def pass2(d, plan, i, shot, args):
        dst, s1p = pathlib.Path(args.output_path), s1_of(args)
        if dst.exists() or not s1p.exists():
            return False
        st = torch.load(s1p)
        ctx = encoded(args.prompt)
        gen = torch.Generator(device=pipe.device)
        gen.set_state(st["gen"])
        nf = st["frames"]
        s2 = denoise_stage2(
            stage=pipe.stage_detailing, image_conditioner=pipe.image_conditioner, upsampler=pipe.upsampler,
            # an anchor frame is half-res: pass 2 takes the look from the pass-1 reference instead
            images=[] if st.get("anchored") else pipe.image_conditioner.resolve_crf(args.images),
            video_shape=VideoPixelShape(batch=1, frames=nf, height=args.height, width=args.width, fps=args.frame_rate),
            keyframes={k: v.to(pipe.device) for k, v in st["kf"].items()},
            half_res_reference=st["ref"].to(pipe.device), downscale_factor=pipe._detailing_downscale,
            audio_latent=st["audio"].to(pipe.device), video_context=ctx.video_encoding, audio_context=ctx.audio_encoding,
            sigmas=STAGE_2_DISTILLED_SIGMAS, noiser=GaussianNoiser(generator=gen), device=pipe.device,
            dtype=torch.bfloat16, **pipe._sampler_kwargs(args.seed, D.ANCESTRAL_STAGE_2_NOISE_SEED_OFFSET))
        video, n, tiling = decode(s2.video_state.latent, s2.keyframes, nf, st["requested"],
                                  args.height, args.width, args.frame_rate, gen)
        # no audio track: the edit lays the song over every clip
        encode_video(video=video, fps=int(args.frame_rate), audio=None, output_path=str(dst),
                     video_chunks_number=get_video_chunks_number(n, tiling))
        s1p.unlink()
        return True

    base_model = make_resident(pipe.stage)
    each_shot(pass1, "pass 1")
    del base_model
    pipe.stage.__dict__.pop("_transformer_ctx", None)  # drops the last reference to the base transformer
    gc.collect()
    torch.cuda.empty_cache()
    make_resident(pipe.stage_detailing)
    each_shot(pass2, "pass 2")


main()
