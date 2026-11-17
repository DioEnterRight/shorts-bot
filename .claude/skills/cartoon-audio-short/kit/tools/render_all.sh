#!/usr/bin/env bash
# Render frames 0..N-1 in parallel Chromium processes:  bash render_all.sh <N> [jobs]
# jobs defaults to CPU count - 1. Each process renders every jobs-th frame. RESUME=1 skips finished frames.
set -e; N="${1:?total frames}"; J="${2:-$(( $(nproc) > 1 ? $(nproc) - 1 : 1 ))}"; mkdir -p frames; pids=()
for ((j = 0; j < J; j++)); do
  [ "$j" -lt "$N" ] || break
  node render.mjs frames "$j-$((N - 1))" "$J" > "frames/log_$j.txt" 2>&1 & pids+=($!)
done
for p in "${pids[@]}"; do wait "$p" || { echo "render job failed, see frames/log_*.txt"; exit 1; }; done
n=$(ls frames/f*.jpg | wc -l); [ "$n" -eq "$N" ] || { echo "only $n of $N frames"; exit 1; }
tail -qn1 frames/log_*.txt; echo "frames ok: $N"
