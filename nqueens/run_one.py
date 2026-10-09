"""Solve one board, print a machine-readable result, optionally export DIMACS.

Every CLI solve has a process-enforced deadline, including for SAT.
"""
import argparse
import json
from pathlib import Path
import sys
import time
from .board import validate_n,check_solution
from .exact_models import SOLVERS
from .sat_model import solve,clauses


def run(n,method,time_limit=30,seed=1):
    validate_n(n)
    start = time.perf_counter()
    if method.startswith("sat:"):
        _,solver,amo,variant = method.split(":")
        result = solve(n,solver,amo,variant)
    else:
        result = SOLVERS[method](n,time_limit,seed)
    result["total_time"] = result["build_time"] + result["solve_time"]
    result["wall_time"] = time.perf_counter()-start
    result["valid"] = check_solution(n,result["solution"]) if result["status"] == "SAT" else None
    if result["status"] == "SAT" and not result["valid"]:
        raise RuntimeError("independent checker rejected the solver solution")
    return result


def export_dimacs(n,amo,variant,path):
    """Stream twice, avoiding a full CNF copy on large boards."""
    top,count = n*n,0
    for clause,top in clauses(n,amo,variant):
        count += 1
    with Path(path).open("w",encoding="ascii") as out:
        out.write(f"c N-queens n={n} {amo} {variant}\np cnf {top} {count}\n")
        for clause,_ in clauses(n,amo,variant):
            out.write(" ".join(map(str,clause))+" 0\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("n",type=int)
    parser.add_argument("method",nargs="?",default="sat:cadical195:commander:minimal")
    parser.add_argument("--time-limit",type=float,default=30)
    parser.add_argument("--seed",type=int,default=1)
    parser.add_argument("--dimacs")
    parser.add_argument("--worker",action="store_true",help=argparse.SUPPRESS)
    args = parser.parse_args()
    try:
        validate_n(args.n)
        if args.time_limit <= 0:
            raise ValueError("time-limit must be positive")
        if args.dimacs:
            if not args.method.startswith("sat:"):
                raise ValueError("DIMACS export requires a SAT method")
            _,_,amo,variant = args.method.split(":")
            export_dimacs(args.n,amo,variant,args.dimacs)
            print(json.dumps(dict(dimacs=str(Path(args.dimacs).resolve()))))
        elif args.worker:
            print(json.dumps(run(args.n,args.method,args.time_limit,args.seed)))
        else:
            from .experiment import run_one
            result = run_one(args.n,args.method,args.time_limit,args.seed)
            print(json.dumps(result))
            if result["status"] == "ERROR":
                sys.exit(1)
    except Exception as exc:
        print(json.dumps(dict(status="ERROR",error_type=type(exc).__name__,error=str(exc))))
        sys.exit(1)


if __name__ == "__main__":
    main()
