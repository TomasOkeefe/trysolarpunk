#!/usr/bin/env bash
# Runs on the rented GPU box. Renders a batch of videos: $OUT/<slug>/final.mp4 for each plan.
# Order keeps each model loaded once: all songs (YuE2), then all clips (LTX), then all edits.
#
# Expects the repo checked out at /workspace/repo (see the start command in ge/runpod.py).
# Env:  HF_TOKEN   Hugging Face read token (LTX-2.5 weights are gated: accept the terms once on HF)
#       PLANS_B64  gzipped JSON list of plans (sent by run.py), or
#       PLAN_FILES space-separated plan paths inside the repo, relative to pipeline/ (runs started by hand)
#       OUT_TOKEN  random string; outputs are served at http://<box>:8080/<OUT_TOKEN>/
#       KEEP_MIN   minutes to keep the box alive after finishing so the videos can be fetched (default 40)
#       PROBE_MODES  GPU probe instead of a batch: e.g. "none cpu" renders 2 shots per LTX offload mode
#                    (no songs, no edit) and writes timings to $OUT/probe.txt (see probe.py)
set -uo pipefail
W=/workspace; GE=${GE_DIR:-$W/repo/pipeline}; TOKEN=${OUT_TOKEN:-run}; OUT=$W/out/$TOKEN; MODELS=$W/models
B=$W/batch
LTX_COMMIT=be6d6d0  # gen_clips.py uses private hooks of this exact version; bump deliberately
mkdir -p "$OUT" "$MODELS" "$B"
log()   { echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$OUT/status.log"; }
stage() { echo "$1" > "$OUT/STAGE"; log "== $1"; }
# on failure keep serving the log instead of exiting: an exited container gets restarted and would loop
fail()  { stage "FAILED: $1"; self_destruct_later; wait; exit 1; }
self_destruct_later() {
  # RunPod pods carry RUNPOD_POD_ID + a pod-scoped key for runpodctl; Vast injects CONTAINER_ID/CONTAINER_API_KEY.
  ( sleep $(( ${KEEP_MIN:-40} * 60 ))
    if [ -n "${RUNPOD_POD_ID:-}" ]; then runpodctl remove pod "$RUNPOD_POD_ID"
    elif [ -n "${CONTAINER_ID:-}" ]; then pip install -q vastai && vastai destroy instance "$CONTAINER_ID" --api-key "$CONTAINER_API_KEY"; fi
  ) >/dev/null 2>&1 &
}
exec >>"$OUT/job.log" 2>&1

# 0. status server first, so progress is visible from the start
python3 "$GE/worker/serve.py" 8080 "$W/out" &
stage "setup on $(nvidia-smi --query-gpu=name --format=csv,noheader 2>/dev/null | head -1)"
export DEBIAN_FRONTEND=noninteractive UV_CACHE_DIR=$W/.uv-cache
# RunPod images set HF_HUB_ENABLE_HF_TRANSFER=1 globally, which breaks downloads in venvs without hf_transfer
export HF_HUB_ENABLE_HF_TRANSFER=0
apt-get update -qq && apt-get install -y -qq ffmpeg git curl >/dev/null || fail "apt"
curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null && export PATH="$HOME/.local/bin:$PATH"
# the plans: one folder per video, $B/<slug>/plan.json
python3 - "$B" <<'EOF' || fail "bad plans"
import base64, gzip, json, os, pathlib, sys
b, ge = pathlib.Path(sys.argv[1]), pathlib.Path(os.environ.get("GE_DIR", "/workspace/repo/pipeline"))
if os.environ.get("PLANS_B64"):
    plans = json.loads(gzip.decompress(base64.b64decode(os.environ["PLANS_B64"])))
else:
    plans = [json.loads((ge / f).read_text()) for f in os.environ.get("PLAN_FILES", "").split()]
assert plans, "no plans"
for p in plans:
    (b / p["slug"]).mkdir(exist_ok=True)
    (b / p["slug"] / "plan.json").write_text(json.dumps(p))
print(len(plans), "plans")
EOF
log "plans: $(ls $B | tr '\n' ' ')"

# 1. fonts for the overlays (not shipped in the repo to keep it small)
mkdir -p "$GE/assets/fonts"
for f in "ofl/fraunces/Fraunces%5BSOFT,WONK,opsz,wght%5D.ttf:Fraunces.ttf" "ofl/spacemono/SpaceMono-Bold.ttf:SpaceMono-Bold.ttf"; do
  src=${f%%:*}; dst=${f##*:}
  [ -f "$GE/assets/fonts/$dst" ] || curl -sfL "https://raw.githubusercontent.com/google/fonts/main/$src" -o "$GE/assets/fonts/$dst"
done

# 2. songs (YuE2, ~7 GB of weights, not gated)
[ -n "${PROBE_MODES:-}" ] || {
stage "songs"
[ -d $W/yue ] || git clone --depth 1 https://github.com/multimodal-art-projection/YuE.git $W/yue
uv venv -q -p 3.12 $W/yue/.venv && VIRTUAL_ENV=$W/yue/.venv uv pip install -q "$W/yue" || fail "yue install"
$W/yue/.venv/bin/python "$GE/worker/gen_song.py" "$B" || fail "yue generate"
log "songs ready: $(ls $B/*/song.flac 2>/dev/null | wc -l)"
}

# 3. clips (LTX-2.5 distilled, ~66 GB of weights, gated)
stage "clips: install"
if [ ! -d $W/ltx ]; then
  git clone -q https://github.com/Lightricks/LTX-2.git $W/ltx && git -C $W/ltx checkout -q $LTX_COMMIT || fail "ltx clone"
fi
( cd $W/ltx && uv sync -q --no-dev --extra natten ) || ( cd $W/ltx && uv sync -q --no-dev ) || fail "ltx install"
( cd $W/ltx && uv pip install -q "huggingface_hub[cli,hf_transfer]" ) || true
# LTX's torch is built for CUDA 13; on an older host driver it silently falls back to the CPU
( cd $W/ltx && uv run --no-sync python -c "import torch; assert torch.cuda.is_available()" ) \
  || fail "GPU unusable by LTX's torch (host driver older than CUDA 13: $(nvidia-smi --query-gpu=driver_version --format=csv,noheader))"
stage "clips: download weights"
L=$MODELS/ltx-2.5
FAST=$(cd $W/ltx && uv run --no-sync python -c "import hf_transfer; print(1)" 2>/dev/null || echo 0)
( cd $W/ltx && HF_HUB_ENABLE_HF_TRANSFER=$FAST HF_TOKEN=$HF_TOKEN uv run --no-sync hf download Lightricks/LTX-2.5 \
    diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors \
    text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors \
    vae/ltx-2.5-video-vae-conv-bf16.safetensors \
    vae/ltx-2.5-audio-vae-bf16.safetensors \
    latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors \
    --local-dir "$L" ) || fail "ltx download (is HF_TOKEN set and the LTX-2.5 terms accepted?)"
GW=$(python3 -c "import yaml,sys;c=yaml.safe_load(open('$GE/config.yaml'));print(c['video']['gen_width'],c['video']['gen_height'],c['video']['clip_frames'])" 2>/dev/null || echo "768 1344 121")
read -r GWIDTH GHEIGHT GFRAMES <<<"$GW"
# cards under 40 GB can't hold Gemma or the transformer: stream weights from CPU RAM (~2 min a clip on a 3090)
VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1)
OFFLOAD=(); [ "${VRAM:-0}" -lt 40000 ] && OFFLOAD=(--offload cpu)
clips() {  # extra args go to LTX, e.g. --offload cpu
( cd $W/ltx && STAGE_FILE="$OUT/STAGE" uv run --no-sync python "$GE/worker/gen_clips.py" "$B" -- \
    --transformer-path       "$L/diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors" \
    --text-encoder-path      "$L/text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors" \
    --video-vae-path         "$L/vae/ltx-2.5-video-vae-conv-bf16.safetensors" \
    --audio-vae-path         "$L/vae/ltx-2.5-audio-vae-bf16.safetensors" \
    --spatial-upsampler-path "$L/latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors" \
    --width "$GWIDTH" --height "$GHEIGHT" --num-frames "$GFRAMES" --frame-rate 24 \
    --quantization fp8-cast "$@" )
}
if [ -n "${PROBE_MODES:-}" ]; then
  mkdir -p "$OUT/probe"
  { nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader; free -g | sed -n 2p; } > "$OUT/probe.txt"
  for m in $PROBE_MODES; do
    stage "probe: offload $m"
    t0=$(date +%s)
    CLIPS_SUBDIR=clips_$m PROBE_SHOTS=2 clips --offload "$m" 2>&1 | tee "$OUT/probe_$m.log" | grep --line-buffered -E "done in|encoded|resident|offload|FAILED|Error|error" | sed "s/^/$m: /" >> "$OUT/probe.txt"
    echo "$m: exit ${PIPESTATUS[0]} after $(( $(date +%s) - t0 ))s" >> "$OUT/probe.txt"
    for f in $B/*/clips_$m/*.mp4; do [ -f "$f" ] && cp "$f" "$OUT/probe/${m}_$(basename "$f")"; done
  done
  : > "$OUT/done.txt"; stage "DONE"; self_destruct_later; wait; exit 0
fi
# no --offload: gen_clips.py frees Gemma before loading the transformer, so both never share the card
stage "clips: render"
log "VRAM ${VRAM} MiB: ${OFFLOAD[*]:-no offload}"
clips "${OFFLOAD[@]}" || fail "ltx render"

# 4. time the lyrics for the captions (whisper alignment on the demucs vocals); a miss only drops captions
stage "captions"
uv venv -q -p 3.12 $W/asm && VIRTUAL_ENV=$W/asm uv pip install -q pillow librosa soundfile pyyaml stable-ts demucs || fail "asm install"
for d in $B/*/; do
  [ -f "$d/song.flac" ] || continue
  ( cd "$GE" && $W/asm/bin/python -m ge.lyrics --song "$d/song.flac" --plan "$d/plan.json" --out "$d/words.json" ) \
    || log "$(basename "$d"): lyric timing FAILED (no captions)"
done

# 5. edit each finished video: beat cuts, hook text, captions, end card, loudness
stage "assemble"
: > "$OUT/done.txt"
for d in $B/*/; do
  s=$(basename "$d"); n=$(python3 -c "import json;print(len(json.load(open('$d/plan.json'))['shots']))")
  if [ ! -f "$d/song.flac" ] || [ "$(ls $d/clips/shot_*.mp4 2>/dev/null | wc -l)" -ne "$n" ]; then
    log "$s: SKIPPED (missing song or clips)"; continue
  fi
  mkdir -p "$OUT/$s"
  ( cd "$GE" && $W/asm/bin/python -m ge.assemble --plan "$d/plan.json" --song "$d/song.flac" --clips "$d/clips" --words "$d/words.json" --out "$OUT/$s/final.mp4" ) \
    && cp "$d/plan.json" "$OUT/$s/plan.json" && echo "$s" >> "$OUT/done.txt" && log "$s: done" \
    || log "$s: assemble FAILED"
done
[ -s "$OUT/done.txt" ] || fail "no video finished"
stage "DONE"
self_destruct_later
wait
