# Cross-cohort transfer protocol v0.2.0

This workload tests whether accepted, evidence-bearing work reduces a later cohort's cost. It is a preregistered protocol and tool release. No model trial, human participant, transfer benefit or engine-learning result is reported. The original thirty-task catalogue and parity workload remain byte-for-byte unchanged.

## Freeze before running

Hash the model revision, adapter/harness, prompt, grader, task definitions, seeds, store manifest and all store content. Record prior/cohort provenance and consent independently of an agent's answer. Freeze the store before creating the genuinely unseen task cohort. Freeze parameter choices and statistical rules before inspecting outcomes. Hold model, harness, tasks, prompts, budgets and cache policy constant across arms.

The public `split.json` deterministically assigns the thirty original tasks to Seen S (20) and store-held-out U (10), plus five Near task definitions on alternate targets. Published U is not secret or demonstrated model-unseen. A real unseen-transfer claim requires a separate post-store-freeze sealed task manifest and exposure audit. Near definitions require adapter-owned distinct targets and independent ground truth; their fixtures are not implemented by this release. Until those prerequisites exist, tool demonstrations cannot qualify the transfer feature.

Record the complete randomized order before running: for each task and five paired seeds, shuffle all six arms with a fixed protocol seed. Reset to the same declared cold cache policy before every arm. Separate the I03 warm-cook-cache experiment; it is not a confound in this six-arm test. There are 1,050 scheduled attempts, including unsuccessful attempts, for a complete 35-task experiment.

| Arm | Frozen inputs |
| --- | --- |
| A0 | No recipes or prior; cold cache. |
| A1 | Prior-cohort accepted recipes for S only. |
| A2 | Prior-cohort sensitivity prior; no recipes. |
| A3 | The same recipes and prior together. |
| A4 | Same recipe count, retrieval count and declared length unit, from a genuinely unrelated fixture. |
| A5 | A1 text with evidence removed, exposed only as a read-only experimental retrieval view. |

Matching length means whitespace-delimited word count unless a pinned model tokenizer is recorded. This is not a claim of equal model-token count. A placebo generator selects genuine unrelated records with matching lengths and refuses a missing match; it must not invent accepted records or verifier evidence. A5 cannot enter the accepted recipe corpus or execute changes. A supplied hash authenticates bytes, not acceptance, consent, trust or independence of a verdict.

## Privacy and authority

Only project-owned synthetic, fixture, engine, artist or agent records with explicit provenance are permitted in this public workload. Refuse learner-class and unknown-class records recursively, including priors, weights, traces and nested evidence. No training on learner data at any age. This benchmark grants no classroom collection, sharing, model-call or inference consent. A separate human-cohort study requires its own governance and consent; none is run here.

Accepted recipe admission still requires the production authority, human acceptance and runtime evidence defined by N05b. Synthetic records exercise validation only and never certify that those production requirements ran. Core remains the only mutation authority. Candidate text does not supply timings, probes, permissions or verdicts.

## Outcomes and uncertainty

Retain every scheduled attempt, including refusal, failure, timeout and unavailable evidence, with task/split/arm/seed, store hashes and source-authenticated usage/verdict artifacts. Distinguish successful read-only/refusal tasks from mutation tasks eligible for an accepted-proposal endpoint. Predeclare endpoint eligibility and censoring; never give an inapplicable task a fabricated proposal acceptance. Missing, duplicate, substituted or mismatched observations invalidate the requested comparison.

Compute endpoints within each task across its five attempts before sampling. Primary endpoints are probes per accepted proposal and elapsed time to acceptance, with total unsuccessful-attempt cost included under the preregistered censoring rule. No accepted proposal means the acceptance-time endpoint is censored/undefined, not zero and not omitted. Secondary endpoints include task acceptance, invariant refusals, token cost and Seen regressions. Report complete denominators and failure counts.

Use 10,000 paired task-cluster bootstrap resamples within S, U and N, retaining all six arms and five paired replicates together for each sampled task. Record the bootstrap seed and percentile 95% intervals. Repeats are not independent task samples. N has only five tasks: show that limited coverage rather than imply broad generalization.

Preregistered predictions are A3 versus A0 on S: at least 30% fewer probes and 20% less time, with improvement intervals excluding zero; at most one Seen task regression; zero learner-record leakage. Compare A5 with A1 and the Near effect with S/U. For U and A4, absence of a significant difference does not establish equivalence. Supply practical equivalence margins before the run and require the complete confidence intervals within them; otherwise that criterion is undetermined. Report each outcome rather than compress incomplete evidence into a pass.

## Running the tools

The existing `agent/run.py --store ...` option authenticates a frozen store and records its hash. The supplied stub remains a conformance adapter: it does not perform retrieval or model inference and cannot measure a store's benefit. Use `python -B agent/run.py --help`, `python -B agent/placebo.py --help` and `python -B agent/bootstrap.py --help` for exact tool arguments and schemas.

```sh
python -B agent/run.py --store STORE/manifest.json --store-sha256 MANIFEST_SHA256 --store-experiment --output stub.json
python -B agent/placebo.py --reference STORE/manifest.json --reference-sha256 MANIFEST_SHA256 --unrelated UNRELATED/manifest.json --unrelated-sha256 UNRELATED_SHA256 --unrelated-fixture FIXTURE_ID --output NEW_PLACEBO_DIRECTORY
python -B agent/bootstrap.py TRIALS.jsonl --seed 20261109 --output analysis.json
```

Use fresh output files/directories. Store manifests have format `imaginebench-transfer-store/1`, `experimentOnly: true`, `dataClass: synthetic` or `recorded`, declared nonlearner provenance, `seenTaskIds` and content-hashed JSON `files`. `agent/store.py` defines the strict record schema; the store tests build valid examples. Recorded classification is a producer declaration, not authenticated acceptance. The analyzer's exact row fields are documented in [the trial schema](../docs/transfer-result-schema.json). A reported complete matrix shape is not verified task identity: current analysis explicitly leaves task identity unverified and qualification null.

The analyzer consumes transfer trial records, not the legacy stub's success-only usage median. Synthetic output, incomplete grids, public-holdout-only tasks, missing equivalence margins or unavailable endpoint evidence cannot produce a qualified transfer verdict. Real adapter trials need independently authenticated runtime artifacts. No API calls are made by these tools.

## Publication and feature acceptance

T07 publishes this protocol with the benchmark harness under the existing MIT code / CC-BY-4.0 new-data grants; procedural fixture data retain CC0. N05b and I02 add the transfer outcomes to their original acceptance requirements, preserving dependencies, budgets, privacy and gates. A protocol release or passing synthetic tests does not complete N05b, I02, N09 or T07's independent external reproduction requirement.

The seed v0.1.0 release remains in Git history. Every updated file and new protocol input receives a v0.2.0 manifest hash. Future measured results must report the exact published commit, manifest and store hashes, all missed targets and unavailable evidence.
