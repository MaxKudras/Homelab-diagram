"""Planning tool: generated file is current, YAML round trip through the browser renders cleanly."""
import json
import re
import pathlib
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def _have_playwright():
    if not shutil.which("node"):
        return False
    r = subprocess.run(["node", "-e", "require('playwright')"], capture_output=True)
    return r.returncode == 0


class Planer(unittest.TestCase):
    def test_file_is_current(self):
        """planer/planer.html is generated from planer/src: rebuild after changes."""
        sys.path.insert(0, str(ROOT / "planer"))
        import build_planer
        with tempfile.TemporaryDirectory() as t:
            out = build_planer.build(pathlib.Path(t) / "p.html")
            # icons depend on what fetch_icons.py downloaded in this checkout: compare everything else
            strip = lambda s: re.sub(r"const ICONS = .*?;\n", "", s, count=1)
            self.assertEqual(strip(out.read_text()), strip((ROOT / "planer" / "planer.html").read_text()),
                             "planer.html ist veraltet: python3 planer/build_planer.py")

    @unittest.skipUnless(_have_playwright(), "Node + Playwright fehlen")
    def test_roundtrip(self):
        import yaml
        from hld import qa
        from hld.model import Lab
        from hld.render2 import Renderer2
        from hld.text import configure
        import build
        with tempfile.TemporaryDirectory() as t:
            out = pathlib.Path(t) / "export.yaml"
            r = subprocess.run(["node", str(ROOT / "tests" / "planer_roundtrip.js"), str(out)],
                               capture_output=True, text=True, timeout=120)
            self.assertEqual(r.returncode, 0, r.stderr)
            res = json.loads(r.stdout.strip().splitlines()[-1])
            self.assertEqual(res["errs"], [])
            self.assertEqual(res["pc1"]["x"], res["pc0"]["x"] - 160)
            self.assertEqual(res["link"], {"a": "sw.p6", "b": res["prId"], "speed": "1G", "net": "20"})
            d = yaml.safe_load(out.read_text())
        self.assertIn("Notebook", [x.get("name") for x in d["devices"]])
        lab = Lab(d)
        configure("example.net", "redacted.test", True)
        self.assertEqual(build.auto_layout(lab), "manual")
        R = Renderer2(lab, layout="manual")
        R.draw("t")
        self.assertEqual(qa.run(R.S), [])
        # the PC was dragged left of the margin: the drawing moves right instead of cutting it off
        self.assertGreaterEqual(min(n.x for n in R.nodes.values()), 40)
        self.assertIn(res["prId"], R.nodes)


if __name__ == "__main__":
    unittest.main()
