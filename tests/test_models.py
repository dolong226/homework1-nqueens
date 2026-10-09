"""Semantic tests: exhaustive AMO truth tables and projected solution counts.

N-queens counts 1,0,0,2,10,4,40,92 are independently obtained by backtracking.
Blocking only board variables ensures auxiliary assignments are not overcounted.
Commercial integration tests are opt-in and exercise SAT and UNSAT cases.
"""
from itertools import product
import os
import tempfile
from pathlib import Path
import unittest
from pysat.solvers import Solver
from nqueens.amo import ENCODINGS
from nqueens.board import check_solution,decode,validate_n
from nqueens.sat_model import clauses
from nqueens.run_one import run,export_dimacs
from nqueens.experiment import run_one


def backtrack(n):
    solutions = []
    def visit(columns):
        r = len(columns)
        if r == n:
            solutions.append(tuple(columns))
            return
        for c in range(n):
            if all(c != d and abs(c-d) != r-i for i,d in enumerate(columns)):
                visit(columns+[c])
    visit([])
    return set(solutions)


class ModelTests(unittest.TestCase):
    def test_amo_truth_tables(self):
        for name,encoder in ENCODINGS.items():
            for k in range(12):
                for polarity in (1,-1):
                    literals = [polarity*i for i in range(1,k+1)]
                    formula,top = encoder(literals,k)
                    self.assertGreaterEqual(top,k)
                    with Solver(name="minisat22",bootstrap_with=formula) as solver:
                        for bits in product((False,True),repeat=k):
                            assumptions = [lit if value else -lit for lit,value in zip(literals,bits)]
                            self.assertEqual(solver.solve(assumptions=assumptions),sum(bits) <= 1,(name,k,bits))

    def test_all_projected_solutions(self):
        for n in range(1,9):
            expected = backtrack(n)
            self.assertEqual(len(expected),[1,0,0,2,10,4,40,92][n-1])
            for amo in ENCODINGS:
                for variant in ("minimal","extended"):
                    found = set()
                    with Solver(name="minisat22",bootstrap_with=[c for c,_ in clauses(n,amo,variant)]) as solver:
                        while solver.solve():
                            solution = decode(n,[v for v in solver.get_model() if v > 0])
                            self.assertTrue(check_solution(n,solution))
                            found.add(tuple(solution))
                            solver.add_clause([-(r*n+c+1) for r,c in enumerate(solution)])
                    self.assertEqual(found,expected,(n,amo,variant))

    def test_checker_rejects_collisions_and_invalid_data(self):
        self.assertTrue(check_solution(4,[1,3,0,2]))
        for bad in ([0,0,2,3],[0,1,2,3],[1,3,0],[1,3,0,4],[True,3,0,2],None):
            self.assertFalse(check_solution(4,bad))
        for n in (0,-1,True,1.5):
            self.assertFalse(check_solution(n,[]))
            with self.assertRaises(ValueError):
                validate_n(n)

    def test_hard_timeout(self):
        result = run_one(128,"sat:cadical195:pairwise:minimal",.001)
        self.assertEqual(result["status"],"TIMEOUT")

    def test_dimacs_roundtrip(self):
        from pysat.formula import CNF
        with tempfile.TemporaryDirectory(dir=Path.cwd()) as directory:
            path = Path(directory)/"queens.cnf"
            export_dimacs(8,"product","extended",path)
            cnf = CNF(from_file=str(path))
            with Solver(name="minisat22",bootstrap_with=cnf) as solver:
                self.assertTrue(solver.solve())
                self.assertTrue(check_solution(8,decode(8,[v for v in solver.get_model() if v > 0])))

    def test_available_sat_backends(self):
        for name in ("cadical195","glucose42","minisat22","maplechrono"):
            self.assertEqual(run(3,f"sat:{name}:seqcounter:minimal")["status"],"UNSAT")
            self.assertTrue(run(8,f"sat:{name}:seqcounter:minimal")["valid"])

    @unittest.skipUnless(os.environ.get("NQUEENS_INTEGRATION") == "1","opt-in commercial solver tests")
    def test_exact_backends(self):
        for method in ("cpsat","cplex_cp","cplex_mip","gurobi"):
            self.assertEqual(run(3,method,10)["status"],"UNSAT",method)
            self.assertTrue(run(8,method,10)["valid"],method)


if __name__ == "__main__":
    unittest.main()
