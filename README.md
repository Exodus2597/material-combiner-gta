# Material Combiner GTA

A Blender add-on for importing textured GLB models and merging selected meshes into a readable texture atlas for **GTA V / Sollumz**.

Modified edition of [Shotariya's Material Combiner](https://github.com/Grim-es/material-combiner-addon), based on upstream commit `eed9ca2`. Tested with **Blender 5.2.1 LTS and Sollumz 2.9.0**.

**[Download the latest release](https://github.com/Exodus2597/material-combiner-gta/releases/latest)** · **[Installation](docs/INSTALLATION.md)** · **[Usage](docs/USAGE.md)**

## What this edition adds

- Import GLB models and attach external diffuse/normal textures through Unreal material JSON references or unambiguous name matching.
- Merge selected meshes into one Sollumz Drawable Model, one material and one `UVMap 0`.
- Keep whole material texture sheets and their original UV island arrangement. Flexible rectangular packing uses spare atlas space more efficiently.
- Export separate diffuse/opacity and tangent-normal DDS files using the same UV layout.
- Choose diffuse and normal resolutions independently, including **2048×2048 diffuse / 512×512 normals**.
- Choose **A8R8G8B8** or **DXT5 (BC3)** independently for each atlas, with complete mipmaps.
- Delete every vertex group and weight from merged output. Original meshes retain their data.
- Validate unsupported inputs and restore scene state after failed imports or merges.

The original PNG/PBR combining workflow remains available. See [added features and fixes](docs/FEATURES.md) and [changelog](CHANGELOG.md).

## Quick start

1. Enable Sollumz and disable previous Material Combiner editions.
2. Download the release installation ZIP. Install it through **Edit → Preferences → Add-ons → Install from Disk** and enable **Shotariya's Material Combiner**.
3. Open **N → MatCombiner → Import GLB + Textures** to import a model and its maps, or select existing mesh objects in Object Mode.
4. Click **Merge Selected + DDS Atlas**, choose a new lowercase DDS filename and select sizes, formats, UV layout and shader.
5. Export the resulting Drawable through Sollumz.

DDS generation uses Blender's bundled NumPy. No Pillow or external DDS converter is required for the GTA workflow. Pillow is used only by the legacy PNG workflow.

Version 2.6.3 simplifies the panels: credits show Exodus (original by shotariya), donation/Discord/Pillow installer controls are removed, and update checks use stable releases from this repository.

## Output and limits

The merge creates `name.dds`, optional `name_normal.dds`, and one merged model with one material and one UV map. Diffuse is sRGB with opacity in alpha; normals are Non-Color, DirectX (-Y), with opaque alpha. Both textures are marked embedded in the Sollumz material.

**Merged output has no vertex groups or weights.** A compatible copied armature may remain in the hierarchy; retargeting and new weighting are not performed. Source meshes, UVs, materials and weights remain unchanged. Existing output files are protected.

DXT5 is lossy. Specular, roughness, metallic, emission, shape keys, multiple populated LODs and specialized GTA shader behavior are outside this merge workflow. CodeWalker XML export has been tested; actual GTA V rendering and native binary YDR/YTD export have not been verified. See [validation](docs/VALIDATION.md).

## Development

Source is ordinary Blender add-on Python. For standalone DDS regression checks, install NumPy and Pillow and run `python tests/test_dds.py`. To build an installation ZIP from a Git checkout, run `python tools/build_release.py`; the archive is written to `dist/`.

Report problems through [Issues](https://github.com/Exodus2597/material-combiner-gta/issues), including Blender/Sollumz/add-on versions and the selected atlas settings. Do not upload private or unlicensed source assets.

## Credits and licensing

Original author: **shotariya**. Upstream repository: **Grim-es/material-combiner-addon**. GTA edition maintained under **Exodus2597**.

The upstream [LICENSE](LICENSE) contains GPL-3.0. Some upstream source files also carry MIT notices; those notices and original copyright credits are retained. This repository preserves the upstream licensing materials. [Original upstream documentation](docs/UPSTREAM.md) is included for attribution and the legacy workflow.

Tested game-export fixtures, GLB models and their textures are not included in this repository or its releases.
