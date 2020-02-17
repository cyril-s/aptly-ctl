from typing import Callable, Any, Iterable, List, Dict
from datetime import timedelta


def rotate(
    key_fmt: str, sort_func: Callable[[Any], Any], n: int, seq: Iterable,
) -> List[Any]:
    """
    Returns items in seq to rotate according to configured policy.
    seq is divided in groups by a hash key which is derived from
    key_fmt. Then items in every group are sorted by key set by
    sort_func in ascending order and last abs(n) items are selected.
    If n >= 0 the rest of items are returned for a group.
    If n < 0 these items are returned for a group.
    key_fmt is a python format string. Each item is passed to it as 'o' attribute.
    """
    h = {}  # type: Dict[str, List[Any]]
    for item in seq:
        h.setdefault(key_fmt.format(o=item), []).append(item)
    for k, v in h.items():
        v.sort(key=sort_func)
        N = min(len(v), abs(n))
        h[k] = v[: len(v) - N] if n >= 0 else v[len(v) - N :]
    return list(sum(h.values(), []))


def urljoin(*parts: str) -> str:
    if parts and parts[0].startswith("/"):
        prefix = "/"
    else:
        prefix = ""
    if parts and parts[-1].endswith("/"):
        suffix = "/"
    else:
        suffix = ""
    return prefix + "/".join(part.strip("/") for part in parts) + suffix


def timedelta_pretty(delta: timedelta) -> str:
    if delta == timedelta():
        return "0μs"
    out = []  # type: List[str]
    quot = abs(delta / timedelta.resolution)
    for div, unit in [
        (1000, "μs"),  # U+03BC
        (1000, "ms"),
        (60, "s"),
        (60, "m"),
        (24, "h"),
        (float("inf"), "d"),
    ]:
        quot, rem = divmod(quot, div)
        if rem > 0:
            out.append(format(rem, ".0f") + unit)
        if quot == 0:
            break
    if delta < timedelta():
        out.append("-")
    return "".join(reversed(out))
