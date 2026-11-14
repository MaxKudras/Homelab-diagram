"""Merge schema-2 dicts: lists of objects with an id/key are merged by that id, dicts deep-merged,
everything else replaced by the later value. Later sources win; overrides.yaml comes last."""

ID_KEYS = ("id", "key", "name")


def _id(o):
    if isinstance(o, dict):
        for k in ID_KEYS:
            if k in o:
                return (k, str(o[k]))
    return None


def merge(a, b):
    if isinstance(a, dict) and isinstance(b, dict):
        out = dict(a)
        for k, v in b.items():
            out[k] = merge(a[k], v) if k in a else v
        return out
    if isinstance(a, list) and isinstance(b, list) and all(_id(x) for x in a + b) and (a or b):
        out = list(a)
        pos = {_id(x): i for i, x in enumerate(out)}
        for x in b:
            k = _id(x)
            if k in pos:
                out[pos[k]] = merge(out[pos[k]], x)
            else:
                pos[k] = len(out)
                out.append(x)
        return out
    return b
