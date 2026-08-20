# Formal Q4 refresh request

This marker records the first formal recomputation after correcting the Q4 interpretation.

The CI refresh job must use:

- the committed formal Q3 trajectory `05_results/q3/trajectory_10hz.csv`;
- official `00_problem/attachments/附件4.xlsx`;
- official `00_problem/attachments/result.xlsx`;
- no artificial nine-task capacity;
- no cross-task preparation-time mutex;
- target coverage -> photo count -> total safety margin lexicographic MILP;
- 0.01 s continuous preparation-window verification;
- regenerated Q4 figures, validation report and result workbook.

The generated artifacts are committed back by `github-actions[bot]` only after the formal result-chain audit and LaTeX asset generation both pass.
