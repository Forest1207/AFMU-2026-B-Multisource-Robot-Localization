# Formal Q4 refresh request

This marker records the final formal recomputation after aligning the branch with the reference-package Q4 structure.

The CI refresh job must use:

- committed formal Q3 trajectory `05_results/q3/trajectory_10hz.csv`;
- official `00_problem/attachments/附件4.xlsx`;
- official `00_problem/attachments/result.xlsx`;
- no artificial nine-task capacity;
- no cross-task preparation-time mutex;
- target coverage -> photo count -> total safety margin lexicographic MILP;
- shooting segment endpoint / maximum-margin candidate compression;
- photography **5-degree bearing-bin** candidate compression plus feasible-segment endpoints;
- 0.01 s full preparation-window verification for all compressed candidates;
- post-MILP bounded continuous refinement within **±0.1 s** for every selected task;
- preservation of >=60-degree same-target photography separation after refinement;
- two-decimal final execution times followed by another 0.01 s full-window verification;
- regenerated Q4 PNG/SVG/PDF figures, validation report and expanded result workbook.

The generated artifacts may be committed back by `github-actions[bot]` only after:

1. all Q1--Q4 synthetic regression tests pass;
2. official input SHA/sheet/row/column audit passes;
3. formal Q4 validation passes;
4. cross-problem `scripts/audit_results.py` passes;
5. `scripts/generate_latex_assets.py` accepts the fresh Q4 schema.
