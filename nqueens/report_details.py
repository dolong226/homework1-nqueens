"""Generate additional report evidence from the archived measurements.

No benchmark is executed and no raw result or collection fingerprint is changed.
The counting recurrences are derived separately from the clause generators.
"""
import argparse
from functools import cache
from math import comb, isqrt
from pathlib import Path
from statistics import median

from .amo import ENCODINGS
from .analyze import audit, latex_table, measured_cell, read_results
from .sat_model import clauses


@cache
def amo_size(name, k):
    if k <= 1:
        return 0, 0
    if name == "pairwise" or (name in ("commander", "product") and k <= 4):
        return 0, comb(k, 2)
    if name in ("binary", "seqcounter") and k == 2:
        return 0, 1
    if name == "binary":
        bits = (k - 1).bit_length()
        return bits, k * bits
    if name == "seqcounter":
        return k - 1, 3 * k - 4
    if name == "commander":
        groups = (k + 2) // 3
        aux, count = amo_size(name, groups)
        full, tail = divmod(k, 3)
        return groups + aux, full * 3 + comb(tail, 2) + k + groups + count
    if name == "product":
        p = isqrt(k - 1) + 1
        q = (k + p - 1) // p
        a_p, c_p = amo_size(name, p)
        a_q, c_q = amo_size(name, q)
        return p + q + a_p + a_q, 2 * k + c_p + c_q
    raise ValueError(name)


def board_size(name, n, variant="minimal"):
    if n == 1:
        return 1, 1 if variant == "minimal" else 2
    a_n, c_n = amo_size(name, n)
    aux = (2 * n + 2) * a_n + 4 * sum(amo_size(name, k)[0] for k in range(2, n))
    count = n + (2 * n + 2) * c_n + 4 * sum(amo_size(name, k)[1] for k in range(2, n))
    return n * n + aux, count + (n if variant == "extended" else 0)


def checked_sizes(ns):
    sizes = {}
    for name, encode in ENCODINGS.items():
        for k in range(129):
            formula, top = encode(list(range(1, k + 1)), k)
            if (top - k, len(formula)) != amo_size(name, k):
                raise ValueError(f"AMO recurrence disagrees with encoder: {name}, k={k}")
        sizes[name] = {}
        for n in sorted(set([1, 2, 3, 4] + ns)):
            count, top = 0, n * n
            for clause, top in clauses(n, name, "minimal"):
                count += 1
            if (top, count) != board_size(name, n):
                raise ValueError(f"Board recurrence disagrees with encoder: {name}, n={n}")
            if n in ns:
                sizes[name][n] = (top, count)
    return sizes


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results", default="results")
    parser.add_argument("--report", default="report")
    args = parser.parse_args()
    rows = read_results(args.results)
    audit_result = audit(args.results, rows)
    report = Path(args.report)
    tables, figures = report / "tables", report / "figs"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    enc = [r for r in rows if r["experiment"] == "encodings"]
    ns = sorted({r["n"] for r in enc})
    sizes = checked_sizes(ns)

    def cell(exp, n, method):
        found = [r for r in rows if r["experiment"] == exp and r["n"] == n
                 and r["method"] == method]
        if len(found) != 3:
            raise ValueError(f"Expected three repetitions: {exp}, n={n}, {method}")
        return found

    def complete(exp, n, method):
        found = cell(exp, n, method)
        if any(r["status"] != "SAT" for r in found):
            raise ValueError(f"Cannot summarize an incomplete cell: {exp}, n={n}, {method}")
        return found

    def med(exp, n, method, field):
        return median(r[field] for r in complete(exp, n, method))

    def sat(name, variant="minimal"):
        return f"sat:cadical195:{name}:{variant}"

    body = []
    for name in ENCODINGS:
        for variant in ("minimal", "extended"):
            values = cell("encodings", 128, sat(name, variant))
            solved = sum(r["status"] == "SAT" for r in values)
            if solved == len(values):
                times = [r["process_time"] for r in values]
                metrics = [f"{median(r[f] for r in values):.3f}" for f in
                           ("build_time", "solve_time")]
                metrics.append(f"{median(times):.3f} [{min(times):.3f}, {max(times):.3f}]")
            else:
                metrics = ["--", "--", f"TO ({solved}/3)"]
            body.append([f"{name}/{variant}"] + metrics)
    latex_table(tables / "encoding_costs.tex",
                ["Encoding / formulation", "Build", "Solve", "Process [min, max]"], body)

    body = [[f"{name}/{variant}"] + [measured_cell(cell("encodings", n, sat(name, variant)))
                                      for n in ns]
            for variant in ("minimal", "extended") for name in ENCODINGS]
    latex_table(tables / "encodings_by_size.tex",
                ["Encoding / formulation"] + [f"$n={n}$" for n in ns], body)

    pair_build = med("encodings", 128, sat("pairwise"), "build_time")
    cmd_build = med("encodings", 128, sat("commander"), "build_time")
    product_time = med("encodings", 128, sat("product", "extended"), "process_time")
    seq_time = med("encodings", 128, sat("seqcounter", "extended"), "process_time")
    text = r"""\paragraph{Construction cost and repeated-run variation.}
Table~\ref{tab:encoding-costs} separates construction and search at $n=128$.
Build time includes generating clauses and inserting them into the SAT
solver; solve time measures the solver call. The process column gives a
median and observed minimum--maximum range across the three repetitions.
Each timing column is summarized separately, so its medians need not add
up. A range from three repeats is descriptive, not a confidence interval.
\begin{table}[pos=htbp]
\centering\small
\caption{Encoding-study times at $n=128$, in seconds. Completed cells
contain three valid solutions. No component times are imputed for timeouts.}
\label{tab:encoding-costs}\input{tables/encoding_costs}
\end{table}
\FloatBarrier
"""
    text += (f"For pairwise/minimal, the median construction time is {pair_build:.3f} s, "
             f"compared with {cmd_build:.3f} s for commander/minimal. "
             f"The ratio is approximately {pair_build/cmd_build:.1f} on this implementation. "
             "This connects the clause-count reduction to an observed construction "
             "saving. It does not determine search performance: product/extended "
             "has fewer clauses than commander/minimal but a longer solver call.\n\n")
    text += (r"\paragraph{Effect of redundant column clauses.}" + "\n"
             "At $n=128$, product/minimal and seqcounter/minimal each finish "
             "zero of three runs, while their extended versions finish all three "
             f"with median process times {product_time:.3f} s and {seq_time:.3f} s. "
             "In each case, extended adds only 128 column ALO clauses and no "
             "variables. These explicit column disjunctions make the column "
             "occupancy requirement directly available to unit propagation; "
             "in minimal it follows from the combined row and column constraints. "
             "The measured improvement is consistent with a change in propagation "
             "or search, but timings alone do not isolate which internal events "
             "caused it. Commander receives the same additional clauses without "
             "a comparable improvement. The benefit is therefore conditional on "
             "the encoding, not a universal advantage of adding redundant clauses.\n")
    (report / "encoding_discussion.tex").write_text(text, encoding="utf-8")

    ca = complete("solvers", 32, sat("commander"))
    gl = complete("solvers", 32, "sat:glucose42:commander:minimal")
    ca_times, gl_times = ([r["process_time"] for r in values] for values in (ca, gl))
    text = (f"At $n=32$, CaDiCaL's median process time is {median(ca_times):.3f} s "
            f"with range [{min(ca_times):.3f}, {max(ca_times):.3f}], whereas Glucose "
            f"records {median(gl_times):.3f} s with range "
            f"[{min(gl_times):.3f}, {max(gl_times):.3f}]. "
            "The difference exceeds the observed timing spread, although three "
            "repetitions do not establish a statistical ranking. At $n=96$, "
            "MiniSat is faster than CaDiCaL in the median table, while CaDiCaL "
            "is faster at $n=128$. The aggregate winner need not win at every size.\n\n"
            "Because the formula is fixed, these differences cannot be explained "
            "by choosing a different AMO construction for each backend. The saved "
            "SAT records include aggregate search counters, but no controlled "
            "ablation of branching or learned-clause policies was conducted. "
            "The report therefore does not assign the runtime differences to a "
            "specific solver heuristic.\n")
    (report / "solver_discussion.tex").write_text(text, encoding="utf-8")

    text = ("The choice of timing metric changes the small-board interpretation. "
            "At $n=8$, reference SAT has median process time "
            f"{med('exact',8,sat('commander'),'process_time'):.3f} s, compared with "
            f"{med('exact',8,'cplex_cp','process_time'):.3f} s for CPLEX CP. "
            "Their construction-plus-solve medians are only "
            f"{med('exact',8,sat('commander'),'total_time'):.3f} s and "
            f"{med('exact',8,'cplex_cp','total_time'):.3f} s. "
            "Much of the end-to-end difference at this size lies outside the "
            "measured core interval. Process time remains the primary metric "
            "because the deadline includes those startup costs.\n\n"
            "At $n=512$, CPLEX CP, CPLEX MIP, and Gurobi have median core times "
            f"{med('scaling',512,'cplex_cp','total_time'):.3f}, "
            f"{med('scaling',512,'cplex_mip','total_time'):.3f}, and "
            f"{med('scaling',512,'gurobi','total_time'):.3f} s, respectively. "
            "CPLEX CP is fastest for this core metric and also for process time "
            "at this particular size, whereas Gurobi has the lowest aggregate "
            "PAR-2 across the eight sizes. These are two different observations. "
            "The small CP input model alone is insufficient to prove why its "
            "engine performs well; solver preprocessing and search were not "
            "isolated experimentally.\n")
    (report / "exact_discussion.tex").write_text(text, encoding="utf-8")

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.rcParams.update({"font.size": 10, "axes.spines.top": False,
                         "axes.spines.right": False, "figure.dpi": 180})
    fig, axes = plt.subplots(1, 2, figsize=(8.8, 3.5))
    names = {"pairwise": "Pairwise", "binary": "Binary", "commander": "Commander",
             "product": "Recursive product", "seqcounter": "Sequential"}
    for name in ENCODINGS:
        for i, ax in enumerate(axes):
            ax.plot(ns, [sizes[name][n][i] for n in ns], marker="o", markersize=3,
                    label=names[name])
    for i, ax in enumerate(axes):
        ax.set(xlabel="Board side n", ylabel=["Total variables", "Generated clauses"][i],
               xscale="log", yscale="log")
        ax.set_xticks(ns, [str(n) for n in ns])
        ax.minorticks_off()
        ax.grid(alpha=.2)
        ax.legend(fontsize=7)
    fig.tight_layout()
    fig.savefig(figures / "formula_sizes.png")
    plt.close(fig)
    print(f"Report details generated; audited {audit_result['runs']} existing runs; "
          "checked AMO counts k=0..128 and board counts at study sizes and n=1..4.")


if __name__ == "__main__":
    main()
