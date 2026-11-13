"""Download the free Kokoro voice model once (cached by GitHub Actions)."""
import urllib.request

from .common import MODELS, log

BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/"
FILES = {"kokoro.onnx": "kokoro-v1.0.int8.onnx", "voices.bin": "voices-v1.0.bin"}


def main():
    MODELS.mkdir(exist_ok=True)
    for local, remote in FILES.items():
        dest = MODELS / local
        if dest.exists() and dest.stat().st_size > 1_000_000:
            log(f"{local} already here")
            continue
        log(f"Downloading {remote}")
        urllib.request.urlretrieve(BASE + remote, dest)


if __name__ == "__main__":
    main()
