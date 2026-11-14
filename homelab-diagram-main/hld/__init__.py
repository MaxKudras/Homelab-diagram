"""hld – homelab diagram engine (v2).

Data (any number of devices, links, servers, guests) → model → layout (placement + cable
router) → SVG/PNG in the look of the original hand-placed diagram.

Modules:
  theme     palette, line widths, sizes
  text      exact text measurement (Pillow + the bundled Fira fonts), redaction helpers
  svg       SVG primitives (+ QA registry of every text box, card and cable)
  parts     drawing building blocks (cards, jacks, chips, pools …), measure-first
  model     data model (dataclasses) built from a schema-2 dict
  validate  data checks with German messages
  legacy    converts the original inventory.yaml (schema 1) into schema 2
  sources   automatic data sources (Ansible, NetBox, Proxmox, Prometheus, …)
  layout    rows/tiers/placement, route = channel cable router
  panels    side panels (networks, legend, port forwards, cloud, flows, IP list)
  server    the big server cards (hardware, guest cards, zones with chips)
  qa        overlap checks on the finished drawing
  render    puts it all together
"""
