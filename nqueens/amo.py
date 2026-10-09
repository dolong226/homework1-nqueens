"""At-most-one (AMO) encodings.

Every encoder has the signature ``encode(lits, top) -> (clauses, top)`` where
``top`` is the largest variable index in use; auxiliary variables are numbered
from ``top + 1`` and the updated ``top`` is returned.

Binary (bitwise) and sequential counter come from PySAT's ``pysat.card``.
Pairwise, commander and recursive product are implemented directly. The
implementations are adapted from the existing coursework AMO module.
"""

from __future__ import annotations

from itertools import combinations
from math import ceil, isqrt

from pysat.card import CardEnc, EncType


def _pysat(enc_type):
    def encode(lits, top):
        if len(lits) < 2:
            return [], top
        cnf = CardEnc.atmost(lits=lits, bound=1, top_id=top, encoding=enc_type)
        return cnf.clauses, max(top, cnf.nv)
    return encode


def pairwise(lits, top):
    return [[-a, -b] for a, b in combinations(lits, 2)], top


def commander(lits, top, group_size=3):
    """Commander encoding (Klieber & Kwon, 2007) with groups of ``group_size``."""
    if len(lits) <= group_size + 1:
        return pairwise(lits, top)
    clauses, commanders = [], []
    for i in range(0, len(lits), group_size):
        group = lits[i:i + group_size]
        top += 1
        cmd = top
        commanders.append(cmd)
        clauses += [[-a, -b] for a, b in combinations(group, 2)]
        clauses += [[-x, cmd] for x in group]      # a true member forces the commander
        clauses.append([-cmd] + group)             # a true commander has a true member
    rest, top = commander(commanders, top, group_size)
    return clauses + rest, top


def product(lits, top):
    """Product encoding (Chen, 2010): place the literals on a p x q grid."""
    k = len(lits)
    if k <= 4:
        return pairwise(lits, top)
    p = isqrt(k - 1) + 1          # ceil(sqrt(k))
    q = ceil(k / p)
    rows = list(range(top + 1, top + p + 1))
    cols = list(range(top + p + 1, top + p + q + 1))
    top += p + q
    clauses = []
    for idx, x in enumerate(lits):
        clauses.append([-x, rows[idx // q]])
        clauses.append([-x, cols[idx % q]])
    for aux in (rows, cols):
        sub, top = product(aux, top)
        clauses += sub
    return clauses, top


ENCODINGS = {
    "pairwise": pairwise,
    "binary": _pysat(EncType.bitwise),
    "commander": commander,
    "product": product,
    "seqcounter": _pysat(EncType.seqcounter),
}
