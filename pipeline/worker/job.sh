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
#       CLIPS_ONLY   1 = render the shots and ship them as $OUT/<slug>/raw.tar, no songs or edit (see shoot.py)
#       GEN_FRAMES   override the frames per clip (config.yaml clip_frames), e.g. 49 for ~2 s
#       TRAIN_DATA_URL  train a video LoRA instead of rendering (see train_lora.py): a tar with dataset.json
#                    + clips; TRAIN_TRIGGER, TRAIN_STEPS, TRAIN_BUCKETS; checkpoints land in $OUT/lora/
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

# 2. installs and downloads run in the background while the GPU writes the songs, so the box pays
# for them once instead of in a row. Background jobs can't call fail(): they leave a reason file.
L=$MODELS/ltx-2.5
prep_ltx() {  # LTX-2.5 distilled: code + ~66 GB of gated weights
  if [ ! -d $W/ltx ]; then
    git clone -q https://github.com/Lightricks/LTX-2.git $W/ltx && git -C $W/ltx checkout -q $LTX_COMMIT || { echo "ltx clone"; return 1; }
  fi
  ( cd $W/ltx && uv sync -q --no-dev --extra natten ) || ( cd $W/ltx && uv sync -q --no-dev ) || { echo "ltx install"; return 1; }
  ( cd $W/ltx && uv pip install -q "huggingface_hub[cli,hf_transfer]" ) || true
  # LTX's torch is built for CUDA 13; on an older host driver it silently falls back to the CPU
  ( cd $W/ltx && uv run --no-sync python -c "import torch; assert torch.cuda.is_available()" ) \
    || { echo "GPU unusable by LTX's torch (host driver older than CUDA 13: $(nvidia-smi --query-gpu=driver_version --format=csv,noheader))"; return 1; }
  log "ltx installed, downloading weights"
  FAST=$(cd $W/ltx && uv run --no-sync python -c "import hf_transfer; print(1)" 2>/dev/null || echo 0)
  ( cd $W/ltx && HF_HUB_ENABLE_HF_TRANSFER=$FAST HF_TOKEN=$HF_TOKEN uv run --no-sync hf download Lightricks/LTX-2.5 \
      diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors \
      text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors \
      vae/ltx-2.5-video-vae-conv-bf16.safetensors \
      vae/ltx-2.5-audio-vae-bf16.safetensors \
      latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors \
      --local-dir "$L" >/dev/null ) || { echo "ltx download (is HF_TOKEN set and the LTX-2.5 terms accepted?)"; return 1; }
  log "ltx weights ready"
}
prep_asm() {  # captions + edit: stable-ts, demucs and their models
  uv venv -q -p 3.12 $W/asm && VIRTUAL_ENV=$W/asm uv pip install -q pillow librosa soundfile pyyaml stable-ts demucs \
    || { echo "asm install"; return 1; }
  $W/asm/bin/python -c "import stable_whisper; stable_whisper.load_model('medium', device='cpu')
from demucs.pretrained import get_model; get_model('htdemucs')" >/dev/null 2>&1 || true
  log "caption tools ready"
}
( prep_ltx > $W/ltx.err 2>&1 ) & LTX_PID=$!
( prep_asm > $W/asm.err 2>&1 ) & ASM_PID=$!
await() {  # await PID NAME: wait for a background prep job, fail with its reason
  wait "$1" || fail "$2: $(tail -3 $W/$2.err | tr '\n' ' ')"
}

# 3. songs (YuE2, ~7 GB of weights, not gated)
[ -n "${PROBE_MODES:-}${CLIPS_ONLY:-}${TRAIN_DATA_URL:-}" ] || {
stage "songs"
[ -d $W/yue ] || git clone --depth 1 https://github.com/multimodal-art-projection/YuE.git $W/yue
uv venv -q -p 3.12 $W/yue/.venv && VIRTUAL_ENV=$W/yue/.venv uv pip install -q "$W/yue" || fail "yue install"
$W/yue/.venv/bin/python "$GE/worker/gen_song.py" "$B" || fail "yue generate"
log "songs ready: $(ls $B/*/song.flac 2>/dev/null | wc -l)"
}

# 4. clips
stage "clips: waiting for ltx download"
await $LTX_PID ltx

VRAM_MIB=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1)
if [ -n "${TRAIN_DATA_URL:-}" ]; then  # LoRA training instead of a batch
  T=$W/train; mkdir -p $T "$OUT/lora"
  stage "train: install"
  ( cd $W/ltx && uv sync -q --no-dev --extra natten --all-packages ) || fail "trainer install"
  curl -sfL "$TRAIN_DATA_URL" | tar -x -C $T || fail "train data download"
  log "dataset: $(python3 -c "import json;print(len(json.load(open('$T/dataset.json'))))" ) clips"
  stage "train: preprocess"
  ( cd $W/ltx/packages/ltx-trainer && uv run --no-sync python scripts/process_dataset.py $T/dataset.json \
      --resolution-buckets "${TRAIN_BUCKETS:-512x896x49}" --skip-audio --lora-trigger "${TRAIN_TRIGGER:-}" \
      --model-path "$L/diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors" \
      --text-encoder-path "$L/text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors" \
      --video-vae-path "$L/vae/ltx-2.5-video-vae-conv-bf16.safetensors" \
      --output-dir $T/.precomputed ) > "$OUT/train.log" 2>&1 || fail "preprocess: $(tail -3 $OUT/train.log | tr '\n' ' ')"
  python3 "$GE/worker/lora_config.py" "$L" $T "$OUT/lora" "${TRAIN_STEPS:-1500}" "$VRAM_MIB" > $T/config.yaml || fail "train config"
  stage "train: steps"
  # the watchdog needs a changing STAGE: mirror the trainer's latest step line every minute
  ( while sleep 60; do l=$(grep -a -o -E "[Ss]tep[ :]+[0-9]+[^,]{0,20}" "$OUT/train.log" | tail -1); [ -n "$l" ] && echo "train: $l" > "$OUT/STAGE"; done ) & TICK=$!
  ( cd $W/ltx/packages/ltx-trainer && uv run --no-sync python scripts/train.py $T/config.yaml --disable-progress-bars ) >> "$OUT/train.log" 2>&1
  rc=$?; kill $TICK 2>/dev/null
  find "$OUT/lora" -name "*.safetensors" | sort > "$OUT/lora/files.txt"
  [ -s "$OUT/lora/files.txt" ] || fail "training (exit $rc): $(tail -5 $OUT/train.log | tr '\n' ' ')"
  log "lora checkpoints: $(wc -l < $OUT/lora/files.txt)"
  : > "$OUT/done.txt"; stage "DONE"; self_destruct_later; wait; exit 0
fi
GW=$(python3 -c "import yaml,sys;c=yaml.safe_load(open('$GE/config.yaml'));print(c['video']['gen_width'],c['video']['gen_height'],c['video']['clip_frames'])" 2>/dev/null || echo "768 1344 121")
read -r GWIDTH GHEIGHT GFRAMES <<<"$GW"
GFRAMES=${GEN_FRAMES:-$GFRAMES}
# 24 GB cards can't hold Gemma or the transformer: stream weights from CPU RAM (~2 min a clip on a 3090).
# 32 GB cards fit just barely (one prompt at a time, no fragmentation); if they still run out, the
# missing clips are retried with offload below.
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
VRAM=$(nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | head -1)
OFFLOAD=(); [ "${VRAM:-0}" -lt 28000 ] && OFFLOAD=(--offload cpu)
missing_clips() {  # how many shots have no clip yet
  python3 -c "import json,pathlib,sys;print(sum(not (d/'clips'/f'shot_{i:02d}.mp4').exists() for d in pathlib.Path(sys.argv[1]).iterdir() if (d/'plan.json').exists() for i in range(len(json.loads((d/'plan.json').read_text())['shots']))))" "$B"
}
# character LoRAs the plans ask for (concept.expand lists them): download once, apply to the whole batch
LORA_ARGS=()
mkdir -p $W/loras
while read -r url strength; do
  [ -n "$url" ] || continue
  f=$W/loras/$(basename "$url")
  [ -s "$f" ] || curl -sfL "$url" -o "$f" || fail "lora download $url"
  LORA_ARGS+=(--lora "$f" "$strength"); log "lora: $(basename "$f") at $strength"
done < <(python3 -c "
import json, pathlib, sys
seen = {}
for p in pathlib.Path(sys.argv[1]).glob('*/plan.json'):
    for l in json.loads(p.read_text()).get('loras', []):
        seen[l['url']] = l.get('strength', 1.0)
for u, s in seen.items(): print(u, s)" "$B")
clips() {  # extra args go to LTX, e.g. --offload cpu
( cd $W/ltx && STAGE_FILE="$OUT/STAGE" uv run --no-sync python "$GE/worker/gen_clips.py" "$B" -- \
    --transformer-path       "$L/diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors" \
    --text-encoder-path      "$L/text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors" \
    --video-vae-path         "$L/vae/ltx-2.5-video-vae-conv-bf16.safetensors" \
    --audio-vae-path         "$L/vae/ltx-2.5-audio-vae-bf16.safetensors" \
    --spatial-upsampler-path "$L/latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors" \
    --width "$GWIDTH" --height "$GHEIGHT" --num-frames "$GFRAMES" --frame-rate 24 \
    --quantization fp8-cast "${LORA_ARGS[@]}" "$@" )
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
TOTAL_CLIPS=$(missing_clips)
clips "${OFFLOAD[@]}"; rc=$?
if [ ${#OFFLOAD[@]} -eq 0 ] && [ "$(missing_clips)" -gt 0 ]; then
  log "$(missing_clips) clips missing after rendering without offload (exit $rc): retrying them with --offload cpu"
  clips --offload cpu; rc=$?
fi
[ "$(missing_clips)" -eq 0 ] || log "$(missing_clips) clips still missing (exit $rc)"
[ "$(missing_clips)" -lt "$TOTAL_CLIPS" ] || fail "ltx render (exit $rc, no clip made)"

if [ -n "${CLIPS_ONLY:-}" ]; then
  : > "$OUT/done.txt"
  for d in $B/*/; do
    s=$(basename "$d"); mkdir -p "$OUT/$s"
    tar -cf "$OUT/$s/raw.tar" -C "$d" clips && echo "$s" >> "$OUT/done.txt"
  done
  stage "DONE"; self_destruct_later; wait; exit 0
fi

# 5. time the lyrics for the captions (whisper alignment on the demucs vocals); a miss only drops captions
stage "captions"
await $ASM_PID asm
for d in $B/*/; do
  [ -f "$d/song.flac" ] || continue
  ( cd "$GE" && $W/asm/bin/python -m ge.lyrics --song "$d/song.flac" --plan "$d/plan.json" --out "$d/words.json" ) \
    || log "$(basename "$d"): lyric timing FAILED (no captions)"
done

# 6. edit each finished video: beat cuts, hook text, captions, end card, loudness
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
  tar -cf "$OUT/$s/raw.tar" -C "$d" clips song.flac $( [ -f "$d/words.json" ] && echo words.json ) || true
done
[ -s "$OUT/done.txt" ] || fail "no video finished"
stage "DONE"
self_destruct_later
wait
