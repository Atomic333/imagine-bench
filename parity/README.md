# Workshop renderer parity

Reproduce the historical B01 comparison using the retained Blackmuse images, then score an image from your own renderer against the same Blender Cycles references. The fixture contains the authored workshop USD, its seven texture files, three camera views, material-ID masks and light-source splits. Measurements use pixel-aligned 960×540 images with AgX at exposure 0.

## Reproduce the historical run

From the repository root, use Python with NumPy and Pillow. The recorded replay used Python 3.12.14, NumPy 2.3.5 and Pillow 13.0.0.

```sh
python -m pip install -r parity/requirements.txt
python -B parity/reproduce.py --output results/workshop-parity
```

Choose a new output directory for each run. The script checks the published file digests, invokes the original comparator and writes per-camera CSV rows, difference heatmaps and a JSON summary. It checks all 18 retained captures against the historical mean, p95, p99 and seven masked material values per image.

| All direct sources | Mean ΔE00 | p95 | p99 |
|---|---:|---:|---:|
| cam_A | 1.577 | 5.612 | 10.395 |
| cam_B | 0.986 | 3.904 | 8.726 |
| cam_C | 1.036 | 3.930 | 7.495 |

The candidate images came from a historical offscreen native renderer using 16 direct realizations, four spatial samples and zero diffuse continuations. The source splits cover all lamps, area lamp only, the 1 cm small-area approximation, sun only, world only, and world only with bump disabled. Three direct-reference self-comparisons measure exactly zero. A black negative-control image exceeds the threshold with a mean of 31.037 on cam_A. These controls exercise the comparator itself. The stored-image replay does not require a Blackmuse renderer or Blender installation.

## Score a capture

Choose the corresponding authored camera and reference mode. For `direct`, capture direct lamp/world/emission with secondary transport disabled. Use `full` for the supplied multi-bounce reference. Feed the comparator the display-referred sRGB image after applying the same AgX transform and camera exposure.

```sh
python -B parity/lane_a_compare.py workshop my-cam-A.png parity/fixtures/fx.workshop.room --camera cam_A --reference direct --mask --out scores.csv --heatmap difference.png
```

The comparator returns 0 when the full-frame mean ΔE00 is at most 3.0 and 2 when it exceeds 3.0. The mask adds per-material measurements. The cam_D leak PNG/EXR is supplemental scene data; the historical camera scores use A, B and C.

## Data and provenance

The original fixture records **CC0 (procedural, Blackmuse)**. Its USD remains byte-identical to the scored source at SHA-256 `52afec8f63ab33aff9b099949c692c3f11384cde7410f95bd23f3bed64b0823b`. The comparator SHA-256 is `3cfe8372699d6218b4190ee2e9798be578b0ef74e49bb8605bd1eab89478ea66`. Optional PNG and EXR metadata was removed for distribution. OpenImageIO verified the equality of every source and published channel value at native precision across all 51 images. The published fixture descriptor points to the new container hashes.

The editable Blender file is omitted because its saved application state retained private host metadata. The USD and textures are portable source assets, and the recorded comparison can be reproduced from this package. Regenerating the exact original Blender authoring state is outside its scope. Blackmuse performed the staged replay; external third-party reproduction remains open.

[Public file hashes](hashes.json) · [Source-to-public hashes, rights and pixel verification](provenance.json) · [Historical per-camera scores](historical-B01.json)
