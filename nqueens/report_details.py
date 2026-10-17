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
from .analyze import audit, fmt, latex_table, measured_cell, read_results, update_numbers
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
        if not found:
            raise ValueError(f"No measurements: {exp}, n={n}, {method}")
        return found

    def sat(name, variant="minimal"):
        return f"sat:cadical195:{name}:{variant}"

    max_n = max(ns)
    numbers = {}
    body = []
    for name in ENCODINGS:
        for variant in ("minimal", "extended"):
            values = cell("encodings", max_n, sat(name, variant))
            done = [r for r in values if r["status"] == "SAT"]
            if len(done) == len(values):
                times = [r["process_time"] for r in values]
                build, solve = (median(r[f] for r in values) for f in ("build_time", "solve_time"))
                numbers[f"cost/{name}-{variant}/build"] = fmt(build)
                numbers[f"cost/{name}-{variant}/solve"] = fmt(solve)
                metrics = [fmt(build), fmt(solve),
                           fmt(median(times))]
            else:
                metrics = ["--", "--", f"TO ({len(done)}/{len(values)})"]
            body.append([f"{name}/{variant}"] + metrics)
    latex_table(tables / "encoding_costs.tex",
                ["Encoding / formulation", "Build", "Solve", "Process"], body)

    body = [[f"{name}/{variant}"] + [measured_cell(cell("encodings", n, sat(name, variant)))
                                      for n in ns]
            for variant in ("minimal", "extended") for name in ENCODINGS]
    latex_table(tables / "encodings_by_size.tex",
                ["Encoding / formulation"] + [f"$n={n}$" for n in ns], body)
    for name in ENCODINGS:
        for n in ns:
            numbers[f"size/{name}/{n}/vars"] = f"{sizes[name][n][0]:,}"
            numbers[f"size/{name}/{n}/clauses"] = f"{sizes[name][n][1]:,}"
    update_numbers(report / "numbers.tex", numbers)

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
