"""QC and the full offline pipeline (sample script -> Kokoro -> auto storyboard -> toon2d render)."""
import json
import subprocess

import numpy as np
import pytest
from PIL import Image

from pipeline import qc

from .conftest import models_present


def test_qc_rejects_wrong_format(tmp_path):
    bad = tmp_path / "bad.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "color=c=red:s=720x1280:r=25:d=12",
                    "-f", "lavfi", "-i", "sine=f=440:d=12", "-shortest", "-c:v", "libx264", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", str(bad)], check=True)
    with pytest.raises(RuntimeError) as e:
        qc.check(bad)
    assert "1080x1920" in str(e.value) and "frame rate" in str(e.value)


@pytest.mark.slow
@pytest.mark.skipif(not models_present(), reason="Kokoro model not downloaded (python -m pipeline.fetch_models)")
@pytest.mark.parametrize("lang", ["hi", "en"])
def test_offline_end_to_end(lang, tmp_state, monkeypatch, tmp_path):
    pytest.importorskip("skia")
    from pipeline import produce
    monkeypatch.setattr(produce, "OUT", tmp_path / "out")
    cfg = produce.load_config()
    cfg["toon2d"]["resolution"] = 720 if lang == "hi" else 1080   # 720 is quick, but QC wants 1080: expect a clear error
    if lang == "hi":
        with pytest.raises(RuntimeError, match="not 1080x1920"):
            produce.produce_one(cfg, {"videos": []}, {"allocation": {}}, test=True, language=lang, theme="explainer")
        return
    work, meta, script, _ = produce.produce_one(cfg, {"videos": []}, {"allocation": {}}, test=True,
                                                language=lang, theme="explainer")
    final = work / "final.mp4"
    info = json.loads(subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams",
                                      "-show_format", str(final)], capture_output=True, text=True).stdout)
    v = next(s for s in info["streams"] if s["codec_type"] == "video")
    a = next(s for s in info["streams"] if s["codec_type"] == "audio")
    assert (v["width"], v["height"], v["avg_frame_rate"]) == (1080, 1920, "30/1")
    assert abs(float(v["duration"]) - float(a["duration"])) < 0.15
    assert meta["language"] == lang and meta["storyboard"] == "sample" and meta["voice_engine"] == "kokoro"
    tl = json.loads((work / "timeline.json").read_text())
    assert len(tl) == len(script["scenes"]) and all(x["end"] > x["start"] for x in tl)
    frames = []   # shots really differ from each other
    for line in tl[:4]:
        out = tmp_path / f"f{len(frames)}.png"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{line['start'] + 0.6:.2f}", "-i", str(final),
                        "-frames:v", "1", str(out)], check=True)
        frames.append(np.asarray(Image.open(out).convert("L").resize((54, 96)), np.float32))
    assert min(np.abs(frames[i] - frames[i + 1]).mean() for i in range(3)) > 5
