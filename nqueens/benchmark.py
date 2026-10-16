"""Reproduce the four sequential experiments without resource contention.

Use ``--results`` to write a fresh run elsewhere; the archived ``results``
directory only resumes runs recorded with an identical configuration.
"""
import argparse
import sys
from .experiment import main


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--results",default="results")
    results = parser.parse_args().results
    for experiment in ("encodings","solvers","exact","scaling"):
        sizes = [256,512] if experiment == "scaling" else [8,16,32,64,96,128]
        sys.argv = [sys.argv[0],experiment,"--sizes",*map(str,sizes),"--repeats","3",
                    "--time-limit","10","--results",results]
        main()
