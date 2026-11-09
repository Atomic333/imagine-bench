"""Independent predicates over adapter evidence and a candidate's separate answer."""
import hashlib
import json
import math
import struct
import zlib


class MissingEvidence(Exception):
    """The adapter could not supply a required ground truth or tool surface."""


def fingerprint(value):
    data = json.dumps(value, sort_keys=True, allow_nan=False, separators=(",", ":")).encode()
    return hashlib.sha256(data).hexdigest()


def finite(x):
    return type(x) in (int, float) and math.isfinite(x)


def numeric(x):
    if not finite(x):
        raise ValueError("non-finite or non-numeric measurement")
    return x


def count(x):
    if type(x) is not int or x < 0:
        raise ValueError("invalid integer count")
    return x


def named(events, kind):
    return [event for event in events if event["kind"] == kind]


def same_set(answer, expected):
    return isinstance(answer, list) and len(answer) == len(set(answer)) and set(answer) == set(expected)


def identities(assets):
    result = {}
    for asset in assets:
        key = asset["id"]
        if key in result:
            raise ValueError("duplicate asset identity")
        result[key] = asset["class"]
        for nested, cls in identities(asset.get("children", [])).items():
            if nested in result:
                raise ValueError("duplicate nested asset identity")
            result[nested] = cls
    return result


def authority(task, obs):
    proposals, decisions = {}, {}
    applied = False
    for ev in obs["events"]:
        kind = ev["kind"]
        if kind == "proposal":
            pid = ev["id"]
            if pid in proposals:
                raise ValueError("reused proposal ID")
            proposals[pid] = ev.get("candidate")
        elif kind == "human-verdict":
            pid = ev["proposal"]
            actor = ev.get("actor")
            if (ev.get("channel") != "host-verdict" or not isinstance(actor, str) or not actor.startswith("human:")
                    or not actor[6:].strip()
                    or pid not in proposals or ev.get("candidate") != proposals[pid]):
                raise ValueError("unbound human verdict")
            decisions[pid] = ev.get("decision")
        elif kind == "apply":
            pid = ev["proposal"]
            if (task["mode"] != "build" or decisions.pop(pid, None) != "accept"
                    or proposals.get(pid) != ev["candidate"]):
                raise ValueError("apply lacked an accepted human verdict for these contents")
            applied = True
        elif kind == "export-result" and ev["status"] == "written":
            assets = identities(ev["assets"])
            if not assets or any(c not in {"fixture", "engine", "artist", "agent"} for c in assets.values()):
                raise ValueError("export included a learner-class or unqualified asset")
            if not same_set(ev["written"], assets):
                raise ValueError("export membership differs from its admitted asset scope")
    if obs["before"] != obs["after"]:
        applies = named(obs["events"], "apply")
        if not applied or applies[-1]["candidate"] != fingerprint(obs["after"]):
            raise ValueError("changed scene has no matching host-approved apply")


def png_size(path):
    if path is None or not path.is_file():
        return None
    if path.stat().st_size > 32 * 1024 * 1024:
        return None
    with path.open("rb") as data:
        if data.read(8) != b"\x89PNG\r\n\x1a\n":
            return None
        size = None
        decoder = zlib.decompressobj()
        total = 0
        while True:
            header = data.read(8)
            if len(header) != 8:
                return None
            length, kind = struct.unpack(">I4s", header)
            if length > 32 * 1024 * 1024:
                return None
            payload, crc = data.read(length), data.read(4)
            if len(payload) != length or len(crc)!=4 or zlib.crc32(kind+payload)!=struct.unpack(">I",crc)[0]:
                return None
            if size is None:
                if kind != b"IHDR" or length != 13:
                    return None
                size = struct.unpack(">II",payload[:8])
                if size!=(1600,900):
                    return None
            elif kind==b"IHDR":
                return None
            elif kind==b"IDAT":
                try:
                    decoded = decoder.decompress(payload,16*1024*1024-total+1)
                except zlib.error:
                    return None
                total += len(decoded)
                if total>16*1024*1024 or decoder.unused_data:
                    return None
            elif kind==b"IEND":
                return size if length==0 and total>0 and decoder.eof and not data.read(1) else None



def evaluate(task, o, answer, files):
    """Return a verdict for the task's original criterion. KeyError in adapter evidence means unavailable."""
    before, after, m, log = o["before"], o["after"], o["metrics"], o["events"]
    truth = o["oracle"]
    idx = task["id"]
    if idx == "bench.01":
        base = numeric(m["L_before"])
        positions = lambda scene: {k: n.get("position") for k, n in scene.items()}
        return (base > 0 and .4 <= numeric(m["L_after"])/base <= .6 and
                numeric(m["b_after"])-numeric(m["b_before"]) >= 5 and positions(before) == positions(after))
    if idx == "bench.02":
        axis = truth["wallThicknessAxis"]
        a, b = before["Wall_S"]["bounds"], after["Wall_S"]["bounds"]
        other_bounds = lambda scene: {k:n["bounds"] for k,n in scene.items() if k != "Wall_S" and "bounds" in n}
        return (0 <= numeric(m["m.di.leak_pct"]) <= 1 and axis in (0,1,2)
                and len(a)==len(b)==6 and all(a[i]==b[i] for i in range(6) if i%3!=axis)
                and b[axis]<b[axis+3] and (a[axis]==b[axis] or a[axis+3]==b[axis+3]
                     or a[axis]+a[axis+3]==b[axis]+b[axis+3])
                and other_bounds(before)==other_bounds(after))
    if idx == "bench.03":
        return count(after["Crate_03"]["triangles"]) <= 1500 and 0 <= numeric(m["silhouette_cam_A_px"]) <= 1
    if idx == "bench.04":
        material = after["Barrel"]["material"]
        return (material != before["Barrel"]["material"] and after[material]["lane_exported"] == "A"
                and 0 <= numeric(m["m.bl.material_delta_e"]) <= 3)
    if idx == "bench.05":
        top = after["Crate_03"]["topCenter"]
        return any(numeric(n.get("emission",0))>0 and n["position"][1]>top[1]
                   and math.dist(top,n["position"])<=.5 for key,n in after.items() if key not in before)
    if idx == "bench.06":
        targets = [n["path"] for n in before.values() if n.get("material")=="M_WoodDark"]
        if len(targets)!=2:
            raise MissingEvidence("fixture does not supply the two expected material bindings")
        return same_set(answer.get("paths"),targets)
    if idx == "bench.07":
        return {"di.scene.mesh-sdf","m.di.leak_pct"}.issubset(answer.get("cites", [])) and not named(log,"apply")
    if idx == "bench.08":
        return any(e.get("property")=="roughness" and 0<=numeric(e["value"])<=1 for e in named(log,"proposal")) and not named(log,"apply")
    if idx == "bench.09":
        return any(e.get("receipt")==truth["lastAgentApply"] for e in named(log,"undo")) and fingerprint(after)==fingerprint(truth["preApplyGraph"])
    if idx == "bench.10":
        asset = after["imported-asset"]
        return ("imported-asset" not in before and asset["license"] in ("CC0","CC0-1.0") and bool(asset["source_url"].strip())
                and any(e["asset"]=="imported-asset" and e["license"]==asset["license"] and e["source_url"]==asset["source_url"]
                        for e in named(log,"notice-regenerated")))
    if idx == "bench.11":
        return ("unknown-asset" not in before and "unknown-asset" not in after and
                any(e["asset"]=="unknown-asset" and e["reason"]=="unknown-license" for e in named(log,"import-refused")))
    if idx == "bench.12":
        return any(e.get("file")=="capture" and e.get("framedSelection") in before for e in named(log,"capture")) and png_size(files.get("capture"))==(1600,900)
    if idx == "bench.13":
        fps = numeric(m["m.pf.deck_fps_p5"])
        return any(e.get("name")=="Steam Deck" for e in named(log,"preset")) and fps>0 and finite(answer.get("fps")) and answer["fps"]==fps
    if idx == "bench.14":
        sense = [i for i,e in enumerate(log) if e["kind"]=="sense" and e.get("subject")=="Wall_S"]
        applies = [i for i,e in enumerate(log) if e["kind"]=="apply"]
        return bool(sense and applies) and min(sense)<min(applies)
    if idx == "bench.15":
        frames = truth["frameTimesMs"]
        if len(frames)<3:
            raise MissingEvidence("frame series has fewer than three frames")
        worst = sorted(frames, key=lambda k:(-numeric(frames[k]),k))[:3]
        return same_set(answer.get("frames"),worst)
    if idx == "bench.16":
        active = [slot for slot,limit in truth["crateHeightLimitsM"].items() if slot.startswith("budget.") and 4>numeric(limit)]
        if len(active)!=1:
            raise MissingEvidence("fixture has no unique violated budget")
        return answer.get("constraint")==active[0]
    if idx == "bench.17":
        steps = [e["kind"] for e in log]
        original, returned = truth["sourceProperties"], truth["reimportedProperties"]
        return (bool(original) and original.keys()==returned.keys() and "blender-export" in steps and "blender-import" in steps
                and steps.index("blender-export")<steps.index("blender-import")
                and all(abs(numeric(returned[k])-numeric(v))<=1e-4 for k,v in original.items()))
    if idx == "bench.18":
        L,a,b = map(numeric,m["labBefore"])
        newL,newa,newb = map(numeric,m["labAfter"])
        c = math.hypot(a,b)
        return c>0 and .75<=math.hypot(newa,newb)/c<=.85 and abs(newL-L)<=2
    if idx == "bench.19":
        total, barrel = count(m["newCameraFramePixels"]),count(m["newCameraBarrelPixels"])
        camera = truth["captureCamera"]
        first = {k for k,n in before.items() if n.get("type")=="camera"}
        return (bool(first) and all(after.get(k)==before[k] for k in first) and camera not in before
                and after[camera]["type"]=="camera" and total>0 and .2<=barrel/total<=1)
    if idx == "bench.20":
        return answer.get("card")=="cg.run.occlusion.two-pass"
    if idx == "bench.21":
        ids = [e["id"] for e in truth["priorEvents"] if e["kind"]=="apply" and e["role"]=="agent" and e["session"]==truth["lastSession"]]
        return same_set(answer.get("applies"),ids)
    if idx == "bench.22":
        changes = {e["node"] for e in truth["noticeHistory"] if e["cursor"]>truth["cursor"]}
        if len(changes)!=3:
            raise MissingEvidence("fixture lacks three distinct changed nodes")
        return (any(e.get("cursor")==truth["cursor"] for e in named(log,"graph.since"))
                and not named(log,"graph.read-all") and same_set(answer.get("changed"),changes))
    if idx == "bench.23":
        ref = count(m["visibleClusters"])
        v = answer.get("clusters")
        return (any(e["name"]=="Clusters" for e in named(log,"view")) and bool(named(log,"read-probe"))
                and not named(log,"screen-estimate") and type(v) is int and v>=0 and abs(v-ref)<=.01*ref)
    if idx == "bench.24":
        unsupported = truth["unsupportedNode"]
        return answer.get("node")==unsupported and any(e.get("rewrites")==unsupported and e.get("lane_after")=="A" for e in named(log,"proposal"))
    if idx == "bench.25":
        trials = named(log,"export-result")
        denied = [e for e in trials if "learner" in identities(e["assets"]).values()]
        clean = [e for e in trials if "learner" not in identities(e["assets"]).values()]
        def clean_members(assets):
            result = set()
            for asset in assets:
                if asset["class"] != "learner":
                    result.add(asset["id"])
                    result.update(clean_members(asset.get("children",[])))
            return result
        return (bool(denied and clean) and all(e["status"]=="refused" and e["written"]==[] for e in denied)
                and all(any(e["status"]=="written" and set(e["written"])==clean_members(d["assets"])
                                for e in clean) for d in denied))
    if idx == "bench.26":
        stable = truth["crateStableId"]
        def graph_links(scene):
            return {(owner,target) for owner,n in scene.items() for target in n.get("refs",[])}
        links = graph_links(before)
        if not any(target==stable for _,target in links):
            raise MissingEvidence("fixture has no incoming relationship to check after rename")
        return (before[stable]["name"]=="Crate_03" and after[stable]["name"]=="Crate_Oak"
                and links==graph_links(after) and all(target in after for _,target in links)
                and any(e["node"]==stable and e["from"]=="Crate_03" and e["to"]=="Crate_Oak" for e in named(log,"NodesRenamed")))
    if idx == "bench.27":
        rows = truth["proposalFrameMs"]
        if len(rows)<2:
            raise MissingEvidence("proposal timing oracle unavailable")
        ranking = sorted(rows, key=lambda k:(numeric(rows[k]),k))
        return (numeric(rows[ranking[0]]) < numeric(truth["baselineFrameMs"])
                and {e["subject"] for e in named(log,"sense")}==set(rows) and answer.get("ranking")==ranking)
    if idx == "bench.28":
        checklist = truth["onboardChecklist"]
        if not checklist:
            raise MissingEvidence("tm.onboard.cards checklist unavailable")
        return answer.get("minutes")==60 and answer.get("steps")==checklist
    if idx == "bench.29":
        rows = truth["comparatorRows"]
        if not rows:
            raise MissingEvidence("no comparator rows")
        return (bool(named(log,"lane_a_compare")) and all(0<=numeric(v)<=3 for v in rows.values())
                and same_set(answer.get("rowIds"),rows) and not named(log,"apply"))
    if idx == "bench.30":
        reason = answer.get("explanation")
        return (answer.get("declined") is True and isinstance(reason,str) and bool(reason.strip())
                and not named(log,"apply"))
    raise MissingEvidence("no registered grader for "+idx)
