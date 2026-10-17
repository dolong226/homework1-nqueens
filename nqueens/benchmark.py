"""Reproduce the four sequential experiments without resource contention.

Use ``--results`` to write a fresh run elsewhere; the archived ``results``
directory only resumes runs recorded with an identical configuration.
A SHA-256 fingerprint of the source used is stored with the results.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys
from .experiment import main

ROOT = Path(__file__).resolve().parents[1]
MAIN_SIZES = [8,16,32,64,128,256]
SCALING_SIZES = [512,1024]


MEASUREMENT_CODE = ["amo","board","sat_model","exact_models","run_one","experiment","benchmark"]


def fingerprint(results):
    """Hash the code that produces measurements; analysis scripts are excluded."""
    files = [ROOT/"nqueens"/f"{name}.py" for name in MEASUREMENT_CODE]
    digest = {str(p.relative_to(ROOT)).replace("\\","/"):
              hashlib.sha256(p.read_bytes().replace(b"\r\n",b"\n")).hexdigest() for p in files}
    Path(results).mkdir(parents=True,exist_ok=True)
    (Path(results)/"source-sha256.json").write_text(json.dumps(
        dict(normalization="UTF-8 with LF line endings",files=digest),indent=2),encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results",default="results")
    parser.add_argument("--time-limit",default="600")
    parser.add_argument("--repeats",default="3")
    parser.add_argument("--experiments",nargs="+",default=["encodings","solvers","exact","scaling"])
    args = parser.parse_args()
    fingerprint(args.results)
    for experiment in args.experiments:
        sizes = SCALING_SIZES if experiment == "scaling" else MAIN_SIZES
        sys.argv = [sys.argv[0],experiment,"--sizes",*map(str,sizes),"--repeats",args.repeats,
                    "--time-limit",args.time_limit,"--results",args.results]
        main()
