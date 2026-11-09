# ImagineBench agent tasks

Run the benchmark from the repository root with CPython 3.10 or later. The runner uses the Python standard library. It calls no model, engine, network service or GPU.

~~~sh
python -B agent/run.py
python -B agent/run.py --task bench.03 --task bench.25 --output agent-results.json
python -B agent/run.py --unavailable bench.14 --unavailable bench.22
python -B -m unittest discover -s tests -p test_agent.py
~~~

The runner writes JSON to stdout unless given a fresh output filename. It creates a temporary directory for its generated grayscale PNG and removes that directory when the run ends. Pass `--scratch` with an existing writable directory to choose its parent. A failed grader returns process status one. An unavailable surface appears as a skipped trial with its reason.

## What is measured

The catalogue has thirty original task records, their budgets and their original release protocol. Its SHA-256 is `7c49012792b96b71d44b53909343d24334b5cb35bb8a438d1aa39d3e974ed58f`. Each selected ID runs three deterministic repeats. The canned graph, numbers, trace events and candidate answers exercise the graders. On the default adapter, all ninety positive synthetic trials satisfy their contracts. The test suite also exercises one separately sealed wrong outcome for each task.

The report identifies these outcomes as `stub-conformance`. It reports skipped and failed trials separately. The usage fields describe the synthetic trace. Tokens and logical wall time are zero; round trips count stub events. The runner enforces all three original budget limits on the adapter's usage. Model results and the release gate remain unmeasured. Measuring success under the original release protocol requires a pinned model at temperature zero, a real engine adapter, trusted telemetry, three independent trials and a comparable baseline.

## Grader interface

`StubAdapter.execute(task, repeat)` returns a `Trial`. Its `observed` record comes from the host adapter and includes the task and fixture IDs, repeat index, before and after graphs, ordered events, measurement rows, fixture oracle and measured or simulated usage. Its `answer` holds the candidate's output separately. The optional artifacts dictionary maps capture keys to actual local files. `assess(task, trial, expected_repeat)` returns a status and reason. An unavailable adapter can raise `MissingEvidence`. A missing required oracle or observation produces a skip; a wrong outcome or altered capture fails.

A change to the scene must match the approved candidate digest. The host trace records a proposal, a human verdict for the same candidate and an apply in Build mode. Candidate text cannot grant this approval. The synthetic verdict marker and learner-class sentinel contain no human or learner records. The SHA-256 seals detect changes after observation. A third-party adapter must obtain authority and telemetry from its own trusted host; anyone with write access to both observations and their seals can author a new record.

The task-specific predicates live in `graders.py`. They compare scene state, measured values and file contents with the catalogue criteria. A few synthetic-fixture conventions matter when replacing the adapter:

- Graph names such as `Crate_03` identify records in the stub snapshot. Object paths, frame timings, constraints and proposal rankings come from the adapter's own fixture. The supplied geometry, reference images and model responses are outside this lane.
- The lantern test measures distance from the crate's top centre in a Y-up frame. The wall test permits a thickness change about its centre or either fixed surface and checks the other bounds. Image graders receive the fixture's Lab statistics or mask counts. The capture task generates a real PNG to test file presence and dimensions.
- The frame-ranking oracle sorts finite durations in descending order and resolves ties by frame ID. The timing-proposal oracle uses a common baseline and ascending measured frame time. The material-zoo check requires a comparator event, qualifying measurement rows and their IDs in the candidate's report.
- The classroom test observes a rejected mixed export and a successful export of the same admissible members after removing the synthetic learner item. A successful trace containing an unknown or learner class fails even if the answer says the export was safe.
- The onboarding test compares the exact ordered fixture checklist and the sixty-minute duration. The stub supplies a synthetic checklist for role manifest, track context and a seeded card. A real run must supply its independently declared checklist.
