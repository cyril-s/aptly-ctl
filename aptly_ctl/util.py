from typing import Callable, Any, Iterable, List, Dict
from datetime import timedelta
import shutil
from math import ceil


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


def format_table(
    orig_table: List[List[Any]],
    max_col_width: int,
    sep=" ",
    min_subtable_col_num: int = 1,
) -> List[List[str]]:
    """
    Return formatted table. Non-list, empty and single sized lists are converted using str().
    List elements are arranged into a subtable. For every row of this subtable except the first
    a blank row is added to contain table rows. If blank row were created before,
    the elements at corresponding index are set.

    Arguments:
        max_col_width -- maximum column width. Taken into account
                         when formatting list element into subtable
        min_subtable_col_num -- minimum number of columns in a subtable
                                when formatting list element into subtable
        sep -- subtable column separator
    """
    if not orig_table:
        return []
    row_len = len(orig_table[0])
    blank_row = [""] * row_len
    table = []
    for row in orig_table:
        split_row = [[]]
        for elem_index, elem in enumerate(row):
            if not isinstance(elem, list):
                split_row[0].append(str(elem))
                continue
            if len(elem) == 0:
                split_row[0].append("")
                continue
            if len(elem) == 1:
                split_row[0].append(str(elem[0]))
                continue

            # arrange list row element in a subtable with `col_num` number of columns
            elem = sorted(elem)
            for col_num in range(min_subtable_col_num, max_col_width):
                length = ceil(len(elem) / col_num)
                subtable = [[] for _ in range(length)]
                for index, subelem in enumerate(elem):
                    subtable[index % length].append(str(subelem))
                col_widths = get_column_sizes(subtable)
                subtable_width = sum(col_widths) + (len(col_widths) - 1) * len(sep)
                if col_num <= min_subtable_col_num or subtable_width <= max_col_width:
                    best_subtable = subtable
                    continue
                break

            normalize_table(best_subtable)

            # inserting `best_subtable` into the `table`
            while len(split_row) < len(best_subtable):
                split_row.append(blank_row[:])
            split_row[0].append("")
            for subrow, subelem in zip(split_row, best_subtable):
                subrow[elem_index] = sep.join(subelem)

        table.extend(split_row)

    return table


def get_column_sizes(table: List[List[str]]) -> List[int]:
    """return a list of max sizes of every column in the table"""
    col_sizes = [0] * len(table[0])
    for row in table:
        for index, elem in enumerate(row):
            if len(elem) >= col_sizes[index]:
                col_sizes[index] = len(elem)
    return col_sizes


def normalize_table(table: List[List[str]]) -> None:
    """
    Bring all elements to the size of the longest string in that column
    padding it with spaces from the rigth
    """
    col_sizes = get_column_sizes(table)
    for row in table:
        for col_index, elem in enumerate(row):
            row[col_index] += " " * (col_sizes[col_index] - len(elem))


def print_table(
    orig_table: List[List[Any]],
    header: List[str] = None,
    sep: str = " ",
    header_sep: str = "-",
) -> None:
    """Prints matrix orig_table converting every element to string as table"""
    if not orig_table:
        return
    # assume that all row are of equal width
    row_len = len(orig_table[0])
    term_width, _ = shutil.get_terminal_size()
    # TODO maybe find the way to detect max_col_size more accurately
    max_col_size = term_width // row_len - len(sep)
    table = format_table(orig_table, max_col_size)
    if header:
        table.insert(0, header)
    normalize_table(table)
    if header:
        header_sep = [header_sep * size for size in map(len, table[0])]
        table.insert(1, header_sep)
    for row in table:
        print(*row, sep=sep)
