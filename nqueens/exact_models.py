"""Identical CP formulations and identical binary MIP formulations.

Single worker/thread and explicit seeds. Solver errors are never interpreted as
UNSAT or silently relabeled as license failures. WLS credentials remain local.
"""
import os
from pathlib import Path
import time
from .board import groups, decode


def _result(status, t0, t1, t2, n_vars, n_constraints, solution=None, **extra):
    return dict(status=status, build_time=t1-t0, solve_time=t2-t1,
                n_vars=n_vars, n_constraints=n_constraints, solution=solution, **extra)


def solve_cpsat(n, time_limit=30, seed=1):
    from ortools.sat.python import cp_model
    t0 = time.perf_counter()
    model = cp_model.CpModel()
    q = [model.new_int_var(0, n-1, f"q{r}") for r in range(n)]
    model.add_all_different(q)
    model.add_all_different([q[r] + r for r in range(n)])
    model.add_all_different([q[r] - r for r in range(n)])
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = seed
    t1 = time.perf_counter()
    status = solver.solve(model)
    t2 = time.perf_counter()
    if status == cp_model.MODEL_INVALID:
        raise RuntimeError(solver.response_stats())
    found = status in (cp_model.FEASIBLE, cp_model.OPTIMAL)
    outcome = "SAT" if found else "UNSAT" if status == cp_model.INFEASIBLE else "TIMEOUT"
    return _result(outcome,t0,t1,t2,n,3,[solver.value(v) for v in q] if found else None)


def cp_executable():
    if os.environ.get("CPO_EXECUTABLE"):
        return os.environ["CPO_EXECUTABLE"]
    base = Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "IBM/ILOG"
    installed = sorted(base.glob("CPLEX_Studio*/cpoptimizer/bin/x64_win64/cpoptimizer.exe"))
    return str(installed[-1]) if installed else "cpoptimizer"


def solve_cplex_cp(n, time_limit=30, seed=1):
    from docplex.cp.model import CpoModel
    t0 = time.perf_counter()
    model = CpoModel()
    q = model.integer_var_list(n,0,n-1,"q")
    model.add(model.all_diff(q))
    model.add(model.all_diff([q[r]+r for r in range(n)]))
    model.add(model.all_diff([q[r]-r for r in range(n)]))
    t1 = time.perf_counter()
    result = model.solve(execfile=cp_executable(),TimeLimit=time_limit,
                         Workers=1,RandomSeed=seed,LogVerbosity="Quiet")
    t2 = time.perf_counter()
    found = result.is_solution()
    status = "SAT" if found else "UNSAT" if result.get_solve_status() == "Infeasible" else "TIMEOUT"
    return _result(status,t0,t1,t2,n,3,[int(result[v]) for v in q] if found else None)


def configure_license():
    if "GRB_LICENSE_FILE" not in os.environ:
        for folder in (Path(__file__).resolve().parents[1],Path(__file__).resolve().parents[2]):
            license_file = folder / "gurobi.lic"
            if license_file.is_file():
                os.environ["GRB_LICENSE_FILE"] = str(license_file)
                break


def solve_gurobi(n, time_limit=30, seed=1):
    import gurobipy as gp
    configure_license()
    # License acquisition is recorded separately from model construction.
    start = time.perf_counter()
    with gp.Env(empty=True) as env:
        env.setParam("OutputFlag",0)
        env.start()
        t0 = time.perf_counter()
        with gp.Model(env=env) as model:
            x = model.addVars(n*n,vtype=gp.GRB.BINARY)
            count = 0
            for kind,literals in groups(n):
                expr = gp.quicksum(x[v-1] for v in literals)
                model.addConstr(expr == 1 if kind in ("row","column") else expr <= 1)
                count += 1
            model.Params.Threads = 1
            model.Params.Seed = seed
            model.Params.TimeLimit = time_limit
            model.update()
            t1 = time.perf_counter()
            model.optimize()
            t2 = time.perf_counter()
            found = model.SolCount > 0
            if not found and model.Status not in (gp.GRB.INFEASIBLE,gp.GRB.TIME_LIMIT):
                raise RuntimeError(f"unexpected Gurobi status: {model.Status}")
            solution = decode(n,(i+1 for i in range(n*n) if x[i].X > .5)) if found else None
            status = "SAT" if found else "UNSAT" if model.Status == gp.GRB.INFEASIBLE else "TIMEOUT"
            return _result(status,t0,t1,t2,n*n,count,solution,setup_time=t0-start)


def solve_cplex_mip(n, time_limit=30, seed=1):
    import cplex
    t0 = time.perf_counter()
    with cplex.Cplex() as model:
        model.set_log_stream(None)
        model.set_results_stream(None)
        model.set_warning_stream(None)
        model.variables.add(types="B"*(n*n))
        count = 0
        for kind,literals in groups(n):
            model.linear_constraints.add(
                lin_expr=[cplex.SparsePair(ind=[v-1 for v in literals],val=[1.0]*len(literals))],
                senses="E" if kind in ("row","column") else "L",rhs=[1.0])
            count += 1
        model.parameters.threads.set(1)
        model.parameters.randomseed.set(seed)
        model.parameters.timelimit.set(time_limit)
        t1 = time.perf_counter()
        model.solve()
        t2 = time.perf_counter()
        found = model.solution.is_primal_feasible()
        code = model.solution.get_status()
        status_codes = model.solution.status
        if found:
            status = "SAT"
            solution = decode(n,(i+1 for i,v in enumerate(model.solution.get_values()) if v > .5))
        elif code in (status_codes.MIP_infeasible,status_codes.infeasible):
            status,solution = "UNSAT",None
        elif code == status_codes.MIP_time_limit_infeasible:
            status,solution = "TIMEOUT",None
        else:
            raise RuntimeError(f"unexpected CPLEX status: {model.solution.get_status_string()}")
        return _result(status,t0,t1,t2,n*n,count,solution)


SOLVERS = dict(cpsat=solve_cpsat,cplex_cp=solve_cplex_cp,
               gurobi=solve_gurobi,cplex_mip=solve_cplex_mip)
