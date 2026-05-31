#!/usr/bin/env python3
"""
Seed reshape patch for app/services/seed_attendance_demo.py
Constants-only edits. Lifts baseline to ~97% (green), sharpens Friday dip
(amber), keeps flu week (red), keeps outlier classes, bumps chronic so the
30 chronic learners still clear the 15+ absent-day flag for Card 3.
Each edit anchored on exact unique string + assertion. ast.parse at end.
"""
import ast

PATH = "app/services/seed_attendance_demo.py"

with open(PATH, "r") as f:
    src = f.read()

orig = src

edits = [
    ("BASE_ABSENCE_PROB = 0.07",            "BASE_ABSENCE_PROB = 0.012"),
    ("MONDAY_ADJ = 0.02",                   "MONDAY_ADJ = 0.008"),
    ("FRIDAY_ADJ = 0.015",                  "FRIDAY_ADJ = 0.05"),
    ("FLU_ADJ = 0.09",                      "FLU_ADJ = 0.11"),
    ("GRADE_ADJUSTMENTS = {8: 0.02, 9: 0.01, 10: 0.0, 11: 0.0, 12: -0.01}",
     "GRADE_ADJUSTMENTS = {8: 0.008, 9: 0.005, 10: 0.0, 11: 0.0, 12: -0.002}"),
    ("OUTLIER_ADJ = 0.04",                  "OUTLIER_ADJ = 0.025"),
    ("CHRONIC_ADJ = 0.10",                  "CHRONIC_ADJ = 0.22"),
]

for old, new in edits:
    assert src.count(old) == 1, f"anchor not unique/found: {old!r}"
    src = src.replace(old, new, 1)

# Also refresh the docstring line so it doesn't lie about the baseline.
DOC_OLD = "  1. Baseline ~93% attendance"
DOC_NEW = "  1. Baseline ~97% attendance"
assert src.count(DOC_OLD) == 1, "docstring baseline anchor not found"
src = src.replace(DOC_OLD, DOC_NEW, 1)

assert src != orig, "No changes applied!"
ast.parse(src)

with open(PATH, "w") as f:
    f.write(src)

print("OK: 7 constant edits applied, ast.parse passed.")
for old, new in edits:
    print(f"  {old.split('=')[0].strip():22s} -> {new.split('=',1)[1].strip()}")
print("  docstring baseline       -> ~97%")
