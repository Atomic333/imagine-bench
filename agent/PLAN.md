# Agent benchmark implementation plan

1. Retain the original task catalogue bytes, task identifiers, grader text, per-task budgets and three-repeat protocol.
2. Implement independent graders over a host adapter's before/after graph, measurement rows, evidence log, captures and candidate answer. Check numeric thresholds, graph relationships, mode restrictions, approval order and export outcomes at the task boundary.
3. Supply a deterministic, offline stub with synthetic fixtures for the thirty task contracts. Missing surfaces or missing oracle evidence produce explicit skips. Results identify the synthetic scope and keep model success and release gates unmeasured.
4. Exercise each grader with positive and negative evidence, including altered measurements, a missing human verdict, and a learner-class export. Run from the staged tree with Python's standard library and record reproducible commands.
