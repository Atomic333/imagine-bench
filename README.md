# Imagine Bench v0

A portable renderer-parity replay harness and thirty agent-task definitions with deterministic stub-adapter grading. It contains benchmark tools and data, **no engine implementation and no learner data**.

## Status

The parity dataset preserves one historical B01 measurement revision. Replaying those captures measures image agreement; it does not run the original engine. Full-GI reference images and direct-light diagnostics are separate workloads. Stub conformance is not a model/agent success score or a production-engine result. An independently documented run by someone outside the project remains required for T07 acceptance.

## Run

See [parity instructions](parity/README.md) and [agent instructions](agent/README.md) for exact commands, dependencies, adapter and grader contracts. Run from a clean checkout; results belong outside the tracked inputs. No API key, hosted service or model call is required.

## Versioned workloads and reporting

Run `python -B verify_release.py` on a clean checkout before creating local outputs. The release inventory in manifest.json freezes every input by SHA-256. Do not replace reference images, seed/task data, masks or compiler/tool pins under the same workload version. Any changed input creates a new version with explicit lineage. Report camera/reference/mask mode, capture and reference hashes, comparator revision, platform/dependencies, measured failures and skipped tasks. Never silently drop unavailable tasks from a reported score.

Three temperature-zero repeats with a named immutable model and all budget measurements are required for a future N09 model result. This release makes no such result. Human approval and privacy tasks must be graded from explicit recorded verdicts, not inferred from an image.

## Results

See the [results dashboard](RESULTS.md). The parity directory documents the retained historical results. Stub runs report only deterministic grader/adapter conformance. No cross-engine leaderboard or claim of superiority is established. To document an external reproduction, record the repository commit, manifest hash, command, environment and complete output, including misses/skips.

## Licences

Code: [MIT](LICENSE). New data and compilation: [CC-BY-4.0](LICENSE-DATA.md). Existing procedural fixture/reference data retain CC0-1.0. Attribution and per-file boundaries are in [NOTICES.md](NOTICES.md) and manifest.json.
