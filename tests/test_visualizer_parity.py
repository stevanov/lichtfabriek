"""Cross-language parity: engine.py primitives vs the shipped viz.js (V23).

The JS preview must show exactly what the Pi renders. Runs the SAME vectors
through both implementations — Python directly, JS via node + viz.js — and
compares. Skipped when node is not available (dev convenience; CI has node).
"""

import json
import math
import shutil
import subprocess
from pathlib import Path

import pytest

from kubusd.engine import PRIMITIVE_FUNCS

REPO = Path(__file__).resolve().parent.parent
VIZ = REPO / "console" / "static" / "viz.js"

VECTORS = [
    # (primitive, params, times)
    ("rainbow", {"speed": 1.0, "offset": 0.3, "brightness": 0.8}, [0.0, 0.5, 1.37]),
    ("huesweep", {"speed": 1.5}, [0.0, 0.7]),
    ("pulse", {"speed": 1.0, "offset": 0.5,
               "colors": [[255, 0, 0], [0, 255, 0], [0, 0, 255]]}, [0.1, 0.9, 2.0]),
    ("fade", {"speed": 1.0, "colors": [[255, 0, 0], [0, 255, 0]]}, [0.2, 0.45]),
    ("chase", {"speed": 2.0, "offset": 0.5, "colors": [[255, 255, 0]]}, [0.1, 0.5]),
    ("holiday", {"speed": 1.0, "seed": 7, "offset": 0.2}, [0.3, 1.1]),
    ("random", {"speed": 1.0, "seed": 3}, [0.0, 0.4, 1.0]),
    ("fire", {"speed": 2.0, "seed": 11}, [0.05, 0.31, 0.9]),
    ("sparkle", {"speed": 1.0, "seed": 5}, [0.0, 0.2, 0.75]),
    ("sine", {"speed": 1.0, "offset": 0.5,
              "colors": [[255, 0, 0], [0, 0, 255]]}, [0.25, 0.75]),
    ("strobe", {"speed": 1.0, "offset": 0.25}, [0.1, 0.6]),
    ("police", {"speed": 1.5}, [0.1, 0.35]),
    ("knight", {"speed": 1.0, "offset": 0.33}, [0.2, 0.7]),
    ("static", {"brightness": 0.5, "colors": [[10, 200, 30]]}, [1.0]),
    ("off", {}, [0.0]),
]


def _py_frame(prim, params, t):
    return [round(c, 9) for c in PRIMITIVE_FUNCS[prim](t, params)]


def test_viz_js_parity():
    if shutil.which("node") is None:
        pytest.skip("node not available")
    script = ";".join(
        f"out.push({{prim: {json.dumps(p)}, t: {t}, "
        f"c: PRIMS[{json.dumps(p)}]({t}, {json.dumps(params)})}})"
        for p, params, times in VECTORS for t in times)
    js = (f"const {{PRIMS}} = require({json.dumps(str(VIZ))});\n"
          f"const out = [];\n{script}\n"
          "console.log(JSON.stringify(out));")
    res = subprocess.run(["node", "-e", js], capture_output=True, text=True,
                         timeout=30)
    assert res.returncode == 0, f"node failed: {res.stderr}"
    js_frames = {(o["prim"], o["t"]): o["c"] for o in json.loads(res.stdout)}
    for prim, params, times in VECTORS:
        for t in times:
            py = _py_frame(prim, params, t)
            jsf = [float(c) for c in js_frames[(prim, t)]]
            assert all(math.isclose(a, b, abs_tol=1e-9)
                       for a, b in zip(py, jsf)), \
                f"parity drift {prim} t={t}: python={py} js={jsf}"
