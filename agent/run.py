"""Offline reference runner for the ImagineBench v0 N09 task catalogue."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics
import tempfile

from graders import MissingEvidence, authority, evaluate, fingerprint, numeric
from stub import StubAdapter


CATALOGUE = Path(__file__).with_name("agent-bench.json")
CATALOGUE_SHA256 = "7c49012792b96b71d44b53909343d24334b5cb35bb8a438d1aa39d3e974ed58f"


def catalogue():
    raw = CATALOGUE.read_bytes()
    if hashlib.sha256(raw).hexdigest() != CATALOGUE_SHA256:
        raise ValueError("task catalogue differs from the published bytes")
    return json.loads(raw)


def assess(task, trial, expected_repeat=None):
    o = trial.observed
    result = {"task":task["id"],"repeat":o.get("repeat"),"status":"failed"}
    try:
        if trial.evidence_hash != fingerprint(o):
            raise ValueError("adapter measurement or observation changed after capture")
        if expected_repeat is not None and o.get("repeat") != expected_repeat:
            raise ValueError("adapter returned a different repeat")
        if o["task"] != task["id"] or o["fixture"] != task["setup"]:
            raise ValueError("evidence belongs to a different task or fixture")
        if set(trial.artifacts) != set(o["artifactHashes"]):
            raise ValueError("capture artifact membership changed")
        for key, path in trial.artifacts.items():
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != o["artifactHashes"][key]:
                raise ValueError("capture artifact missing or changed")
        for field,limit in task["budget"].items():
            val = o["usage"][field]
            if field in ("tokens","round_trips") and type(val) is not int:
                raise ValueError("invalid usage count for "+field)
            if not 0 <= numeric(val) <= limit:
                raise ValueError("exceeded original budget: "+field)
        # Candidate text never supplies verdicts, telemetry, execution order or permissions.
        authority(task,o)
        if not evaluate(task,o,trial.answer,trial.artifacts):
            raise ValueError("observed evidence or answer did not satisfy the task grader")
        result.update(status="passed",reason="stub observations satisfy the original task grader")
    except (KeyError, MissingEvidence) as error:
        result.update(status="skipped",reason="required adapter evidence unavailable: "+str(error))
    except (ValueError, TypeError, IndexError, ArithmeticError) as error:
        result["reason"]=str(error)
    return result


def run_suite(tasks, adapter):
    spec = catalogue()["run"]
    rows, usage = [], []
    for task in tasks:
        for repeat in range(spec["repeats"]):
            try:
                trial = adapter.execute(task,repeat)
                row = assess(task,trial,repeat)
                if row["status"]=="passed":
                    usage.append(trial.observed["usage"])
            except MissingEvidence as error:
                row = {"task":task["id"],"repeat":repeat,"status":"skipped","reason":str(error)}
            rows.append(row)
    c = Counter(row["status"] for row in rows)
    return {"format":"imaginebench-agent-report/1","mode":"stub-conformance","catalogueSha256":CATALOGUE_SHA256,
            "tasks":len(tasks),"attempts":len(rows),"protocol":spec,
            "conformance":{k:c[k] for k in ("passed","failed","skipped")},
            "stubUsageMedian":{k:statistics.median(v[k] for v in usage) if usage else None
                               for k in ("tokens","round_trips","wall_s")},
            "modelBenchmark":{"model":None,"modelRuns":0,"success_pct":None,"tokens_per_task_median":None,
                              "round_trips_median":None,"wall_s_median":None,"releaseGate":"unmeasured"},
            "results":rows}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--task",action="append",help="Run a task ID (repeat for multiple tasks)")
    parser.add_argument("--unavailable",action="append",default=[],help="Simulate a missing adapter surface by task ID")
    parser.add_argument("--output",type=Path,help="Write a fresh JSON report instead of stdout")
    parser.add_argument("--scratch",type=Path,help="Existing writable directory for a temporary generated PNG")
    args=parser.parse_args()
    tasks=catalogue()["tasks"]
    ids={t["id"] for t in tasks}
    unknown=(set(args.task or [])|set(args.unavailable))-ids
    if unknown:
        parser.error("unknown task IDs: "+", ".join(sorted(unknown)))
    with tempfile.TemporaryDirectory(dir=args.scratch) as scratch:
        stub=StubAdapter(scratch)
        stub.unavailable.update(args.unavailable)
        report=run_suite([t for t in tasks if args.task is None or t["id"] in args.task],stub)
    text=json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+"\n"
    if args.output:
        with args.output.open("x",encoding="utf-8",newline="\n") as stream:
            stream.write(text)
    else:
        print(text,end="")
    return 1 if report["conformance"]["failed"] else 0


if __name__=="__main__":
    raise SystemExit(main())
