"""Audit raw solutions and generate report tables/figures from measured data."""
import argparse
from collections import defaultdict,Counter
import csv
import json
from pathlib import Path
from statistics import mean,median
from .board import check_solution
from .sat_model import clauses


def read_results(directory):
    rows = []
    for path in sorted(Path(directory).glob("*.csv")):
        with path.open(newline="",encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                row["experiment"] = path.stem
                for key in ("n","repeat","seed"):
                    row[key] = int(row[key])
                for key in ("budget","process_time","build_time","solve_time","total_time"):
                    row[key] = float(row[key]) if row[key] else None
                rows.append(row)
    return rows


def audit(directory,rows):
    checked = 0
    raw = {}
    for path in sorted(Path(directory).glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            result = json.loads(line)
            key = (path.stem,result["n"],result["method"],result["repeat"])
            if key in raw:
                raise ValueError(f"duplicate raw result: {key}")
            raw[key] = result
            if result["status"] == "SAT":
                if not check_solution(result["n"],result["solution"]):
                    raise ValueError(f"invalid solution: {key}")
                checked += 1
            elif result["status"] == "UNSAT" and result["n"] not in (2,3):
                raise ValueError(f"unexpected UNSAT on ordinary N-queens: {key}")
    seen = set()
    for row in rows:
        key = (row["experiment"],row["n"],row["method"],row["repeat"])
        if key in seen or key not in raw or raw[key]["status"] != row["status"]:
            raise ValueError(f"CSV/raw mismatch: {key}")
        seen.add(key)
    if seen != set(raw):
        raise ValueError("CSV/raw record counts differ")
    for path in Path(directory).glob("*.config.json"):
        config = json.loads(path.read_text())
        expected = {(config["experiment"],n,m,r) for n in config["sizes"]
                    for m in config["methods"] for r in range(1,config["repeats"]+1)}
        actual = {key for key in seen if key[0] == config["experiment"]}
        if actual != expected:
            raise ValueError(f"incomplete experiment: {path.stem}")
    return dict(runs=len(rows),checked_solutions=checked,statuses=dict(Counter(r["status"] for r in rows)))


def par2(rows):
    return mean(row["process_time"] if row["status"] in ("SAT","UNSAT") else 2*row["budget"] for row in rows)


def label(method):
    if method.startswith("sat:"):
        _,solver,amo,variant = method.split(":")
        return f"{amo}/{variant}"
    return {"cplex_cp":"CPLEX CP","cplex_mip":"CPLEX MIP","gurobi":"Gurobi","cpsat":"CP-SAT"}[method]


def latex_table(path,headers,body,alignment=None):
    alignment = alignment or "l"+"r"*(len(headers)-1)
    lines = [r"\begin{tabular}{"+alignment+"}",r"\toprule"," & ".join(headers)+r" \\",r"\midrule"]
    lines += [" & ".join(map(str,row))+r" \\" for row in body]
    lines += [r"\bottomrule",r"\end{tabular}"]
    path.write_text("\n".join(lines)+"\n",encoding="utf-8")


def measured_cell(rows,field="process_time"):
    solved = [r for r in rows if r["status"] in ("SAT","UNSAT")]
    if len(solved) != len(rows):
        return f"TO ({len(solved)}/{len(rows)})"
    return f"{median(r[field] for r in solved):.3f}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results",default="results")
    parser.add_argument("--report",default="report")
    args = parser.parse_args()
    rows = read_results(args.results)
    audit_result = audit(args.results,rows)
    report = Path(args.report)
    tables,figures = report/"tables",report/"figs"
    tables.mkdir(parents=True,exist_ok=True)
    figures.mkdir(parents=True,exist_ok=True)
    groups = defaultdict(list)
    for row in rows:
        groups[(row["experiment"],row["method"])].append(row)
    encodings = {method:values for (exp,method),values in groups.items() if exp == "encodings"}
    ranking = sorted(encodings,key=lambda m:par2(encodings[m]))
    body,sizes = [],{}
    max_n = max(r["n"] for r in rows if r["experiment"] == "encodings")
    for method in ranking:
        values = encodings[method]
        _,_,amo,variant = method.split(":")
        top,count = max_n*max_n,0
        for clause,top in clauses(max_n,amo,variant):
            count += 1
        sizes[method] = dict(n_vars=top,n_constraints=count)
        body.append([label(method),f"{sum(r['status']=='SAT' for r in values)}/{len(values)}",
                     f"{par2(values):.3f}",f"{top:,}",f"{count:,}"])
    latex_table(tables/"encodings.tex",["Encoding / formulation","Solved","PAR-2 (s)","Variables","Clauses"],body)
    exact = [r for r in rows if r["experiment"] in ("exact","scaling")]
    methods = list(dict.fromkeys(r["method"] for r in exact))
    exact_sizes = sorted({r["n"] for r in exact})
    body = []
    for n in exact_sizes:
        body.append([n]+[measured_cell([r for r in exact if r["n"] == n and r["method"] == m]) for m in methods])
    latex_table(tables/"exact.tex",["$n$"]+["SAT" if m.startswith("sat:") else label(m) for m in methods],body)
    body = []
    for n in exact_sizes:
        cell = [r for r in exact if r["n"] == n]
        body.append([n]+[measured_cell([r for r in cell if r["method"] == m],"total_time") for m in methods])
    latex_table(tables/"exact_core.tex",["$n$"]+["SAT" if m.startswith("sat:") else label(m) for m in methods],body)
    sat_methods = [m for (exp,m) in groups if exp == "solvers"]
    body = []
    for n in sorted({r["n"] for r in rows if r["experiment"] == "solvers"}):
        body.append([n]+[measured_cell([r for r in groups[("solvers",m)] if r["n"] == n]) for m in sat_methods])
    latex_table(tables/"solvers.tex",["$n$"]+[m.split(":")[1] for m in sat_methods],body)
    summary = audit_result | dict(encoding_ranking=[dict(method=m,par2=par2(encodings[m])) for m in ranking],
        encoding_sizes=sizes,exact={m:dict(solved=sum(r["status"]=="SAT" for r in exact if r["method"]==m),
            runs=sum(r["method"]==m for r in exact),par2=par2([r for r in exact if r["method"]==m])) for m in methods})
    (Path(args.results)/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    winner = ranking[0]
    best_values = encodings[winner]
    best_name = label(winner)
    pairwise = sizes["sat:cadical195:pairwise:minimal"]["n_constraints"]
    best_clauses = sizes[winner]["n_constraints"]
    text = (f"The lowest aggregate PAR-2 is obtained by {best_name}, "
            f"at {par2(best_values):.3f} seconds, with "
            f"{sum(r['status']=='SAT' for r in best_values)} of {len(best_values)} runs solved. "
            f"At $n={max_n}$, pairwise/minimal has {pairwise:,} clauses, "
            f"whereas {best_name} has {best_clauses:,}. "
            "The ranking is measured rather than inferred from clause count alone. "
            "The reference used in the following experiments is commander/minimal; "
            "it was selected after an exploratory encoding comparison on the same size family. "
            "The reported encoding results were then collected with the finalized harness.\n")
    for amo in ("product","seqcounter"):
        minimal = encodings[f"sat:cadical195:{amo}:minimal"]
        extended = encodings[f"sat:cadical195:{amo}:extended"]
        text += (f"For {amo}, the minimal formulation solves "
                 f"{sum(r['status']=='SAT' for r in minimal)}/{len(minimal)} runs "
                 f"with PAR-2 {par2(minimal):.3f} seconds; adding column ALO solves "
                 f"{sum(r['status']=='SAT' for r in extended)}/{len(extended)} "
                 f"with PAR-2 {par2(extended):.3f} seconds. ")
    text += ("Thus the added column clauses can improve measured runtime without "
             "changing the set of placements, although the effect depends on the encoding.\n")
    (report/"encoding_findings.tex").write_text(text,encoding="utf-8")
    sat_rank = sorted(sat_methods,key=lambda m:par2(groups[("solvers",m)]))
    text = "All backends use commander/minimal. Their aggregate PAR-2 values are "
    text += ", ".join(f"{m.split(':')[1]}: {par2(groups[('solvers',m)]):.3f} seconds" for m in sat_rank)
    text += (". These results describe this fixed formula family and short budget; "
             "they do not establish a universal ranking of SAT engines.\n")
    (report/"solver_findings.tex").write_text(text,encoding="utf-8")
    text = "Across the 24 runs per method, "
    text += "; ".join(f"{'SAT' if m.startswith('sat:') else label(m)} solves "
                      f"{summary['exact'][m]['solved']}/{summary['exact'][m]['runs']} "
                      f"with PAR-2 {summary['exact'][m]['par2']:.3f} seconds" for m in methods)
    text += (". Timeout cells in Tables~\\ref{tab:exact} and~\\ref{tab:core} "
             "preserve unsuccessful runs. On small boards, process times include "
             "library and license startup that may exceed actual search time. "
             "On larger boards, representation size and search dominate, so the "
             "compact CP model and binary board model need not scale similarly.\n")
    largest = max(exact_sizes)
    text += f"At $n={largest}$, "
    text += "; ".join(f"{'SAT' if m.startswith('sat:') else label(m)} completes "
                      f"{sum(r['status']=='SAT' for r in exact if r['method']==m and r['n']==largest)}/3 runs"
                      for m in methods)
    text += (f". The CP user model at this size has {largest:,} integer variables "
             f"and three global constraints; the ILP user model has {largest*largest:,} "
             f"binary variables and {6*largest-6:,} linear constraints. "
             "These are input-model counts, not the numbers remaining after presolve.\n")
    (report/"exact_findings.tex").write_text(text,encoding="utf-8")
    text = (f"The final audit covers {audit_result['runs']} timed runs and independently "
            f"revalidates {audit_result['checked_solutions']} returned placements. "
            f"There are {audit_result['statuses'].get('TIMEOUT',0)} timeouts and "
            f"{audit_result['statuses'].get('ERROR',0)} solver errors. "
            "The measured differences support selecting a suitable encoding and "
            "modeling interface for the available budget; they do not imply "
            "that any generic solver replaces specialized N-queens constructions.\n")
    (report/"conclusion_findings.tex").write_text(text,encoding="utf-8")
    # Figures show deadline penalties, rather than omitting failed runs.
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size":10,"axes.spines.top":False,"axes.spines.right":False,"figure.dpi":160})
    fig,ax = plt.subplots(figsize=(7.2,4.2))
    for method in ranking:
        values = encodings[method]
        ns = sorted({r["n"] for r in values})
        ax.plot(ns,[par2([r for r in values if r["n"]==n]) for n in ns],marker="o",ms=3,label=label(method))
    ax.set(xlabel="Board side n",ylabel="PAR-2 process time (s)",yscale="log")
    ax.legend(fontsize=7,ncol=2)
    ax.grid(alpha=.2)
    fig.tight_layout()
    fig.savefig(figures/"encodings.png")
    plt.close(fig)
    fig,axes = plt.subplots(1,2,figsize=(9.0,3.8))
    for method in methods:
        values = [r for r in exact if r["method"]==method]
        axes[0].plot(exact_sizes,[par2([r for r in values if r["n"]==n]) for n in exact_sizes],marker="o",ms=3,
                     label="SAT" if method.startswith("sat:") else label(method))
        times = sorted(r["process_time"] for r in values if r["status"]=="SAT")
        axes[1].step(times,range(1,len(times)+1),where="post",label="SAT" if method.startswith("sat:") else label(method))
    axes[0].set(xlabel="Board side n",ylabel="PAR-2 process time (s)",xscale="log",yscale="log")
    axes[1].set(xlabel="Process time (s)",ylabel="Solved runs (cumulative)")
    for ax in axes:
        ax.grid(alpha=.2)
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(figures/"exact.png")
    plt.close(fig)
    # Visual example comes from a measured solution, not a hand-drawn placement.
    example = next(json.loads(line) for line in (Path(args.results)/"encodings.jsonl").read_text().splitlines()
                   if json.loads(line)["n"]==8 and json.loads(line)["status"]=="SAT")
    fig,ax = plt.subplots(figsize=(3.4,3.4))
    from matplotlib.colors import ListedColormap
    ax.imshow([[(r+c)%2 for c in range(8)] for r in range(8)],cmap=ListedColormap(["#f1f4f7","#9cb2c6"]),vmin=0,vmax=1)
    ax.scatter(example["solution"],range(8),c="#182c42",s=180,marker="o",edgecolors="white",linewidths=1.8)
    ax.set_xticks(range(8),range(1,9))
    ax.set_yticks(range(8),range(1,9))
    ax.set(xlabel="Column",ylabel="Row")
    fig.tight_layout()
    fig.savefig(figures/"board.png")
    plt.close(fig)
    print(json.dumps(audit_result))


if __name__ == "__main__":
    main()
