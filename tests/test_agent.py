"""Offline public agent bench checks. All observed operations are synthetic."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "agent"))
from run import catalogue, assess, run_suite
from stub import StubAdapter
from graders import fingerprint


class AgentBenchmark(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.addCleanup(self.scratch.cleanup)
        self.adapter = StubAdapter(Path(self.scratch.name))
        self.tasks = catalogue()["tasks"]

    def test_protocol_and_deterministic_results(self):
        a = run_suite(self.tasks, self.adapter)
        self.assertEqual(a, run_suite(self.tasks, self.adapter))
        self.assertEqual((a["conformance"]["passed"], a["attempts"]), (90, 90))
        self.assertIsNone(a["modelBenchmark"]["success_pct"])
        self.assertEqual(a["mode"], "stub-conformance")

    def test_unavailable_is_skipped(self):
        self.adapter.unavailable.add("bench.14")
        result = run_suite(self.tasks, self.adapter)
        self.assertEqual(result["conformance"]["skipped"], 3)
        self.assertTrue(all(row["reason"] for row in result["results"] if row["status"]=="skipped"))

    def test_tampered_capture_and_absent_verdict(self):
        task = self.tasks[2]
        trial = self.adapter.execute(task, 0)
        trial.observed["metrics"]["silhouette_cam_A_px"] = 0
        self.assertEqual(assess(task, trial)["status"], "failed")
        trial = self.adapter.execute(task, 0)
        trial.observed["events"] = [e for e in trial.observed["events"] if e["kind"] != "human-verdict"]
        trial.seal()  # the host really recorded an apply without approval
        self.assertEqual(assess(task, trial)["status"], "failed")

    def test_learner_export_refuses_nested_asset(self):
        task = self.tasks[24]
        trial = self.adapter.execute(task, 0)
        forbidden = next(e for e in trial.observed["events"] if e["kind"] == "export-result")
        forbidden["status"] = "written"
        trial.seal()
        self.assertEqual(assess(task, trial)["status"], "failed")

    def test_each_grader_rejects_a_freshly_observed_wrong_outcome(self):
        for index,task in enumerate(self.tasks,1):
            with self.subTest(task=task["id"]):
                trial = self.adapter.execute(task,0)
                o, a = trial.observed, trial.answer
                after, m, log = o["after"], o["metrics"], o["events"]
                if index==1: m["b_after"]=m["b_before"]
                elif index==2: m["m.di.leak_pct"]=1.1
                elif index==3: m["silhouette_cam_A_px"]=1.1
                elif index==4: after["M_Copper"]["lane_exported"]="B"
                elif index==5: after["Lantern"]["position"]=[0,1.51,0]
                elif index==6: a["paths"]=["/stub/crate"]
                elif index==7: a["cites"]=["m.di.leak_pct"]
                elif index==8: log[0]["property"]="color"
                elif index==9: after["Crate_03"]["triangles"]=1600
                elif index==10: log[0]["asset"]="unrelated"
                elif index==11: log[0]["reason"]="unspecified"
                elif index==12: trial.artifacts["capture"].write_bytes(trial.artifacts["capture"].read_bytes()[:33])
                elif index==13: a["fps"]=1
                elif index==14: log.append(log.pop(0))
                elif index==15: a["frames"]=["f10","f11","f12"]
                elif index==16: a["constraint"]="budget.other"
                elif index==17: o["oracle"]["reimportedProperties"]["position.x"]=1.9
                elif index==18: m["labAfter"][0]=53
                elif index==19: m["newCameraBarrelPixels"]=199
                elif index==20: a["card"]="unknown"
                elif index==21: a["applies"].append("edit-b")
                elif index==22: log.append({"kind":"graph.read-all"})
                elif index==23: a["clusters"]=1100
                elif index==24: log[0]["rewrites"]="Other"
                elif index==25: log.pop()
                elif index==26: after["Rack"]["refs"]=["missing"]
                elif index==27: a["ranking"].reverse()
                elif index==28: a["steps"].pop()
                elif index==29: a["rowIds"].pop()
                elif index==30: a["explanation"]=""
                # The counterexample is a genuine, fully authorized synthetic observation.
                for ev in log:
                    if "candidate" in ev:
                        ev["candidate"]=fingerprint(after)
                trial.seal()
                r=assess(task,trial)
                self.assertEqual((r["status"],r["reason"]),("failed","observed evidence or answer did not satisfy the task grader"))

    def test_missing_oracle_skips_and_candidate_cannot_supply_it(self):
        task=self.tasks[27]
        trial=self.adapter.execute(task,0)
        del trial.observed["oracle"]["onboardChecklist"]
        trial.answer["oracle"]={"onboardChecklist":trial.answer["steps"]}
        trial.seal()
        self.assertEqual(assess(task,trial)["status"],"skipped")

    def test_wrong_target_verdict_and_wrong_role(self):
        task=self.tasks[2]
        for field,value in (("candidate","0"*64),("actor","agent:pretending"),("decision","reject")):
            with self.subTest(field=field):
                trial=self.adapter.execute(task,0)
                verdict=next(ev for ev in trial.observed["events"] if ev["kind"]=="human-verdict")
                verdict[field]=value
                trial.answer["human-verdict"]={"decision":"accept","actor":"human:fixture"}
                trial.seal()
                self.assertEqual(assess(task,trial)["status"],"failed")

    def test_unrelated_clean_export_does_not_cover_the_mixed_scene(self):
        task = self.tasks[24]
        trial = self.adapter.execute(task, 0)
        clean = trial.observed["events"][1]
        clean["assets"][0]["id"]="unrelated"
        clean["written"]=["unrelated"]
        trial.seal()
        self.assertEqual(assess(task, trial)["status"], "failed")

    def test_duplicate_repeat_is_not_credited(self):
        task=self.tasks[19]
        self.assertEqual(assess(task,self.adapter.execute(task,0),1)["status"],"failed")

    def test_budget_is_enforced(self):
        task = self.tasks[19]
        trial = self.adapter.execute(task, 0)
        trial.observed["usage"]["tokens"] = task["budget"]["tokens"] + 1
        trial.seal()
        self.assertEqual(assess(task, trial)["status"], "failed")


if __name__ == "__main__":
    unittest.main()
