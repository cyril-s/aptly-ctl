from typing import Callable, Any, Iterable, List, Dict


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
