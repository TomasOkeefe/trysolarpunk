#!/usr/bin/env bash
# Runs on the rented GPU box. Produces $OUT/final.mp4 from $GE/plan.json.
#
# Expects the repo checked out at /workspace/repo (see the start command in ge/runpod.py).
# Env:  HF_TOKEN   Hugging Face read token (LTX-2.5 weights are gated: accept the terms once on HF)
#       PLAN_B64 or PLAN_FILE   the video plan
#       OUT_TOKEN  random string; outputs are served at http://<box>:8080/<OUT_TOKEN>/
#       KEEP_MIN   minutes to keep the box alive after finishing so the video can be fetched (default 40)
set -uo pipefail
W=/workspace; GE=${GE_DIR:-$W/repo/pipeline}; TOKEN=${OUT_TOKEN:-run}; OUT=$W/out/$TOKEN; MODELS=$W/models
mkdir -p "$OUT" "$MODELS"
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
stage "setup"
export DEBIAN_FRONTEND=noninteractive UV_CACHE_DIR=$W/.uv-cache
# RunPod images set HF_HUB_ENABLE_HF_TRANSFER=1 globally, which breaks downloads in venvs without hf_transfer
export HF_HUB_ENABLE_HF_TRANSFER=0
apt-get update -qq && apt-get install -y -qq ffmpeg git curl >/dev/null || fail "apt"
curl -LsSf https://astral.sh/uv/install.sh | sh >/dev/null && export PATH="$HOME/.local/bin:$PATH"
# the plan: PLAN_B64 (sent by run.py) or PLAN_FILE (a path inside the repo, for runs started by hand)
if [ -n "${PLAN_B64:-}" ]; then echo "$PLAN_B64" | base64 -d > "$GE/plan.json"
elif [ -n "${PLAN_FILE:-}" ]; then cp "$GE/$PLAN_FILE" "$GE/plan.json"; fi
[ -f "$GE/plan.json" ] || fail "no plan.json"

# 1. fonts for the overlays (not shipped in the repo to keep it small)
mkdir -p "$GE/assets/fonts"
for f in "ofl/fraunces/Fraunces%5BSOFT,WONK,opsz,wght%5D.ttf:Fraunces.ttf" "ofl/spacemono/SpaceMono-Bold.ttf:SpaceMono-Bold.ttf"; do
  src=${f%%:*}; dst=${f##*:}
  [ -f "$GE/assets/fonts/$dst" ] || curl -sfL "https://raw.githubusercontent.com/google/fonts/main/$src" -o "$GE/assets/fonts/$dst"
done

# 2. song (YuE2, ~7 GB of weights, not gated)
stage "song"
if [ ! -f "$OUT/song.flac" ]; then
  [ -d $W/yue ] || git clone --depth 1 https://github.com/multimodal-art-projection/YuE.git $W/yue
  uv venv -q -p 3.12 $W/yue/.venv && VIRTUAL_ENV=$W/yue/.venv uv pip install -q "$W/yue" || fail "yue install"
  $W/yue/.venv/bin/python "$GE/worker/gen_song.py" "$GE/plan.json" "$W/song" 1 || fail "yue generate"
  cp "$W/song/song_0/audio.flac" "$OUT/song.flac"
fi
log "song ready: $(du -h "$OUT/song.flac" | cut -f1)"

# 3. clips (LTX-2.5 distilled, ~66 GB of weights, gated)
stage "clips: install"
[ -d $W/ltx ] || git clone --depth 1 https://github.com/Lightricks/LTX-2.git $W/ltx
( cd $W/ltx && uv sync -q --no-dev --extra natten ) || ( cd $W/ltx && uv sync -q --no-dev ) || fail "ltx install"
( cd $W/ltx && uv pip install -q "huggingface_hub[cli,hf_transfer]" ) || true
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
stage "clips: render"
GW=$(python3 -c "import yaml,sys;c=yaml.safe_load(open('$GE/config.yaml'));print(c['video']['gen_width'],c['video']['gen_height'],c['video']['clip_frames'])" 2>/dev/null || echo "768 1344 121")
read -r GWIDTH GHEIGHT GFRAMES <<<"$GW"
PRODUCT=$(python3 -c "import json;print(json.load(open('$GE/plan.json'))['product'])")
IMG="$GE/assets/hib_fridge.jpg"; [ "$PRODUCT" = "eyelid" ] && IMG="$GE/assets/eyelid_studio.jpg"
( cd $W/ltx && uv run --no-sync python "$GE/worker/gen_clips.py" "$GE/plan.json" "$W/clips" "$IMG" -- \
    --transformer-path       "$L/diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors" \
    --text-encoder-path      "$L/text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors" \
    --video-vae-path         "$L/vae/ltx-2.5-video-vae-conv-bf16.safetensors" \
    --audio-vae-path         "$L/vae/ltx-2.5-audio-vae-bf16.safetensors" \
    --spatial-upsampler-path "$L/latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors" \
    --width "$GWIDTH" --height "$GHEIGHT" --num-frames "$GFRAMES" --frame-rate 24 \
    --quantization fp8-cast --offload cpu ) || fail "ltx render"
log "clips: $(ls $W/clips | wc -l)"

# 4. edit: beat cuts, hook text, AI label, end card, loudness
stage "assemble"
uv venv -q -p 3.12 $W/asm && VIRTUAL_ENV=$W/asm uv pip install -q pillow librosa soundfile pyyaml || fail "asm install"
( cd "$GE" && $W/asm/bin/python -m ge.assemble --plan plan.json --song "$OUT/song.flac" --clips $W/clips --out "$OUT/final.mp4" ) || fail "assemble"
cp "$GE/plan.json" "$OUT/plan.json"
for i in 1 4 7; do ffmpeg -loglevel error -y -ss $((i*5)) -i "$OUT/final.mp4" -frames:v 1 -vf scale=360:-2 "$OUT/thumb_$i.jpg"; done
stage "DONE"
self_destruct_later
wait
