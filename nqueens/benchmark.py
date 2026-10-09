"""Reproduce the four sequential experiments without resource contention."""
import sys
from .experiment import main


if __name__ == "__main__":
    for experiment in ("encodings","solvers","exact","scaling"):
        sizes = [256,512] if experiment == "scaling" else [8,16,32,64,96,128]
        sys.argv = [sys.argv[0],experiment,"--sizes",*map(str,sizes),"--repeats","3","--time-limit","10"]
        main()
