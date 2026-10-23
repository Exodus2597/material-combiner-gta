# Exodus' Material Combiner

A Blender add-on for importing textured OVL/GLB models and merging selected meshes into a readable texture atlas for **GTA V / Sollumz**.

Modified edition of [Shotariya's Material Combiner](https://github.com/Grim-es/material-combiner-addon), based on upstream commit `eed9ca2`. Tested with **Blender 5.2.1 LTS and Sollumz 2.9.0**.

**[Download the latest release](https://github.com/Exodus2597/material-combiner-gta/releases/latest)** · **[Installation](docs/INSTALLATION.md)** · **[Usage](docs/USAGE.md)**

## What this edition adds

- Import GLB models and attach external diffuse/normal textures through Unreal material JSON references or unambiguous name matching.
- Import OVL models with Cobra Tools, resolve diffuse/normal/opacity textures from FGM references, and use the same DDS/Sollumz merge workflow.
- Optionally remove all imported modifiers, including Armature, using the default-on import toggle. Existing scene objects remain untouched.
- Merge selected meshes into one Sollumz Drawable Model, one material and one `UVMap 0`.
- Keep whole material texture sheets and their original UV island arrangement. Flexible rectangular packing uses spare atlas space more efficiently.
- Export separate diffuse/opacity and tangent-normal DDS files using the same UV layout.
- Choose diffuse and normal resolutions independently, including **2048×2048 diffuse / 512×512 normals**.
- Choose **A8R8G8B8** or **DXT5 (BC3)** independently for each atlas, with complete mipmaps.
- Choose whether to keep vertex groups/rigging, set orange/black GTA vertex colors, and generate Medium/Low LODs with successive 0.6 Decimate ratios. All three toggles appear in the DDS save dialog and default off.
- Add two-sided geometry during merging or separately through **Misc. Tools → Create Backfaces**, with an adjustable offset.
- Validate unsupported inputs and restore scene state after failed imports or merges.

The original PNG/PBR combining workflow remains available. See [added features and fixes](docs/FEATURES.md) and [changelog](CHANGELOG.md).

## Quick start

1. Enable Sollumz and disable previous Material Combiner editions.
2. Download **`material_combiner_gta_2_7_0.zip`** from [Releases](https://github.com/Exodus2597/material-combiner-gta/releases/latest). Install it through **Edit → Preferences → Add-ons → Install from Disk** and enable **Exodus' Material Combiner**. Restart Blender if an older version remains loaded.
3. Open **N → MatCombiner → Import GLB + Textures** to import a model and its maps, or select existing mesh objects in Object Mode.
4. Click **Merge Selected + DDS Atlas**, choose a new lowercase DDS filename and select sizes, formats, UV layout and shader.
5. Export the resulting Drawable through Sollumz.

DDS generation uses Blender's bundled NumPy. No external DDS converter is required for the GTA workflow.

## New in 2.7.0

### OVL models and textures

Open **N → MatCombiner → Import OVL + Textures**, select an `.ovl` and keep its `.ovs`/`.aux` companions beside it. The importer locates highest-detail static meshes and their FGM-referenced diffuse, normal and supported opacity textures, packs the images into Blender, and selects the imported meshes. Use **Merge Selected + DDS Atlas** to create the Sollumz Drawable, DDS maps and optional Medium/Low LODs, just as with GLB imports.

**OVL requires external Cobra Tools and Python 3.11 with Cobra's dependencies and texture converter.** Paths are detected where possible and can be set under **Advanced Paths**. The tested Planet Zoo 2 installation uses **Cobra Tools 2026.10.11 with local Planet Zoo 2 format-54 patches**; those external patches are **not bundled** in this release. An unmodified Cobra installation is not validated for Planet Zoo 2. GLB import, DDS merging and standalone backfaces do not require Cobra. See [OVL requirements](docs/INSTALLATION.md#ovl-requirements).

**Shared Textures OVL** and **Shared Texture Folder** can supply maps stored outside the selected archive. **Source Game** overrides automatic detection for moved archives. Missing or ambiguous required textures cancel import. Source archives remain unchanged.

This release also fixes:

- **Fusilier fins:** preserve graded opacity rather than clipping fin membranes at 50%. Choose **Shader → Alpha** when merging translucent fins; Cutout applies a hard threshold.
- **Common Sea Fan:** handle its separate vegetation bone block during static decoding and recognize `pOpacity` maps.
- **Magnificent Sea Anemone:** decode its 32-byte foliage vertices and reconstruct inferred packed normal maps to correct dark tentacle shading.
- **Aquatic Seaweed Wrack and Aquatic Grass Eel:** read green-only `pOpacity` masks so foliage stays visible while leaf gaps remain transparent.

OVL import covers static geometry and basic texture materials. Skeletons, animation, wind, collisions and complete game shaders are outside this workflow. Other archives depend on Cobra's decoding support; packed BC7 normal detection is inferred. Reimport models created with earlier previews to receive material fixes. See [OVL usage](docs/USAGE.md#import-ovl-with-textures).

### Two-sided meshes for foliage

Enable **Create Backfaces (Two-Sided Mesh)** in the DDS save dialog to append reversed faces behind the originals. **Backface Offset** defaults to **0.0001 Blender units** and supports zero. UVs, colors, weights and reversed custom normals are retained; both sides share the same DDS atlas. Backfaces are added after baking and decimation to High and generated Medium/Low LODs. The toggle defaults off and source objects remain unchanged.

For existing meshes, use **N → MatCombiner → Misc. Tools → Create Backfaces** in Object Mode. This standalone tool edits selected base meshes without merging, baking or exporting. It preserves materials, modifiers and transforms, protects unselected linked instances, supports Undo and measures offset in Blender world units. On Sollumz models it edits **only the currently displayed LOD**; switch LODs to process another level.

**Each run doubles face count.** Use once per mesh/LOD; this adds reversed surfaces, not edge walls. Shape-key meshes are rejected. The standalone tool requires only Blender and accepts meshes without UVs or materials. See [backface usage](docs/USAGE.md#misc-tools--create-backfaces).

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
