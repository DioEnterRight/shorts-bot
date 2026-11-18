#!/usr/bin/env python3
"""Write models/index.json (name -> file) and models/CATALOG.md (one compact line per pack with sizes in metres).

    python3 tools/build_model_catalog.py [kit/models]

Sizes come from the POSITION accessor bounds with node translation/scale (rotation ignored), so they are close
but not exact. CATALOG.md is what Claude reads; it never needs to open the model files.
"""
import json
import struct
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent / "models")


def gltf_json(p):
    if p.suffix == ".glb":
        b = p.read_bytes()
        n = struct.unpack_from("<I", b, 12)[0]
        return json.loads(b[20:20 + n])
    return json.loads(p.read_text(encoding="utf-8"))


def size(g):
    lo, hi = [1e9] * 3, [-1e9] * 3

    def walk(i, t, s):
        nd = g["nodes"][i]
        t = [t[k] + s[k] * nd.get("translation", [0, 0, 0])[k] for k in range(3)]
        s = [s[k] * nd.get("scale", [1, 1, 1])[k] for k in range(3)]
        if "mesh" in nd:
            for prim in g["meshes"][nd["mesh"]]["primitives"]:
                acc = g["accessors"][prim["attributes"]["POSITION"]]
                for k in range(3):
                    a, b = t[k] + s[k] * acc["min"][k], t[k] + s[k] * acc["max"][k]
                    lo[k], hi[k] = min(lo[k], a, b), max(hi[k], a, b)
        for c in nd.get("children", []):
            walk(c, t, s)

    for r in g["scenes"][g.get("scene", 0)]["nodes"]:
        walk(r, [0, 0, 0], [1, 1, 1])
    return [round(hi[k] - lo[k], 1) for k in range(3)]


index, lines = {}, []
for pack in sorted(d for d in ROOT.iterdir() if d.is_dir()):
    items = []
    for f in sorted(list(pack.glob("*.gltf")) + list(pack.glob("*.glb"))):
        name = f"{pack.name}/{f.stem}"
        index[name] = f"{pack.name}/{f.name}"
        w, h, d = size(gltf_json(f))
        items.append(f"{f.stem} {w}x{h}x{d}")
    lines.append(f"## {pack.name} ({len(items)})\n" + ", ".join(items))
(ROOT / "index.json").write_text(json.dumps(index, indent=0), encoding="utf-8")
(ROOT / "CATALOG.md").write_text(
    "# 3D models (KayKit, CC0). Use: await model('pack/name', x, y, z, {scale, rotY, tint})\n"
    "# Sizes are width x height x depth in metres at scale 1 (approx). Characters stay 2D cards (2.25 m tall).\n"
    "# Scale to match the cards: city 5 (streetlight 5 m, buildings 8-15 m), furniture 0.7, restaurant 0.7,\n"
    "# dungeon 0.5 (barrel_large ~1 m). Mix models with the kit's painted primitives; models get toon shading\n"
    "# and ink outlines automatically. Load them in the world section (top-level await works in main.js).\n\n"
    + "\n\n".join(lines) + "\n", encoding="utf-8")
print(f"{len(index)} models -> {ROOT / 'CATALOG.md'}")
