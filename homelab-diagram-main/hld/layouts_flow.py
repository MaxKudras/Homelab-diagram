"""Flow layout: read from left to right.

Left: all panels in one column. Next to it the edge chain runs top → down (internet, ISP router,
firewall(s), core switch(es)). Right of the chain hang the trees (blocks) of every chain device,
each block level with the device it hangs on, stacked from top to bottom. Inside a block the same
tree as in the cluster layout (children in columns, entering from the left)."""
from . import panels as P
from . import theme as T

CHAIN_GAP = 96         # vertical gap between chain rows (room for straight cables)
TRACK_GAP = 200        # chain → blocks (cables run across here)
BLOCK_VGAP = 90        # between stacked blocks


def layout_flow(R):
    from . import render2 as R2
    R.build_tree()
    R.make_cables()
    lab = R.lab
    for n in R.nodes.values():
        if n.d.extra.get("kvm_note"):
            n.h += 26
        if n.kind == "server":
            n.w = n.server.best_w()
            n.h = n.server.size(n.w)
    # all panels stacked in the left column
    R.feat = R.features()
    R.left = [("networks", P.networks_h(lab)), ("legend", P.legend_h(R.feat))]
    y = 150 + sum(h + 20 for _, h in R.left)
    right = []
    if lab.cloud:
        h = len(lab.cloud) * 54 - 10
        right.append(("cloud", y, h))
        y += h + 18
    if lab.port_forwards:
        h = P.forwards_h(lab)
        right.append(("forwards", y, h))
        y += h + 20
    for p in lab.panels:
        fn = P.PANELS.get(p.get("type"))
        if fn:
            h = fn(R.S, lab, p, T.LEFT_X, y, T.RIGHT_W, draw=False)
            right.append((p, y, h))
            y += h + 20
    R.right = right
    T.RIGHT_X = T.LEFT_X                        # right-column panels move into the left column
    R.left_bottom = y
    R.right_bottom = 0
    # the edge chain, top → down, left-aligned next to the panels
    x0 = T.LEFT_X + max(T.LEFT_W, T.RIGHT_W) + 80
    y = P.CLOUD_Y + 58 + 60 + T.TAB
    prev = None
    chain_r = x0
    for ids in R.chain:
        nodes = [R.nodes[i] for i in ids]
        if prev is not None:
            y = prev + CHAIN_GAP + T.TAB
        gap = 120 if any(l.a_dev in ids and l.b_dev in ids for l in lab.links) else 40
        x = x0
        for n in nodes:
            n.x, n.y = x, y
            x += n.w + gap
        chain_r = max(chain_r, x - gap)
        prev = max(n.y + n.h for n in nodes)
    first = [R.nodes[i] for i in R.chain[0]] if R.chain else []
    if first and first[0].kind == "isp":
        up = next((p for p in first[0].d.ports if p.uplink), None)
        if up:
            T.CX = first[0].x + first[0].port_x[up.id]
    elif first:
        T.CX = first[0].x + first[0].w / 2
    # blocks right of the chain, stacked; pick the variant with the lowest picture
    cands = []
    for wgt in (0.05, 0.15, 0.4):
        R2.WIDTH_WEIGHT[0] = wgt
        bl = R.make_blocks()
        tot = sum(b.h for _, b in bl) + BLOCK_VGAP * max(0, len(bl) - 1)
        wid = max([b.w for _, b in bl] or [0])
        cands.append((max(tot, prev or 0), wid, bl))
    R2.WIDTH_WEIGHT[0] = 0.4
    fits = [c for c in cands if chain_r + TRACK_GAP + c[1] + T.MARGIN <= 3800]
    _, _, blocks = min(fits or cands, key=lambda c: (c[0], c[1]))
    R.blocks = blocks
    bx = chain_r + TRACK_GAP + R.n_block_tracks() * 0.5
    by = P.CLOUD_Y + 58 + 60 + T.TAB
    for root, b in blocks:
        yy = max(by, root.y if root else by)
        b.place(bx, yy)
        by = yy + b.h + BLOCK_VGAP
    width = max([bx + b.w for _, b in blocks] + [chain_r]) + T.MARGIN
    if width > T.W:
        R.set_width(width)
    R.bottom = max([n.y + n.h for n in R.nodes.values() if n.y is not None] + [R.left_bottom])
