"""Sequential fresh-process benchmark with a hard wall-clock budget per run.

Timing includes model construction and solving. Wall-clock deadlines also
include imports and license acquisition. CSV is resumable only with matching
configuration; raw JSONL stores every solution for independent revalidation.
"""
import argparse
import csv
from importlib.metadata import version
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

AMOS = ["pairwise","binary","commander","product","seqcounter"]
SAT_SOLVERS = ["cadical195","glucose42","minisat22","maplechrono"]
REFERENCE_SAT = "sat:cadical195:commander:minimal"
EXPERIMENTS = {
    "encodings":[f"sat:cadical195:{amo}:{variant}" for variant in ("minimal","extended") for amo in AMOS],
    "solvers":[f"sat:{name}:commander:minimal" for name in SAT_SOLVERS],
    "exact":[REFERENCE_SAT,"cplex_cp","cplex_mip","gurobi","cpsat"],
    "scaling":[REFERENCE_SAT,"cplex_cp","cplex_mip","gurobi","cpsat"],
}
FIELDS = ["n","method","repeat","seed","budget","status","n_vars","n_constraints",
          "build_time","solve_time","total_time","setup_time","wall_time","process_time","valid","error_type","error"]


def run_one(n,method,budget,seed=1):
    start = time.perf_counter()
    command = [sys.executable,"-m","nqueens.run_one",str(n),method,"--time-limit",str(budget),"--seed",str(seed),"--worker"]
    process = subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,encoding="utf-8")
    try:
        stdout,stderr = process.communicate(timeout=budget)
    except subprocess.TimeoutExpired:
        if os.name == "nt":
            # CP Optimizer is a child process; kill our complete solver tree.
            subprocess.run(["taskkill","/PID",str(process.pid),"/T","/F"],capture_output=True)
        else:
            process.kill()
        process.communicate()
        return dict(status="TIMEOUT",process_time=time.perf_counter()-start,error="hard process deadline")
    elapsed = time.perf_counter()-start
    try:
        result = json.loads(stdout.strip().splitlines()[-1])
    except (ValueError,IndexError):
        return dict(status="ERROR",process_time=elapsed,error=stderr[-1500:])
    result["process_time"] = elapsed
    if process.returncode and result.get("status") != "ERROR":
        result.update(status="ERROR",error=stderr[-1500:])
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("experiment",choices=EXPERIMENTS)
    parser.add_argument("--sizes",nargs="+",type=int,default=[8,16,32,64,96,128])
    parser.add_argument("--repeats",type=int,default=3)
    parser.add_argument("--time-limit",type=float,default=15)
    parser.add_argument("--results",default="results")
    args = parser.parse_args()
    if args.repeats < 1 or args.time_limit <= 0 or any(n < 1 for n in args.sizes):
        parser.error("sizes, repeats and time limit must be positive")
    directory = Path(args.results)
    directory.mkdir(parents=True,exist_ok=True)
    config = vars(args) | dict(methods=EXPERIMENTS[args.experiment],python=sys.version,
        platform=platform.platform(),cpu=platform.processor(),logical_cpus=os.cpu_count(),
        packages={name:version(name) for name in ("python-sat","gurobipy","cplex","docplex","ortools")},
        threads=1,symmetry_breaking=False)
    manifest = directory / f"{args.experiment}.config.json"
    if manifest.exists() and json.loads(manifest.read_text()) != config:
        parser.error("configuration differs from existing results; choose a new --results directory")
    manifest.write_text(json.dumps(config,indent=2),encoding="utf-8")
    csv_path = directory / f"{args.experiment}.csv"
    raw_path = directory / f"{args.experiment}.jsonl"
    lock_path = directory / f"{args.experiment}.lock"
    try:
        with lock_path.open("x") as lock:
            lock.write(str(os.getpid()))
    except FileExistsError:
        parser.error(f"experiment locked: {lock_path}")
    try:
        done = set()
        if csv_path.exists():
            with csv_path.open(newline="") as handle:
                done = {(int(row["n"]),row["method"],int(row["repeat"])) for row in csv.DictReader(handle)}
        else:
            with csv_path.open("w",newline="",encoding="utf-8") as handle:
                csv.DictWriter(handle,FIELDS).writeheader()
        # Rotate method order between repeats to reduce a fixed-order bias.
        methods = EXPERIMENTS[args.experiment]
        for repeat in range(1,args.repeats+1):
            for n in args.sizes:
                rotated = methods[repeat-1:] + methods[:repeat-1]
                for method in rotated:
                    if (n,method,repeat) in done:
                        continue
                    result = run_one(n,method,args.time_limit,repeat)
                    row = dict(n=n,method=method,repeat=repeat,seed=repeat,budget=args.time_limit,**result)
                    with raw_path.open("a",encoding="utf-8") as handle:
                        handle.write(json.dumps(row)+"\n")
                    with csv_path.open("a",newline="",encoding="utf-8") as handle:
                        csv.DictWriter(handle,FIELDS,extrasaction="ignore").writerow(row)
                    print(f"n={n:4} repeat={repeat} {method:42} {row['status']:8} {row['process_time']:.3f}s",flush=True)
    finally:
        lock_path.unlink()


if __name__ == "__main__":
    main()
