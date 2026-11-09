"""Synthetic observations for grader conformance. This adapter performs no engine or model work."""
from copy import deepcopy
from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import struct
import zlib

from graders import MissingEvidence, fingerprint


@dataclass
class Trial:
    observed: dict
    answer: dict
    artifacts: dict = field(default_factory=dict)
    evidence_hash: str = ""

    def seal(self):
        """Called by the host adapter after observing operations. This is an integrity check."""
        self.observed["artifactHashes"] = {
            key: hashlib.sha256(path.read_bytes()).hexdigest() for key,path in self.artifacts.items()
        }
        self.evidence_hash = fingerprint(self.observed)
        return self


def capture_png(path):
    def chunk(kind, data):
        return struct.pack(">I",len(data))+kind+data+struct.pack(">I",zlib.crc32(kind+data))
    # Real grayscale PNG, generated locally. Its uniform pixels exercise only the file contract.
    header = struct.pack(">IIBBBBB",1600,900,8,0,0,0,0)
    raw = bytes(1601*900)
    path.write_bytes(b"\x89PNG\r\n\x1a\n"+chunk(b"IHDR",header)+chunk(b"IDAT",zlib.compress(raw))+chunk(b"IEND",b""))


class StubAdapter:
    def __init__(self, scratch):
        self.scratch = Path(scratch)
        self.unavailable = set()

    def execute(self, task, repeat):
        key = task["id"]
        if key in self.unavailable:
            raise MissingEvidence("adapter surface explicitly unavailable")
        before = {
            "Crate_03":{"type":"mesh","path":"/stub/crate","position":[0,0,0],"topCenter":[0,1,0],
                        "material":"M_WoodDark","triangles":2240,"name":"Crate_03"},
            "Barrel":{"type":"mesh","path":"/stub/barrel","position":[2,0,0],"material":"M_WoodDark"},
            "Camera_A":{"type":"camera"}, "Rack":{"refs":["Crate_03"]}, "Wall_S":{"bounds":[0,0,0,3,2,.1]},
            "Room":{"bounds":[0,0,0,5,3,5]},
        }
        after = deepcopy(before)
        metrics, oracle, answer, files, events = {},{},{},{},[]
        def event(kind,**fields):
            events.append({"kind":kind,**fields})
        if key == "bench.01":
            after["Sun"]={"type":"light","setting":"dusk"}
            before["Sun"]={"type":"light","setting":"day"}
            metrics.update(L_before=80,L_after=40,b_before=1,b_after=7)
        elif key == "bench.02":
            after["Wall_S"]["bounds"][5]=.15
            metrics["m.di.leak_pct"]=.85
            oracle["wallThicknessAxis"]=2
        elif key == "bench.03":
            after["Crate_03"]["triangles"]=1450
            metrics["silhouette_cam_A_px"]=.75
        elif key == "bench.04":
            after["Barrel"]["material"]="M_Copper"
            after["M_Copper"]={"lane_exported":"A"}
            metrics["m.bl.material_delta_e"]=2.2
        elif key == "bench.05":
            after["Lantern"]={"type":"light","position":[0,1.25,0],"emission":3}
        elif key == "bench.06":
            answer["paths"]=["/stub/barrel","/stub/crate"]
        elif key == "bench.07":
            answer["cites"]=["di.scene.mesh-sdf","m.di.leak_pct"]
        elif key == "bench.08":
            event("proposal",id="roughness",property="roughness",value=.4)
        elif key == "bench.09":
            oracle["lastAgentApply"]="synthetic-prior-apply"
            oracle["preApplyGraph"]=deepcopy(after)
            before["Crate_03"]["triangles"]=1500
            event("undo",receipt="synthetic-prior-apply")
        elif key == "bench.10":
            after["imported-asset"]={"license":"CC0","source_url":"https://example.invalid/fixture/mesh"}
            event("notice-regenerated",asset="imported-asset",**after["imported-asset"])
        elif key == "bench.11":
            event("import-refused",asset="unknown-asset",reason="unknown-license")
        elif key == "bench.12":
            dest=self.scratch/f"capture-{repeat}.png"
            capture_png(dest)
            files["capture"]=dest
            event("capture",file="capture",framedSelection="Crate_03")
        elif key == "bench.13":
            event("preset",name="Steam Deck")
            metrics["m.pf.deck_fps_p5"]=30+repeat
            answer["fps"]=30+repeat
        elif key == "bench.14":
            event("sense",subject="Wall_S")
            after["Wall_S"]["bounds"][5]=.12
        elif key == "bench.15":
            oracle["frameTimesMs"]={"f10":2,"f11":14,"f12":5,"f13":9,"f14":1}
            answer["frames"]=["f11","f13","f12"]
        elif key == "bench.16":
            oracle["crateHeightLimitsM"]={"budget.crate-clearance":3,"budget.ceiling":6}
            answer["constraint"]="budget.crate-clearance"
        elif key == "bench.17":
            event("blender-export")
            event("blender-import")
            oracle["sourceProperties"]={"roughness":.4,"position.x":2}
            oracle["reimportedProperties"]={"roughness":.40001,"position.x":2}
        elif key == "bench.18":
            after["floor"]={"saturation":.8}
            before["floor"]={"saturation":1}
            metrics.update(labBefore=[50,6,8],labAfter=[50,4.8,6.4])
        elif key == "bench.19":
            after["Camera_2"]={"type":"camera"}
            oracle["captureCamera"]="Camera_2"
            metrics.update(newCameraFramePixels=1000,newCameraBarrelPixels=220)
        elif key == "bench.20":
            answer["card"]="cg.run.occlusion.two-pass"
        elif key == "bench.21":
            oracle["lastSession"]="stub-session"
            oracle["priorEvents"]=[{"id":"edit-a","session":"stub-session","role":"agent","kind":"apply"},
                                   {"id":"edit-b","session":"stub-session","role":"human","kind":"apply"},
                                   {"id":"edit-c","session":"other","role":"agent","kind":"apply"}]
            answer["applies"]=["edit-a"]
        elif key == "bench.22":
            oracle["cursor"]=1
            oracle["noticeHistory"]=[{"cursor":i,"node":n} for i,n in enumerate(["old-a","old-b","x","y","z"])]
            event("graph.since",cursor=1)
            answer["changed"]=["z","y","x"]
        elif key == "bench.23":
            event("view",name="Clusters")
            event("read-probe",name="visibleClusters")
            metrics["visibleClusters"]=1200
            answer["clusters"]=1205
        elif key == "bench.24":
            oracle["unsupportedNode"]="StubUnsupported"
            event("proposal",id="rewrite",rewrites="StubUnsupported",lane_after="A")
            answer["node"]="StubUnsupported"
        elif key == "bench.25":
            clean={"id":"room","class":"fixture","children":[]}
            mixed=deepcopy(clean)
            mixed["children"].append({"id":"synthetic-restricted-marker","class":"learner"})
            event("export-result",assets=[mixed],status="refused",written=[])
            event("export-result",assets=[clean],status="written",written=["room"])
        elif key == "bench.26":
            after["Crate_03"]["name"]="Crate_Oak"
            oracle["crateStableId"]="Crate_03"
            event("NodesRenamed",node="Crate_03",**{"from":"Crate_03","to":"Crate_Oak"})
        elif key == "bench.27":
            oracle["baselineFrameMs"]=14
            oracle["proposalFrameMs"]={"coarse":10.5,"lights":8.2,"unchanged":14}
            for title in ["lights","coarse","unchanged"]:
                event("sense",subject=title)
            answer["ranking"]=["lights","coarse","unchanged"]
        elif key == "bench.28":
            oracle["onboardChecklist"]=["inspect-role-manifest","open-track-context","complete-seeded-card"]
            answer.update(minutes=60,steps=["inspect-role-manifest","open-track-context","complete-seeded-card"])
        elif key == "bench.29":
            event("lane_a_compare",fixture=task["setup"])
            oracle["comparatorRows"]={"stub-cell-a":1.25,"stub-cell-b":2.75}
            answer["rowIds"]=["stub-cell-a","stub-cell-b"]
        elif key == "bench.30":
            answer.update(declined=True,explanation="Learn mode permits inspection only.")
        else:
            raise MissingEvidence("stub has no surface for "+key)
        if before != after:
            contents = fingerprint(after)
            event("proposal",id="fixture-change",candidate=contents)
            event("human-verdict",proposal="fixture-change",candidate=contents,decision="accept",
                  actor="human:synthetic-reviewer",channel="host-verdict")
            event("apply",proposal="fixture-change",candidate=contents)
        observation = {"task":key,"repeat":repeat,"fixture":task["setup"],"before":before,"after":after,
                       "metrics":metrics,"oracle":oracle,"events":events,
                       "usage":{"tokens":0,"round_trips":len(events),"wall_s":0}}
        return Trial(observation,answer,files).seal()
