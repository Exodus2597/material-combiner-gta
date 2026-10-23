# Changelog

## 2.7.1 — 2026-10-23

- Bundle the patched Cobra Tools 2026.10.11 static decoder, Planet Zoo 2 format-54 fixes, texconv and pinned Pillow/imageio/bitarray libraries for Windows x64 / CPython 3.13.
- Use Blender's own Python in an isolated worker by default. Remove installed-Cobra discovery and external Python 3.11 setup from normal OVL import; no pip, dependency downloads or Python environment changes occur during use.
- Locate the existing game's Oodle DLL in game root/Win64 folders around `ovldata`; add an optional Advanced Paths → Oodle Library override for copied archives. Do not redistribute or modify the proprietary DLL.
- Verify runtime SHA256 and archive paths before temporary extraction, retain source/licenses/provenance and add a deterministic runtime build tool.
- Preserve all 2.7.0 OVL texture/foliage fixes, DDS/Sollumz merging and backface tools. Document the one-ZIP setup, platform support and game-DLL requirement.

## 2.7.0 — 2026-10-23

- Publish the cumulative 2.6.7–2.6.13 previews as the stable OVL/backfaces release.
- Add static OVL import with diffuse/normal/opacity textures, shared texture sources and configurable external Cobra/Python paths; integrate the DDS/Sollumz merge and LOD workflow.
- Fix Fusilier fin transparency, Common Sea Fan bone-block decoding, Magnificent Sea Anemone foliage vertices/normal shading and green-only foliage opacity for Seaweed Wrack/Eel Grass.
- Add optional backfaces to merged High/Medium/Low output and standalone **Misc. Tools → Create Backfaces**, with adjustable offsets, preserved mesh data, source protection and rollback.
- Update installation, usage and README documentation, including external Planet Zoo 2 Cobra patch requirements and static-import/export limits.

## 2.6.13 — Local preview, 2026-10-22

- Add **MatCombiner → Misc. Tools → Create Backfaces** as a standalone operator. Select meshes in Object Mode and set the offset in its dialog; no atlas merge, texture bake or export is required.
- Reuse the existing backface geometry helper with world-space offset support for scaled/mirrored objects. Preserve object transforms, modifiers, materials, UVs, colors, weights and custom normals. Selected objects receive private mesh copies so unselected linked instances stay unchanged.
- Edit the active mesh/current Sollumz LOD only. Support Undo and validate all inputs before committing changes. Reject shape-key meshes, empty meshes, read-only objects and invalid coordinates/transforms; roll back all prepared copies on failure.

## 2.6.12 — Local preview, 2026-10-22

- Add **Create Backfaces (Two-Sided Mesh)** to the DDS merge dialog, disabled by default. Append reversed face copies displaced behind the originals along vertex normals; **Backface Offset** defaults to 0.0001 Blender units and supports zero.
- Reuse atlas UVs, diffuse/normal DDS, materials, colors, weights and custom corner normals. Add backfaces after baking and decimation to High and generated Medium/Low meshes. This doubles face count without allocating extra atlas space.
- Enable Blender material backface culling for the generated two-sided output. Source objects remain unchanged; failure during backface generation rolls back partial output and LODs.
- Verify Eel Grass with front/rear culling diagnostics, unchanged atlas bytes, paired LOD geometry and CodeWalker XML export. Rigging, GTA colors and zero-offset paired geometry also pass tests.

## 2.6.11 — Local preview, 2026-10-22

- Fix invisible PZ2 foliage when `pOpacity` stores its mask only in green. If red is empty and green contains data, use green for diffuse alpha. Preserve existing red/grayscale opacity handling.
- Verify Aquatic Seaweed Wrack and Aquatic Grass Eel: imported alpha matches the source mask, rendered plants are visible with transparent gaps, and DDS/Sollumz merging retains visibility.

## 2.6.10 — Local preview, 2026-10-22

- Support static Planet Zoo 2 format-54 foliage meshes using format 4: a 16-byte bounding box followed by 32-byte vertex records. Fix Magnificent Sea Anemone failing with `'ChunkedMesh' object has no attribute 'vertices'`.
- Validate chunk counts, buffer lengths, positions, UVs and local triangle ranges. Surface vertex-decoding errors that Cobra previously logged and swallowed; stop instead of importing incomplete meshes.
- Reconstruct positive Z from R/G for PZ2 BC7 normal textures whose entire blue channel lies below neutral. This inferred packed-map handling fixes dark anemone tentacles in the test render.
- Verify all three anemone variants (six meshes), diffuse/normal/opacity setup, DDS merging, Medium/Low LODs and CodeWalker XML export. Installed Cobra and original archives remain unchanged.

## 2.6.9 — Local preview, 2026-10-22

- Fix Planet Zoo 2 Common Sea Fan import failing at `Ms2File.models_reader`. During static format-54 import, skip the bounded, separately stored bone block that Cobra cannot decode for this vegetation asset. Other games and versions retain Cobra's original reader. Installed Cobra files are not modified.
- Recognize vegetation's `pOpacity` texture slot so coral transparency is attached and included in the diffuse DDS.
- Verify all three Common Sea Fan variants, DDS merging, Medium/Low LODs and CodeWalker XML export; retain Fusilier fin-opacity behavior.

## 2.6.8 — Local preview, 2026-10-19

- Preserve graded opacity from dedicated OVL opacity textures. Fix Fusilier fin membranes disappearing because the intermediate GLB material applied a hard 50% alpha cutoff.
- Use Alpha when merging translucent fins for Sollumz; Cutout intentionally clips partial transparency.

## 2.6.7 — Local preview, 2026-10-19

- Add Import OVL + Textures to the MatCombiner panel. Automatically locate MS2 models, FGM material references and required diffuse/normal/opacity textures in the selected archive.
- Use the installed Cobra Tools decoder and its external Python 3.11 runtime; game archives are read only. Import highest-detail static meshes into the current Blender scene through the existing GLB pipeline.
- Reconstruct BC5 normal-map Z, retain Cobra's PNG normal convention, embed textures and support optional shared archives/extracted texture folders.
- Support the existing DDS atlas, Sollumz conversion and optional Medium/Low LOD workflow for OVL geometry.
- Validate missing assets/dependencies, preserve existing scene data on failed/repeated imports and expose optional game/runtime path overrides.

## 2.6.6 — 2026-10-15

- Rename the installed add-on to Exodus' Material Combiner. Retain the original author credit and source licensing notices.

- Add Remove All Modifiers to the GLB import dialog, enabled by default.
- Remove modifiers only from newly imported objects without applying them; retain geometry, groups/weights and armature objects. Disable the toggle to keep the imported armature modifier and rig deformation.
- Add DDS save-dialog toggles to keep vertex groups/weights, set GTA vertex colors and generate Medium/Low LODs. All default off.
- Set Color 1 to exact sRGB bytes #FF8000FF and Color 2 to #00000000 when enabled.
- Generate Medium from High at Decimate ratio 0.6, then Low from Medium at ratio 0.6. Preserve High and leave it active.
- Keep compatible rigging, shared atlas material, UVs and vertex colors across generated LODs; restore sources and remove generated meshes on failure.

## 2.6.3 — 2026-10-02

- Show Created by Exodus (original by shotariya).
- Remove Discord, donations and Pillow installation panels and buttons.
- Check this repository's stable releases using version tags, excluding drafts and prereleases.
- Keep updates as manual release downloads.

## 2.6.2 — 2026-10-02

- Publish the GTA edition with installation, usage, feature and validation documentation.
- Point Blender documentation, issue reporting and update notices at this repository.
- Use manual release installation instead of replacing this edition with upstream archives.
- Retain the upstream GPL-3.0 license file and MIT notices present in individual files; correct the earlier MIT-only documentation.

## 2.6.1

- Remove every vertex group and weight from merged output, preserving source groups and weights.

## 2.6.0

- Add independent diffuse and normal atlas sizes.
- Add independent A8R8G8B8 and DXT5 (BC3) output formats, complete mipmaps and resolution-scaled normal bake margins.
- Preserve exact neutral flat normals in DXT5 encoding.

## Earlier GTA edition work

- Add GLB import with external diffuse/normal texture matching and Unreal material JSON support.
- Add merged Sollumz Drawables, one output UV map and diffuse/opacity plus normal DDS export.
- Preserve original material texture sheets and their UV island arrangement; add flexible rectangular packing.
- Preserve sources, validate unsupported inputs, handle transformed normal maps and roll back failed imports/exports.
- Fix validation, resizing and save-failure handling in the original workflow.

Based on upstream commit `eed9ca2` of [Grim-es/material-combiner-addon](https://github.com/Grim-es/material-combiner-addon).
