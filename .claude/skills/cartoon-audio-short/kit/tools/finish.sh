#!/usr/bin/env bash
# Encode frames + mix_raw.wav -> mp4, then QA.   bash finish.sh "Title Of Short"
# Loudness: one linear gain to about -14 LUFS (two-pass loudnorm, linear=true) plus a -1 dBFS true-peak limit.
set -e; T="${1:-short}"; F="out/${T// /-}.mp4"
J=$(ffmpeg -hide_banner -i mix_raw.wav -af loudnorm=I=-14:TP=-1:LRA=11:print_format=json -f null - 2>&1 | sed -n '/^{/,/^}/p')
read -r II TP LRA TH OFF <<<"$(python3 -c "import json,sys;d=json.loads(sys.argv[1]);print(d['input_i'],d['input_tp'],d['input_lra'],d['input_thresh'],d['target_offset'])" "$J")"
ffmpeg -v error -y -i mix_raw.wav -af "loudnorm=I=-14:TP=-1:LRA=11:measured_I=$II:measured_TP=$TP:measured_LRA=$LRA:measured_thresh=$TH:offset=$OFF:linear=true" -ar 48000 -ac 2 mix.wav
# Frames go to ffmpeg as raw RGB (decoded by Pillow), exactly like the 2D engine: JPEG's full-range YCbCr is handled
# differently by different ffmpeg versions (newer ones keep it full range), RGB -> yuv420p is TV range everywhere.
N=$(ls frames/f*.jpg | wc -l); read -r W H <<<"$(python3 -c "from PIL import Image; print(*Image.open('frames/f0000.jpg').size)")"
python3 frames_rgb.py frames "$N" | ffmpeg -v error -y -f rawvideo -pix_fmt rgb24 -s "${W}x${H}" -r 30 -i - -i mix.wav \
  -map 0:v:0 -map 1:a:0 -c:v libx264 -preset slow -crf 17 -pix_fmt yuv420p \
  -c:a aac -b:a 192k -ar 48000 -shortest -movflags +faststart "$F"
GOT=$(ffprobe -v error -select_streams v -show_entries stream=pix_fmt,color_range -of csv=p=0 "$F")
case "$GOT" in yuv420p|yuv420p,tv|yuv420p,unknown) ;; *) echo "finish.sh: output is $GOT, want yuv420p TV range"; exit 1;; esac
ffprobe -v error -show_entries format=duration -show_entries stream=width,height,r_frame_rate -of compact "$F"
echo "--- QA (empty = no black/frozen spans)"; ffmpeg -i "$F" -vf "freezedetect=n=0.0005:d=0.4,blackdetect=d=0.05" -an -f null - 2>&1 | grep -E "freeze_start|black_start" || true
ffmpeg -i "$F" -af ebur128 -f null - 2>&1 | grep -E "^\s+I:" | tail -1
ffmpeg -v error -y -i "$F" -vf "fps=2,scale=180:-1,tile=10x4" -frames:v 1 out/qa_sheet.jpg; echo "$F"
