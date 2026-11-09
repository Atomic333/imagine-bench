#!/usr/bin/env python3
"""lane_a_compare.py — B01 / Gate 1 acceptance harness for the Lane-A fixtures.

Compares an engine capture against the Cycles references produced by build_lane_a_fixtures.py
and writes measurement rows. CIEDE2000 on display-referred sRGB (both images already carry the
AgX view transform; the engine capture must use the same OCIO config, exposure 0).

Usage:
  lane_a_compare.py workshop  <engine_capture.png> <fixture_dir> --camera cam_A [--out rows.csv]
  lane_a_compare.py zoo       <engine_grid.png>    <fixture_dir> [--out rows.csv] [--threshold 3.0]

workshop: writes m.bl.lit_room_delta_e (mean ΔE over covered pixels) and p95 ΔE.
zoo:      writes one row per material cell (ΔE mean inside the cell's sphere rect, shrunk 15 %),
          plus a coverage summary: how many Lane-A materials meet the threshold.
Exit 2 when the primary metric misses its threshold (workshop mean ΔE > 3.0; zoo: any lane_a
material above --threshold), so verify.ps1 can gate on it.
"""
import sys, json, csv, argparse, math, os
import numpy as np
try:
    from PIL import Image
except ImportError:
    Image = None
    try:
        import bpy   # fallback: run under Blender's python (blender -b --python-expr / Codex runtime without Pillow)
    except ImportError:
        sys.exit("needs Pillow, or run under Blender's python")

def load_rgb8(path):
    """Return HxWx3 uint8 sRGB (display-referred) regardless of loader."""
    if Image is not None:
        return np.asarray(Image.open(path).convert("RGB"), dtype=np.uint8)
    im = bpy.data.images.load(path, check_existing=False); w, h = im.size
    im.colorspace_settings.name = "Non-Color"       # read the stored bytes as-is: bpy would otherwise linearise sRGB PNGs
    px = np.empty(w * h * 4, dtype=np.float32); im.pixels.foreach_get(px); bpy.data.images.remove(im)
    a = px.reshape(h, w, 4)[::-1, :, :3]            # bpy rows are bottom-up
    return np.clip(np.round(a * 255), 0, 255).astype(np.uint8)

def srgb_to_lab(img):
    a = (np.asarray(img, dtype=np.float64) if isinstance(img, np.ndarray) else np.asarray(img.convert("RGB"), dtype=np.float64)) / 255.0
    lin = np.where(a <= 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    M = np.array([[0.4124564, 0.3575761, 0.1804375], [0.2126729, 0.7151522, 0.0721750], [0.0193339, 0.1191920, 0.9503041]])
    xyz = lin @ M.T
    xyz /= np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 0.008856, np.cbrt(xyz), 7.787 * xyz + 16 / 116)
    L = 116 * f[..., 1] - 16; A = 500 * (f[..., 0] - f[..., 1]); B = 200 * (f[..., 1] - f[..., 2])
    return np.stack([L, A, B], -1)

def ciede2000(lab1, lab2):
    L1, a1, b1 = lab1[..., 0], lab1[..., 1], lab1[..., 2]; L2, a2, b2 = lab2[..., 0], lab2[..., 1], lab2[..., 2]
    C1 = np.hypot(a1, b1); C2 = np.hypot(a2, b2); Cm = (C1 + C2) / 2
    G = 0.5 * (1 - np.sqrt(Cm ** 7 / (Cm ** 7 + 25 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360; h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    dLp = L2 - L1; dCp = C2p - C1p
    dh = h2p - h1p; dh = np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh)); dh = np.where(C1p * C2p == 0, 0, dh)
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dh / 2))
    Lm = (L1 + L2) / 2; Cmp = (C1p + C2p) / 2
    hs = h1p + h2p; hm = np.where(np.abs(h1p - h2p) > 180, np.where(hs < 360, (hs + 360) / 2, (hs - 360) / 2), hs / 2); hm = np.where(C1p * C2p == 0, hs, hm)
    T = 1 - 0.17 * np.cos(np.radians(hm - 30)) + 0.24 * np.cos(np.radians(2 * hm)) + 0.32 * np.cos(np.radians(3 * hm + 6)) - 0.20 * np.cos(np.radians(4 * hm - 63))
    Sl = 1 + 0.015 * (Lm - 50) ** 2 / np.sqrt(20 + (Lm - 50) ** 2); Sc = 1 + 0.045 * Cmp; Sh = 1 + 0.015 * Cmp * T
    dth = 30 * np.exp(-(((hm - 275) / 25) ** 2)); Rc = 2 * np.sqrt(Cmp ** 7 / (Cmp ** 7 + 25 ** 7)); Rt = -np.sin(np.radians(2 * dth)) * Rc
    return np.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2 + Rt * (dCp / Sc) * (dHp / Sh))

def rows_out(path, rows):
    if not path: return
    new = not os.path.exists(path)
    with open(path, "a", newline="") as f:
        w = csv.writer(f)
        if new: w.writerow(["id", "fixture", "value", "unit", "scope", "evidence"])
        for r in rows: w.writerow(r)

def workshop(a):
    fx = json.load(open(os.path.join(a.fixture_dir, "fixture.json")))
    suffix = "" if a.reference == "full" else "_" + a.reference
    ref = load_rgb8(os.path.join(a.fixture_dir, f"ref_{a.camera}{suffix}.png")); eng = load_rgb8(a.capture)
    if eng.shape != ref.shape: sys.exit(f"capture {eng.shape[1]}x{eng.shape[0]} must match reference {ref.shape[1]}x{ref.shape[0]}")
    de = ciede2000(srgb_to_lab(eng), srgb_to_lab(ref))
    mean, p95, p99 = float(de.mean()), float(np.percentile(de, 95)), float(np.percentile(de, 99))
    rows = [["m.bl.lit_room_delta_e", fx["fixture"], f"{mean:.3f}", "dE", f"{a.camera} mean CIEDE2000 vs Cycles {fx['renderer']} ({a.reference} reference)", a.capture],
            ["m.bl.lit_room_delta_e_p95", fx["fixture"], f"{p95:.3f}", "dE", f"{a.camera} p95", a.capture]]
    if a.mask and os.path.exists(os.path.join(a.fixture_dir, f"mask_{a.camera}.png")) and "diagnostics" in fx:
        mb = load_rgb8(os.path.join(a.fixture_dir, f"mask_{a.camera}.png"))[..., 0].astype(np.float64) / 255.0
        nmat = max(fx["diagnostics"]["material_index"].values())
        if mb.max() * 255 > nmat * 1.5:                      # mask was written through the sRGB display transform: undo it
            mb = np.where(mb <= 0.04045, mb / 12.92, ((mb + 0.055) / 1.055) ** 2.4)
        m = np.clip(np.round(mb * 255), 0, 255).astype(int)
        inv = {v: k for k, v in fx["diagnostics"]["material_index"].items()}
        for idx in sorted(set(np.unique(m)) - {0}):
            sel = m == idx
            if sel.sum() < 50: continue
            name = inv.get(int(idx), f"mat{idx}"); md = float(de[sel].mean())
            rows.append([f"m.bl.material_delta_e", fx["fixture"], f"{md:.3f}", "dE", f"{a.camera} {name} ({int(sel.sum())} px, {a.reference} reference)", a.capture])
            print(f"   {name:<28} {md:6.3f}  ({100 * sel.mean():4.1f}% of frame)")
        bg = m == 0
        if bg.any(): print(f"   {'(background/sky)':<28} {float(de[bg].mean()):6.3f}  ({100 * bg.mean():4.1f}% of frame)")
    rows_out(a.out, rows)
    print(f"{fx['fixture']} {a.camera}: mean dE {mean:.3f}  p95 {p95:.3f}  p99 {p99:.3f}  ({'PASS' if mean <= 3.0 else 'MISS > 3.0'})")
    if a.heatmap:
        hm = (np.clip(de / 10.0, 0, 1) * 255).astype(np.uint8)
        if Image is not None: Image.fromarray(hm).save(a.heatmap)
        else: np.save(a.heatmap + ".npy", hm)
    return 0 if mean <= 3.0 else 2

def zoo(a):
    fx = json.load(open(os.path.join(a.fixture_dir, "fixture.json")))
    ref = load_rgb8(os.path.join(a.fixture_dir, "ref_grid.png")); eng = load_rgb8(a.capture)
    if eng.shape != ref.shape: sys.exit(f"capture {eng.shape[1]}x{eng.shape[0]} must match reference {ref.shape[1]}x{ref.shape[0]}")
    de = ciede2000(srgb_to_lab(eng), srgb_to_lab(ref))
    rows, misses, lane_a_total, lane_a_ok = [], [], 0, 0
    for c in fx["cells"]:
        x0, y0, x1, y1 = c["rect"]; w, h = x1 - x0, y1 - y0
        sx, sy = int(w * 0.15), int(h * 0.15)
        cell = de[y0 + sy:y1 - sy, x0 + sx:x1 - sx]
        m = float(cell.mean()) if cell.size else float("nan")
        c["engine_delta_e"] = m
        rows.append([f"m.bl.material_delta_e", fx["fixture"], f"{m:.3f}", "dE", f"{c['node']} lane_a={c.get('lane_a')}", a.capture])
        if c.get("lane_a"):
            lane_a_total += 1
            if m <= a.threshold: lane_a_ok += 1
            else: misses.append((c["node"], round(m, 2)))
    rows.append(["m.bl.mtlx_node_coverage_pct", fx["fixture"], f"{100.0 * lane_a_ok / max(1, lane_a_total):.1f}", "percent",
                 f"lane_a materials within dE {a.threshold}: {lane_a_ok}/{lane_a_total}", a.capture])
    rows_out(a.out, rows)
    json.dump(fx, open(os.path.join(os.path.dirname(a.out) if a.out else ".", "zoo-compare.json"), "w"), indent=1)
    print(f"{fx['fixture']}: lane_a within dE {a.threshold}: {lane_a_ok}/{lane_a_total}; misses: {misses[:15]}{' …' if len(misses) > 15 else ''}")
    return 0 if not misses else 2

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest="mode", required=True)
    w = sub.add_parser("workshop"); w.add_argument("capture"); w.add_argument("fixture_dir"); w.add_argument("--camera", default="cam_A"); w.add_argument("--out"); w.add_argument("--heatmap"); w.add_argument("--reference", default="full", help="full | direct | direct_sun | direct_area | direct_world | direct_point (see fixture.json diagnostics)")
    w.add_argument("--mask", action="store_true", help="also report mean dE per material using mask_<cam>.png and fixture.json diagnostics.material_index")
    z = sub.add_parser("zoo"); z.add_argument("capture"); z.add_argument("fixture_dir"); z.add_argument("--out"); z.add_argument("--threshold", type=float, default=3.0)
    a = ap.parse_args(); sys.exit(workshop(a) if a.mode == "workshop" else zoo(a))
