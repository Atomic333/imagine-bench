# Results dashboard — v0.1.0

| Workload | Recorded result | Qualification |
| --- | --- | --- |
| B01 retained direct cam_A | Mean ΔE00 1.577; p95 5.612 | Historical captured image replay; not a new engine render |
| B01 retained direct cam_B | Mean ΔE00 0.986; p95 3.904 | Same pinned scene/comparator revision |
| B01 retained direct cam_C | Mean ΔE00 1.036; p95 3.930 | Same pinned scene/comparator revision |
| All lighting-isolation captures | 18 cases with per-material mask rows | Reproduce with parity/reproduce.py; report every case |
| Reference self controls | Three camera means zero | Comparator conformance only |
| Black-image negative | Exceeds the direct-workshop threshold | Expected rejection, not a renderer score |
| N09 stub | 30 tasks × 3 deterministic repeats | Synthetic grader/adapter conformance only |
| N09 model success | Unmeasured | No model/agent execution or benchmark superiority claim |
| Outside-party reproduction | Pending | Project agents and creator do not satisfy this criterion |

Full references are retained separately from the direct-light workloads. These historical direct results do not establish full global-illumination acceptance. Source authoring .blend is omitted because saved state retained private host paths; portable USD/texture/reference/capture inputs support metric replay, not rebuilding the original Blender authoring session.
