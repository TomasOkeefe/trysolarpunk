"""Render a batch on Modal instead of RunPod. Same worker (worker/job.sh), different host.

Why Modal: a pooled multi-cloud GPU supply (rarely "no capacity"), $30/month of free credits on the
Starter plan, and the job keeps running in the cloud when this Mac sleeps. The installs are baked
into the image once; model weights live on the `ge-models` volume, so a run skips ~10 min of setup.
Each run works in `ge-work:/runs/<run_id>/`, so a preempted run resumes where it stopped.

Driven by run.py (`--provider modal`, or automatically when no cheap RunPod card is free).
One-time setup (owner): `python3 -m modal token new`, and a Modal secret named `huggingface`
holding HF_TOKEN (the LTX-2.5 weights are gated).
"""
import os
import pathlib
import subprocess
import time

import modal

APP = "trysolarpunk"
LTX_COMMIT = "be6d6d0"  # keep in step with worker/job.sh
GPUS = ["L40S", "A100-80GB"]  # 48 GB+ so LTX runs without offload; L40S is the cheapest that fits
PIPELINE = pathlib.Path(__file__).resolve().parent

app = modal.App(APP)
# model caches point into the volume, set at run time: as image env they made the build write into
# /models, and Modal won't mount a volume on a non-empty path
CACHES = {"MODELS_DIR": "/models", "HF_HOME": "/models/hf", "XDG_CACHE_HOME": "/models/cache",
          "TORCH_HOME": "/models/torch"}
models = modal.Volume.from_name("ge-models", create_if_missing=True)
work = modal.Volume.from_name("ge-work", create_if_missing=True)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git", "curl", "ffmpeg", "build-essential")
    .pip_install("uv", "pyyaml")
    .run_commands(
        f"git clone -q https://github.com/Lightricks/LTX-2.git /opt/ltx && git -C /opt/ltx checkout -q {LTX_COMMIT}",
        "cd /opt/ltx && (uv sync -q --no-dev --extra natten || uv sync -q --no-dev)",
        "cd /opt/ltx && uv pip install -q 'huggingface_hub[cli,hf_transfer]'",
        "git clone -q --depth 1 https://github.com/multimodal-art-projection/YuE.git /opt/yue",
        "uv venv -q -p 3.12 /opt/yue/.venv && VIRTUAL_ENV=/opt/yue/.venv uv pip install -q /opt/yue",
        "uv venv -q -p 3.12 /opt/asm && VIRTUAL_ENV=/opt/asm uv pip install -q pillow librosa soundfile pyyaml stable-ts demucs",
    )
    .env({"PREBUILT": "1", "LTX_DIR": "/opt/ltx", "YUE_DIR": "/opt/yue", "ASM_DIR": "/opt/asm",
          "HF_HUB_ENABLE_HF_TRANSFER": "0"})
    .add_local_dir(PIPELINE, "/root/pipeline", ignore=["plans/**", "__pycache__/**", "*.pyc", "*.log"])
)


def _job(run_id: str, plans_b64: str, extra_env: dict | None = None) -> list[str]:
    """Run worker/job.sh for one batch. Returns the slugs that finished."""
    run = pathlib.Path("/work/runs") / run_id
    run.mkdir(parents=True, exist_ok=True)
    # the mounted code is read-only; job.sh writes fonts into it, so work on a copy
    subprocess.run(["cp", "-r", "/root/pipeline", "/tmp/pipeline"], check=True)
    env = {**os.environ, **CACHES, "WORK_DIR": str(run), "GE_DIR": "/tmp/pipeline", "OUT_TOKEN": "out",
           "PLANS_B64": plans_b64, "KEEP_MIN": "0", "UV_CACHE_DIR": "/tmp/uv-cache", **(extra_env or {})}
    # job.sh waits on its status server at the end; on Modal nothing needs to fetch from it, so stop it
    proc = subprocess.Popen(["bash", "/tmp/pipeline/worker/job.sh"], env=env)
    out = run / "out" / "out"
    while proc.poll() is None:
        try:
            stage = (out / "STAGE").read_text().strip()
        except OSError:
            stage = ""
        if stage == "DONE" or stage.startswith("FAILED"):
            proc.terminate()
            break
        work.commit()  # make progress (STAGE, finished clips) visible to the watcher and to a retry
        time.sleep(30)
    work.commit()
    done = out / "done.txt"
    return done.read_text().split() if done.exists() else []


@app.function(image=image, gpu=GPUS, timeout=4 * 3600, volumes={"/models": models, "/work": work},
              secrets=[modal.Secret.from_name("huggingface")], retries=modal.Retries(max_retries=2))
def render(run_id: str, plans_b64: str, extra_env: dict | None = None) -> list[str]:
    return _job(run_id, plans_b64, extra_env)


# LoRA training (train_lora.py --provider modal): 80 GB cards train in bf16; no retries, a restart would
# begin the training again and bill it twice
@app.function(image=image, gpu=["H100", "A100-80GB"], timeout=3 * 3600, volumes={"/models": models, "/work": work},
              secrets=[modal.Secret.from_name("huggingface")])
def train(run_id: str, plans_b64: str, extra_env: dict | None = None) -> list[str]:
    return _job(run_id, plans_b64, extra_env)


# the same on the cheap card (int8, slow): for a few-step smoke test of the training path
@app.function(image=image, gpu="L40S", timeout=3600, volumes={"/models": models, "/work": work},
              secrets=[modal.Secret.from_name("huggingface")])
def train_small(run_id: str, plans_b64: str, extra_env: dict | None = None) -> list[str]:
    return _job(run_id, plans_b64, extra_env)


@app.function(image=modal.Image.debian_slim(python_version="3.12"), gpu="T4", timeout=600,
              volumes={"/models": models})
def gpu_check() -> str:
    """Cheap smoke test: driver version and whether LTX's CUDA 13 torch sees the GPU."""
    return subprocess.run(["nvidia-smi", "--query-gpu=name,driver_version", "--format=csv,noheader"],
                          capture_output=True, text=True).stdout


@app.function(image=image, gpu="T4", timeout=900)
def ltx_check() -> str:
    """Smoke test on the real image: LTX's torch must see the GPU (it silently uses the CPU otherwise)."""
    r = subprocess.run(["bash", "-c", "cd /opt/ltx && uv run --no-sync python -c "
                        "'import torch; print(torch.__version__, torch.cuda.is_available(), torch.cuda.get_device_name(0))'; "
                        "nvidia-smi --query-gpu=driver_version --format=csv,noheader"],
                       capture_output=True, text=True)
    return r.stdout + r.stderr[-2000:]


LTX_FILES = ["diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors",
             "text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors",
             "vae/ltx-2.5-video-vae-conv-bf16.safetensors", "vae/ltx-2.5-audio-vae-bf16.safetensors",
             "latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors",
             "vae/ltx-2.5-video-vae-bf16.safetensors"]  # as in job.sh; the DiffVAE one is for DFR's keyframe decode
DETAIL_REPO, DETAIL_FILE = "Lightricks/LTX-2.5-22b-IC-LoRA-Pixel-Spatial-Upscaler", "ltx-2.5-22b-ic-lora-pixel-spatial-upscaler-x2-1.0.safetensors"


@app.function(image=image, cpu=4, memory=16384, timeout=3 * 3600, volumes={"/models": models},
              secrets=[modal.Secret.from_name("huggingface")])
def fetch_models() -> str:
    """Put every model on the ge-models volume with a cheap CPU container, so GPU time isn't spent
    downloading: LTX-2.5 (~70 GB, gated), YuE2 songs, whisper medium + demucs for the captions."""
    steps = [
        "cd /opt/ltx && HF_HUB_ENABLE_HF_TRANSFER=1 uv run --no-sync hf download Lightricks/LTX-2.5 "
        + " ".join(LTX_FILES) + " --local-dir /models/ltx-2.5",
        f"cd /opt/ltx && uv run --no-sync hf download {DETAIL_REPO} {DETAIL_FILE} --local-dir /models/ltx-2.5/loras",
        "/opt/yue/.venv/bin/python -c \"from huggingface_hub import snapshot_download as s; "
        "[s(r) for r in ('m-a-p/YuE2-3B', 'm-a-p/YuE2-Vae')]\"",
        "/opt/asm/bin/python -c \"import stable_whisper; stable_whisper.load_model('medium', device='cpu'); "
        "from demucs.pretrained import get_model; get_model('htdemucs')\"",
    ]
    report = []
    for cmd in steps:
        t = time.time()
        r = subprocess.run(["bash", "-c", cmd], capture_output=True, text=True, env={**os.environ, **CACHES})
        report.append(f"exit {r.returncode} in {time.time() - t:.0f}s: {cmd[:60]}... {r.stderr[-300:] if r.returncode else ''}")
        models.commit()
    du = subprocess.run(["du", "-sh", "/models"], capture_output=True, text=True).stdout
    return "\n".join(report) + "\n" + du


# ---- first frames: an image-editing model draws a character from its master pictures into a shot's
# scene and pose, and LTX animates from that frame (worker/gen_clips.py: a shot's "image"). A LoRA alone
# never held Moss exactly; a clip that starts from a picture of him does (2026-11-11 tests).
EDIT_MODEL = "Qwen/Qwen-Image-Edit-2511"  # Apache 2.0; 1 to 3 reference images
EDIT_FAST = ("lightx2v/Qwen-Image-Edit-2511-Lightning", "Qwen-Image-Edit-2511-Lightning-8steps-V1.0-bf16.safetensors")
edit_image = (
    modal.Image.debian_slim(python_version="3.12")
    .apt_install("git")
    .pip_install("torch", "torchvision", "transformers", "accelerate", "peft", "safetensors", "pillow", "sentencepiece",
                 "huggingface_hub[hf_transfer]", "git+https://github.com/huggingface/diffusers")
    .env({"HF_HOME": "/models/hf", "HF_HUB_ENABLE_HF_TRANSFER": "1"})
    .add_local_dir(PIPELINE / "assets", "/root/assets")
)


@app.function(image=edit_image, cpu=4, memory=8192, timeout=2 * 3600, volumes={"/models": models})
def fetch_edit_model() -> str:
    """Download the editing model to the ge-models volume on a CPU container, and report the pipeline's
    call signature (a free check that this diffusers build has the arguments first_frames uses)."""
    import inspect

    from diffusers import QwenImageEditPlusPipeline
    from huggingface_hub import hf_hub_download, snapshot_download
    t = time.time()
    snapshot_download(EDIT_MODEL)
    hf_hub_download(*EDIT_FAST)
    models.commit()
    du = subprocess.run(["du", "-sh", "/models/hf/hub"], capture_output=True, text=True).stdout.strip()
    return f"downloaded in {time.time() - t:.0f}s, {du}\n{list(inspect.signature(QwenImageEditPlusPipeline.__call__).parameters)}"


@app.function(image=edit_image, gpu=["A100-80GB", "H100"], timeout=3600, volumes={"/models": models, "/work": work})
def first_frames(run_id: str, jobs: list[dict], modes: list[str]) -> list[str]:
    """jobs: [{"name", "refs": [paths under assets/], "prompt", "seed"}]. Writes
    /work/frames/<run_id>/<name>_<mode>.png for mode "fast" (8-step Lightning LoRA) and/or "full" (40 steps).
    Returns the volume paths written."""
    import math

    import torch
    from diffusers import FlowMatchEulerDiscreteScheduler, QwenImageEditPlusPipeline
    from PIL import Image
    out = pathlib.Path("/work/frames") / run_id
    out.mkdir(parents=True, exist_ok=True)
    t = time.time()
    pipe = QwenImageEditPlusPipeline.from_pretrained(EDIT_MODEL, torch_dtype=torch.bfloat16).to("cuda")
    base_scheduler = pipe.scheduler
    print(f"model on the GPU in {time.time() - t:.0f}s, {torch.cuda.memory_allocated() / 2**30:.1f} GB", flush=True)
    done = []

    def run(mode, **kw):
        for k, j in enumerate(jobs):
            t0 = time.time()
            p = out / f"{j['name']}_{mode}.png"
            try:
                if not p.exists():  # a retried run keeps what it already drew
                    refs = [Image.open(f"/root/assets/{r}").convert("RGB") for r in j["refs"]]
                    with torch.inference_mode():
                        img = pipe(image=refs, prompt=j["prompt"], negative_prompt=" ", width=j.get("width", 768),
                                   height=j.get("height", 1344), generator=torch.manual_seed(j.get("seed", 0)),
                                   num_images_per_prompt=1, **kw).images[0]
                    img.save(p)
                done.append(str(p).removeprefix("/work/"))
            except Exception as e:  # noqa: BLE001  (one bad frame must not sink the batch: that shot renders from text)
                print(f"{j['name']} {mode} FAILED: {type(e).__name__}: {e}", flush=True)
            if k % 10 == 9 or k == len(jobs) - 1:
                work.commit()
            print(f"{j['name']} {mode} in {time.time() - t0:.0f}s ({k + 1}/{len(jobs)})", flush=True)

    if "fast" in modes:
        # the Lightning LoRA's own schedule (from its model card): a fixed shift of 3
        pipe.scheduler = FlowMatchEulerDiscreteScheduler.from_config({
            "base_image_seq_len": 256, "base_shift": math.log(3), "invert_sigmas": False, "max_image_seq_len": 8192,
            "max_shift": math.log(3), "num_train_timesteps": 1000, "shift": 1.0, "shift_terminal": None,
            "stochastic_sampling": False, "time_shift_type": "exponential", "use_beta_sigmas": False,
            "use_dynamic_shifting": True, "use_exponential_sigmas": False, "use_karras_sigmas": False})
        pipe.load_lora_weights(EDIT_FAST[0], weight_name=EDIT_FAST[1])
        run("fast", num_inference_steps=8, true_cfg_scale=1.0)
        pipe.unload_lora_weights()
        pipe.scheduler = base_scheduler
    if "full" in modes:
        run("full", num_inference_steps=40, true_cfg_scale=4.0)
    return done
