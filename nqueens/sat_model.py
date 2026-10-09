"""Streaming CNF construction; row EO, column/diagonal AMO.

The extended variant also adds redundant column ALO clauses. Both variants
have the same projected solutions. No symmetry breaking or constructive hints.
"""
import time
from pysat.solvers import Solver
from .amo import ENCODINGS
from .board import groups, decode


def clauses(n, amo="seqcounter", variant="minimal"):
    if variant not in ("minimal", "extended"):
        raise ValueError("unknown SAT variant")
    top = n * n
    encoder = ENCODINGS[amo]
    for kind, literals in groups(n):
        if kind == "row" or (kind == "column" and variant == "extended"):
            yield literals, top
        encoded, top = encoder(literals, top)
        for clause in encoded:
            yield clause, top


def solve(n, solver_name="cadical195", amo="seqcounter", variant="minimal", **_):
    t0 = time.perf_counter()
    top, count = n * n, 0
    with Solver(name=solver_name) as solver:
        for clause, top in clauses(n, amo, variant):
            solver.add_clause(clause)
            count += 1
        t1 = time.perf_counter()
        sat = solver.solve()
        t2 = time.perf_counter()
        solution = decode(n, (x for x in solver.get_model() if x > 0)) if sat else None
        return dict(status="SAT" if sat else "UNSAT", solution=solution,
                    n_vars=top, n_constraints=count, build_time=t1-t0,
                    solve_time=t2-t1, solver_stats=solver.accum_stats())
