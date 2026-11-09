"""Check the published workshop images with the original comparison program."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parent
FIXTURE = Path("fixtures/fx.workshop.room")
METRICS = re.compile(r"mean dE ([\d.]+)\s+p95 ([\d.]+)\s+p99 ([\d.]+)")


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def compare(capture, camera, mode, folder, expected_exit):
    folder.mkdir(parents=True)
    rows = folder / "rows.csv"
    command = [
        sys.executable, "-B", "lane_a_compare.py", "workshop", str(capture),
        FIXTURE.as_posix(), "--camera", camera, "--reference", mode, "--mask",
        "--out", str(rows), "--heatmap", str(folder / "heatmap.png"),
    ]
    process = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if process.returncode != expected_exit:
        raise RuntimeError(f"{mode}/{camera} returned {process.returncode}: {process.stderr or process.stdout}")
    match = METRICS.search(process.stdout)
    if not match:
        raise ValueError(f"Missing {mode}/{camera} summary")
    with rows.open(newline="") as stream:
        material = {}
        for row in csv.DictReader(stream):
            if row["id"] == "m.bl.material_delta_e":
                name = row["scope"].split(" (", 1)[0].split(" ", 1)[1]
                material[name] = float(row["value"])
    return dict(zip(("mean", "p95", "p99"), map(float, match.groups()))), material


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True, help="new directory for rows, heatmaps and summary")
    args = parser.parse_args()
    output = args.output.resolve()
    manifest = json.loads((ROOT / "hashes.json").read_bytes())
    for name, expected in manifest["files"].items():
        if sha(ROOT / name) != expected:
            raise ValueError(f"SHA-256 mismatch: {name}")
    history = json.loads((ROOT / "historical-B01.json").read_bytes())
    if sha(ROOT / "lane_a_compare.py") != history["comparatorSha256"]:
        raise ValueError("The comparator differs from the original B01 run")
    output.mkdir(parents=True, exist_ok=False)
    observation = {}
    for key, expected in history["cases"].items():
        mode, camera = key.split("/")
        score, material = compare(expected["capture"], camera, mode, output / mode / camera, 0)
        if any(score[k] != expected[k] for k in score) or material != expected["perMaterial"]:
            raise ValueError(f"{key} differs from the historical metrics")
        observation[key] = {**score, "perMaterial": material}
        print(f"{key:<30} mean {score['mean']:.3f}  p95 {score['p95']:.3f}  p99 {score['p99']:.3f}")
    self_scores = {}
    for camera in ("cam_A", "cam_B", "cam_C"):
        reference = FIXTURE / f"ref_{camera}_direct.png"
        score, material = compare(reference, camera, "direct", output / "self" / camera, 0)
        if any(score.values()) or any(material.values()):
            raise ValueError(f"{camera} reference self-check is nonzero")
        self_scores[camera] = score
    image = output / "black-control.png"
    with Image.open(ROOT / FIXTURE / "ref_cam_A_direct.png") as reference:
        Image.fromarray(np.zeros((reference.height, reference.width, 3), dtype=np.uint8)).save(image)
    black, _ = compare(image, "cam_A", "direct", output / "black", 2)
    if black["mean"] <= 3:
        raise ValueError("Black-image negative control failed to exceed the workshop threshold")
    result = {"historicalCases": observation, "referenceSelf": self_scores, "blackNegative": black}
    (output / "summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    print(f"Matched all {len(observation)} historical cases with material masks.")


if __name__ == "__main__":
    main()
