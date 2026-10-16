"""Check input consequences with unit propagation only, without SAT search."""
import unittest

from nqueens.amo import ENCODINGS


def unit_closure(clauses, initial):
    """Return forced literals, or None on a conflict, using only the unit rule."""
    assigned = set(initial)
    if any(-literal in assigned for literal in assigned):
        return None
    while True:
        changed = False
        for clause in clauses:
            if any(literal in assigned for literal in clause):
                continue
            remaining = [literal for literal in clause if -literal not in assigned]
            if not remaining:
                return None
            if len(remaining) == 1 and remaining[0] not in assigned:
                assigned.add(remaining[0])
                changed = True
        if not changed:
            return assigned


class PropagationTests(unittest.TestCase):
    def test_selected_input_excludes_all_others(self):
        for name, encoder in ENCODINGS.items():
            for k in range(1, 65):
                for polarity in (1, -1):
                    inputs = [polarity * i for i in range(1, k + 1)]
                    formula, _ = encoder(inputs, k)
                    for selected in inputs:
                        with self.subTest(encoding=name, k=k, selected=selected):
                            forced = unit_closure(formula, [selected])
                            self.assertIsNotNone(forced)
                            self.assertTrue(all(-other in forced for other in inputs
                                                if other != selected))


if __name__ == "__main__":
    unittest.main()
