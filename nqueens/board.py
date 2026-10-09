"""Shared geometry and an independent solution checker (zero-based columns)."""
from collections import defaultdict


def validate_n(n):
    if isinstance(n, bool) or not isinstance(n, int) or n < 1:
        raise ValueError("n must be a positive integer")


def groups(n):
    validate_n(n)
    for r in range(n):
        yield "row", [r * n + c + 1 for c in range(n)]
    for c in range(n):
        yield "column", [r * n + c + 1 for r in range(n)]
    down, up = defaultdict(list), defaultdict(list)
    for r in range(n):
        for c in range(n):
            down[r - c].append(r * n + c + 1)
            up[r + c].append(r * n + c + 1)
    for diagonals in (down, up):
        for cells in diagonals.values():
            if len(cells) > 1:
                yield "diagonal", cells


def check_solution(n, columns):
    """Reject invalid lengths, repeated columns and either diagonal collision."""
    if type(n) is not int or n < 1:
        return False
    if not isinstance(columns, (list, tuple)) or len(columns) != n:
        return False
    if any(type(c) is not int or not 0 <= c < n for c in columns):
        return False
    return (len(set(columns)) == n
            and len({r - c for r, c in enumerate(columns)}) == n
            and len({r + c for r, c in enumerate(columns)}) == n)


def decode(n, positive_literals):
    columns = [-1] * n
    for lit in positive_literals:
        if 1 <= lit <= n * n:
            r, c = divmod(lit - 1, n)
            if columns[r] != -1:
                raise ValueError("model contains two queens in a row")
            columns[r] = c
    return columns
