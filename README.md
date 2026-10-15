# Exodus' Material Combiner

A Blender add-on for importing textured GLB models and merging selected meshes into a readable texture atlas for **GTA V / Sollumz**.

Modified edition of [Shotariya's Material Combiner](https://github.com/Grim-es/material-combiner-addon), based on upstream commit `eed9ca2`. Tested with **Blender 5.2.1 LTS and Sollumz 2.9.0**.

**[Download the latest release](https://github.com/Exodus2597/material-combiner-gta/releases/latest)** · **[Installation](docs/INSTALLATION.md)** · **[Usage](docs/USAGE.md)**

## What this edition adds

- Import GLB models and attach external diffuse/normal textures through Unreal material JSON references or unambiguous name matching.
- Optionally remove all imported modifiers, including Armature, using the default-on import toggle. Existing scene objects remain untouched.
- Merge selected meshes into one Sollumz Drawable Model, one material and one `UVMap 0`.
- Keep whole material texture sheets and their original UV island arrangement. Flexible rectangular packing uses spare atlas space more efficiently.
- Export separate diffuse/opacity and tangent-normal DDS files using the same UV layout.
- Choose diffuse and normal resolutions independently, including **2048×2048 diffuse / 512×512 normals**.
- Choose **A8R8G8B8** or **DXT5 (BC3)** independently for each atlas, with complete mipmaps.
- Choose whether to keep vertex groups/rigging, set orange/black GTA vertex colors, and generate Medium/Low LODs with successive 0.6 Decimate ratios. All three toggles appear in the DDS save dialog and default off.
- Validate unsupported inputs and restore scene state after failed imports or merges.

The original PNG/PBR combining workflow remains available. See [added features and fixes](docs/FEATURES.md) and [changelog](CHANGELOG.md).

## Quick start

1. Enable Sollumz and disable previous Material Combiner editions.
2. Download **`material_combiner_gta_2_6_6.zip`** from [Releases](https://github.com/Exodus2597/material-combiner-gta/releases/latest). Install it through **Edit → Preferences → Add-ons → Install from Disk** and enable **Exodus' Material Combiner**. Restart Blender if an older version remains loaded.
3. Open **N → MatCombiner → Import GLB + Textures** to import a model and its maps, or select existing mesh objects in Object Mode.
4. Click **Merge Selected + DDS Atlas**, choose a new lowercase DDS filename and select sizes, formats, UV layout and shader.
5. Export the resulting Drawable through Sollumz.

DDS generation uses Blender's bundled NumPy. No external DDS converter is required for the GTA workflow.

Version 2.6.3 simplifies the panels: Donation/Discord/Pillow installer controls are removed, and update checks use stable releases from this repository.

## New in 2.6.6

The installed add-on is now named **Exodus' Material Combiner**. New controls are available directly in the import and DDS save dialogs:

| Dialog | Toggle | Default | Behavior |
| --- | --- | --- | --- |
| GLB import | Remove All Modifiers | On | Remove every modifier from newly imported objects, including Armature, without applying them. Vertex groups, weights and armature objects remain. |
| DDS save | Keep Vertex Groups (Rigging) | Off | Retain source group names and weights on the merged output and generated LODs. Compatible armatures are copied. |
| DDS save | Set GTA Vertex Colors | Off | Set byte color layers **Color 1: #FF8000FF** (orange) and **Color 2: #00000000** (transparent black), including on generated LODs. |
| DDS save | Generate Medium + Low LODs | Off | Decimate High to Medium at ratio **0.6**, then Medium to Low at **0.6**. High remains unchanged and active. |

**To keep a working rig:** turn **Remove All Modifiers off** during import, then turn **Keep Vertex Groups (Rigging) on** when merging. Retaining groups alone does not restore a removed armature modifier or retarget an imported skeleton to GTA.

Generated LODs occupy the Medium and Low slots on the same Sollumz Drawable Model and share its atlas material and UV layout. Target triangle counts are approximately **60% / 36% of High**; topology can limit reduction. The supplied SWAT model produced **31,308 High → 18,784 Medium → 11,270 Low** triangles. Both requested color layers remain on the Blender meshes; Sollumz exports channels used by the selected shader.

## Output and limits

The merge creates `name.dds`, optional `name_normal.dds`, and one merged model with one material and one UV map. Diffuse is sRGB with opacity in alpha; normals are Non-Color, DirectX (-Y), with opaque alpha. Both textures are marked embedded in the Sollumz material.

**Merged output has no vertex groups or weights by default.** Enable Keep Vertex Groups to retain them in High and generated LODs. A compatible armature is copied; retargeting and new weighting are not performed. Source meshes, UVs, materials and weights remain unchanged. Existing output files are protected.

DXT5 is lossy. Specular, roughness, metallic, emission, shape keys, merging inputs with multiple populated LODs and specialized GTA shader behavior are outside this workflow. CodeWalker XML export has been tested; actual GTA V rendering and native binary YDR/YTD export have not been verified. See [validation](docs/VALIDATION.md).

## Development

Report problems through [Issues](https://github.com/Exodus2597/material-combiner-gta/issues), including Blender/Sollumz/add-on versions and the selected atlas settings. Do not upload private or unlicensed source assets.

## Credits and licensing

Original author: **shotariya**. Upstream repository: **Grim-es/material-combiner-addon**. GTA edition maintained under **Exodus2597**.

The upstream [LICENSE](LICENSE) contains GPL-3.0. Some upstream source files also carry MIT notices; those notices and original copyright credits are retained. This repository preserves the upstream licensing materials. [Original upstream documentation](docs/UPSTREAM.md) is included for attribution and the legacy workflow.

Tested game-export fixtures, GLB models and their textures are not included in this repository or its releases.
