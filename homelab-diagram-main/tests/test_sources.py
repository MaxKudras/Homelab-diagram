"""Tests for the data sources (offline, with the fixtures) and the whole pipeline.

Run: python3 -m unittest discover tests      (from homelab-diagram-main/)
"""
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
FX = ROOT / "tests" / "fixtures"

from hld.sources import ansible, collect, merge, netbox, opnsense, prometheus, proxmox  # noqa: E402
from hld.sources.base import SourceError  # noqa: E402


class Sources(unittest.TestCase):
    def test_netbox(self):
        d = netbox.collect({"type": "netbox", "url": "x", "token_env": "NB", "fixture": str(FX / "netbox.json")})
        ids = {x["id"]: x for x in d["devices"]}
        self.assertEqual(set(ids), {"fritzbox", "heimdall", "hvergelmir", "walkuere", "valhalla", "pve1"})
        self.assertEqual(ids["hvergelmir"]["role"], "switch")
        self.assertEqual(len(ids["hvergelmir"]["ports"]), 9)
        self.assertTrue(any(p.get("uplink") for p in ids["fritzbox"]["ports"]))
        links = {(l["a"], l["b"]): l for l in d["links"]}
        self.assertIn(("heimdall.lan", "hvergelmir.Gi1/0/1"), links)
        self.assertEqual(links[("heimdall.lan", "hvergelmir.Gi1/0/1")]["vlans"], ["10", "20", "40", "50"])
        self.assertEqual(links[("hvergelmir.Te1/0/1", "pve1.enp1s0")]["speed"], "10G")
        self.assertEqual({n["key"]: n.get("subnet") for n in d["networks"]}["20"], "10.10.20.0/24")
        self.assertEqual(ids["pve1"]["guests"][0]["name"], "netbox")

    def test_proxmox(self):
        d = proxmox.collect({"type": "proxmox", "url": "x", "token_env": "PVE", "fixture": str(FX / "proxmox.json")})
        node = d["devices"][0]
        self.assertEqual(node["id"], "pve1")
        g = {x["id"]: x for x in node["guests"]}
        self.assertEqual(g[1217]["ip"], "10.10.20.217")
        self.assertEqual(g[1217]["net"], "20")
        self.assertEqual(g[6227]["kind"], "VM")
        self.assertIn("gestoppt", g[9230]["note"])

    def test_ansible(self):
        d = ansible.collect({"type": "ansible", "inventory": str(FX / "ansible" / "hosts.yml")})
        ids = {x["id"]: x for x in d["devices"]}
        self.assertEqual(ids["heimdall"]["role"], "firewall")
        self.assertEqual(ids["pve1"]["role"], "server")
        g = {x["name"]: x for x in ids["pve1"]["guests"]}
        self.assertEqual(g["pihole"]["icons"], ["pihole"])          # from host_vars
        self.assertEqual(g["immich"]["kind"], "VM")
        self.assertEqual(d["links"][0]["a"], "hvergelmir.Gi1/0/5")

    def test_prometheus(self):
        d = prometheus.collect({"type": "prometheus", "url": "x", "fixture": str(FX / "prometheus.json")})
        self.assertEqual(d["_monitor"]["valhalla"], "down")
        self.assertEqual(d["_monitor"]["pve1"], "up")

    def test_opnsense(self):
        d = opnsense.collect({"type": "opnsense", "url": "x", "key_env": "K", "secret_env": "S",
                              "fixture": str(FX / "opnsense.json")})
        ips = {e["ip"]: e for e in d["_ips"]}
        self.assertEqual(ips["100.64.10.10"]["name"], "Laptop")
        self.assertEqual(ips["192.168.50.121"]["kind"], "static")

    def test_missing_secret(self):
        with self.assertRaises(SourceError):
            netbox.collect({"type": "netbox", "url": "http://127.0.0.1:9", "token_env": "HLD_TEST_UNSET_VAR"})

    def test_merge_links_by_ends(self):
        a = {"links": [{"a": "x.1", "b": "y", "speed": "1G"}]}
        b = {"links": [{"a": "x.1", "b": "y", "speed": "10G"}, {"a": "x.2", "b": "z"}]}
        m = merge.merge(a, b)
        self.assertEqual(len(m["links"]), 2)
        self.assertEqual(m["links"][0]["speed"], "10G")

    def test_gather_all(self):
        import yaml
        cfgs = yaml.safe_load((ROOT / "sources.example.yaml").read_text())["sources"]
        for c in cfgs:
            for k in ("fixture", "inventory"):
                if c.get(k):
                    c[k] = str(ROOT / c[k])
        d, report, errors = collect.gather(cfgs)
        self.assertEqual(errors, [])
        ids = {x["id"]: x for x in d["devices"]}
        self.assertIn("muninn", ids)                                   # only Ansible knows it
        self.assertEqual(ids["valhalla"]["monitor"], "down")
        pve = {g["id"]: g for g in ids["pve1"]["guests"]}
        self.assertEqual(pve[1217]["icons"], ["pihole"])              # Proxmox + Ansible merged
        self.assertEqual(pve[1217]["ip"], "10.10.20.217")
        self.assertNotIn("10.10.20.16", [e["ip"] for e in d["ip_extra"]])   # lease of a known host dropped


class Pipeline(unittest.TestCase):
    def _draw(self, f, layout):
        import build
        from hld import qa, validate
        from hld.model import Lab
        from hld.render import Renderer
        from hld.render2 import Renderer2
        from hld.text import configure
        lab = Lab(build.load(f))
        configure(lab.meta.get("domain", ""), "redacted.test", True)
        err, _ = validate.check(lab)
        self.assertEqual(err, [])
        if layout == "auto":
            layout = build.auto_layout(lab)
        R = Renderer(lab) if layout == "rows" else Renderer2(lab, layout=layout)
        H = R.draw("t")
        return R, qa.run(R.S), qa.score(R.S, R.S.w, H)

    def test_examples_render_without_qa_problems(self):
        """Every lab in the default layout and in cluster/flow: no overlaps, no stacked cables, every
        cable routed (SVG only, no PNG: fast)."""
        for f in sorted((ROOT / "examples").glob("*.yaml")) + [ROOT / "inventory.yaml"]:
            for layout in ("auto", "cluster", "flow"):
                with self.subTest(lab=f.name, layout=layout):
                    R, problems, _ = self._draw(f, layout)
                    self.assertEqual(problems, [])
                    self.assertEqual(getattr(R, "failed", []), [])

    def test_manual_layout(self):
        """Positions from the file are used 1:1, waypoints are followed."""
        import copy
        import yaml
        d = yaml.safe_load((ROOT / "examples" / "manuell.yaml").read_text())
        d = copy.deepcopy(d)
        for l in d["links"]:
            if l["b"] == "pi":
                l["via"] = [[1172, 1180]]
        import build
        from hld import qa
        from hld.model import Lab
        from hld.render2 import Renderer2
        from hld.text import configure
        lab = Lab(d)
        configure("example.net", "redacted.test", True)
        self.assertEqual(build.auto_layout(lab), "manual")
        R = Renderer2(lab, layout="manual")
        R.draw("t")
        self.assertEqual(qa.run(R.S), [])
        self.assertEqual((R.nodes["pc"].x, R.nodes["pc"].y), (40.0, 1250.0))
        pi = next(c for c in R.cables if c["b"].id == "pi" or c["a"].id == "pi")
        self.assertIn((1172.0, 1180.0), pi["pts"])

    def test_cluster_stays_tidy(self):
        """Guard against chaos coming back: few crossings in the big labs (cluster layout)."""
        limits = {"max-zukunft.yaml": 15, "stress-60.yaml": 10, "klein.yaml": 0, "aus-quellen.yaml": 0}
        for name, limit in limits.items():
            with self.subTest(lab=name):
                _, _, sc = self._draw(ROOT / "examples" / name, "cluster")
                self.assertLessEqual(sc["Kreuzungen"], limit)


if __name__ == "__main__":
    unittest.main()
