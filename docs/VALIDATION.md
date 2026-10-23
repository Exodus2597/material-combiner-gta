# Validation

Environment: Blender 5.2.1 LTS (`9e2066aef7ef`), Sollumz 2.9.0, its matching pure-Python szio 1.3.0.dev9. Tests ran in isolated background Blender processes without changing the user's installed add-ons. Pillow 11.0 independently decoded generated DDS data.

## Passed

- Release 2.7.0: installation ZIP registration/unregistration and standalone UI checks pass without Sollumz/Pillow. Packaged standalone and merge backfaces, kept rig/vertex colors/LODs, Fusilier/Clownfish, Sea Fan, Sea Anemone, Seaweed Wrack/Eel Grass, GLB imports and CodeWalker XML export pass in isolated Blender processes. DDS encoder checks pass independently under Python 3.11/Pillow, including A8R8G8B8, DXT5, opacity, normal mipmaps and a complete 2048 BC3 mip chain. External Cobra uses the locally patched Planet Zoo 2 setup described in installation requirements.

- Local 2.6.13 standalone backfaces: multiselection preserves object transforms, modifiers, object-linked materials, two UV sets, custom normals, weights, selection and active object. Nonuniform/reflected transforms retain the requested world-space offset. Unselected shared-mesh instances remain unchanged. Only the displayed Sollumz LOD changes, including correct LOD switching afterward. Shape-key, zero-scale and empty-mesh validation cancels without edits; injected failure on a second selected mesh removes all prepared copies and preserves both originals. Undo is registered. Packaged UI/operator checks cover the Misc. Tools button and meshes without UVs/materials or Sollumz/Pillow.

- Local 2.6.12 backface preview: Eel Grass High faces 1,924 → 3,848; Medium 1,154 → 2,308; Low 692 → 1,384. Original front geometry/UVs/colors and source objects remain unchanged. Backfaces share UVs and produce byte-identical diffuse/normal DDS files to the single-sided merge. Explicit back-facing-ray culling in a Cycles diagnostic shows increased coverage from front and rear. Three-LOD Sollumz/CodeWalker XML export passes. Separate checks verify negative-normal offsets, reversed winding, per-corner UV/color data, weights, inverted custom normals and temporary attribute cleanup. A posed rig with all mesh toggles enabled preserves deformation/weights, exact GTA colors and skinned LOD export at zero offset. Failure while adding Medium backfaces removes partial geometry, LODs and DDS files and restores selection. Existing merge-option regressions pass. Actual GTA V rendering remains untested.

- Local 2.6.11 OVL preview: both Aquatic Seaweed Wrack and Aquatic Grass Eel have green-only `pOpacity` maps (red/blue zero, green 0–255). Every imported material's alpha matches the source green channel pixel-for-pixel within 1/255. Wrack imports eight variants/8,601 triangles; eel grass imports three variants/3,461 triangles. Rendered PNGs have visible plant coverage and transparent backgrounds, and were visually inspected. DXT5 diffuse atlases retain opaque leaves and transparent gaps; normal DDS, Sollumz material, Medium/Low LODs, CodeWalker XML and original mesh/material preservation pass.

- Local 2.6.10 OVL preview: reproduced Magnificent Sea Anemone's unsupported format-4 error and missing `vertices` symptom. All three variants import as six body/tentacle meshes, 4,583 vertices and 3,322 triangles. Tests verify packed diffuse/normal images, opaque body materials, tentacle `pOpacity`, reconstructed positive-Z tentacle normals, DDS merge, Medium/Low LODs, source preservation and CodeWalker XML export. The render was inspected. Independent binary fixtures verify positions/UVs/multi-chunk index offsets, unchanged source bytes, game/version isolation and ten malformed-buffer cases. Quiet Cobra vertex errors propagate and temporary method overrides restore after failure. BC7 packing is inferred from channel values; exact game shader parity is not asserted.

- Local 2.6.9 OVL preview: reproduced the unmodified Cobra reader's `Ms2File.models_reader` failure at offset 1977 on Common Sea Fan. Static import now loads all three variants (268/344/390 vertices, 327/428/461 triangles), packed diffuse/normal textures and vegetation `pOpacity`; a render was visually checked. Merging all variants preserves sources and produces two DDS files, a Sollumz Drawable, Medium/Low LODs and valid CodeWalker XML. Fusilier/Clownfish imports, fin alpha and error rollback regressions pass. Adapter checks confirm bounds validation, propagation of geometry errors, restoration of Cobra methods and unchanged handling of other games/versions.

- Local 2.6.8 OVL preview: Fusilier's dedicated opacity map retains graded alpha below 50%, without a threshold in the imported material. The corrected render shows dorsal, anal and pelvic fin membranes. Merging with Alpha retains graded transparency in the DXT5 diffuse DDS and selects `normal_alpha.sps`; normal DDS, Medium/Low LODs and CodeWalker XML export pass. Fusilier/Clownfish import and scene-preservation checks pass again. Actual GTA V rendering remains untested.

- Local 2.6.7 OVL preview: automatic Cobra/Python discovery, direct Fusilier import (three highest-detail meshes, 1,793 triangles, three diffuse/two normal assignments), BC5 Z reconstruction and packed textures after temporary extraction cleanup pass. Imported meshes merge to 512 DXT5 diffuse/256 DXT5 normal DDS, a Sollumz Drawable and Medium/Low LODs; CodeWalker XML export includes both maps. Repeated imports preserve existing materials and objects. Clownfish OVL also imports. Invalid paths/runtime/Cobra folders, invalid archives and timeout handling preserve scene data and selection. Existing GLB import/texture/rollback tests pass. OVL import currently covers static geometry and basic diffuse/normal/opacity materials; skeletons/animations and specialized game shaders remain outside this path.

- Local 2.6.5 preview: supplied SWAT GLB imports with all new-object modifiers removed by default. Disabling Remove All Modifiers retains its armature modifier/binding. Group names, every vertex weight and rest coordinates match both import modes; existing objects/modifiers remain untouched. The cleaned import merges successfully to DDS while retaining groups when requested. Import error rollback, repeated imports and external texture setup regressions pass.

- Local 2.6.4 preview: default settings retain the previous group removal, white Color 1 and High-only output. New toggles preserve group names/weights across multi-mesh joining (including different source group orders), reproduce the original posed deformation, and set exact Color 1/2 sRGB bytes. Generated Medium/Low meshes preserve UVMap 0, the atlas material, weights and colors; test triangle counts are 448 → 268 → 160. Switching/exporting LODs introduces no duplicate group names. Failure after LOD creation removes new meshes/files and restores sources/selection. Existing merge, normal-bake and input-guard regressions pass.
- Supplied SWAT armor GLB with all three options passes source-data preservation, retained High weights, exact color layers, two DXT5 DDS files and Sollumz CodeWalker export of three skinned LODs. Triangle counts are 31,308 → 18,784 → 11,270.

- Version 2.6.3: packaged registration/unregistration and panel drawing pass in Blender 5.2.1 without Pillow. Credits show Exodus (original by shotariya); only the repository issue button remains. Main and embedded panels contain no installer/donation/Discord controls. Release checks use this repository's version tags, sort versions and exclude drafts/prereleases. Simulated newer/equal releases, empty/malformed responses and timeout handling pass. Before publication, live GitHub checks detected public 2.6.2 from 2.6.1 and correctly reported the newer local 2.6.3 build as up to date.

- Version 2.6.2 publishes repository documentation, retains upstream licensing materials and points help/issues/manual update notices at Exodus2597/material-combiner-gta. Packaged Blender registration validates the new version and updater configuration.

- Version 2.6.1 removes all vertex groups and per-vertex weights from the merged output after joining. Static meshes with empty/weighted groups, multiple rigged meshes and the actual supplied GLB pass. Source group names and every GLB vertex weight remain unchanged; source armatures remain intact. Saved example reopens with no output groups or weights.
- Version 2.6 supports independent diffuse/normal dimensions and independent A8R8G8B8/DXT5 formats. Defaults retain A8R8G8B8 and matching dimensions. Normal/world-normal bake margins scale with resolution; world-normal capture uses the larger atlas resolution.
- Independent Pillow decoding verifies DXT5 FourCC/linear-size headers, top-down rows, sRGB diffuse conversion, exact transparent/opaque alpha, interpolated alpha/color indices, rectangular/small blocks and every mip down to 1 Ã— 1. Flat neutral normals retain exact 128/128/255 RGB at every mip. Smooth color/alpha gradients cross encoder chunk boundaries with RMS error below 3/255. Transparent-edge mip filtering remains linear-light and alpha-aware. Unsupported formats are rejected.
- A 2048 DXT5 atlas with full mipmaps is 5,592,560 bytes, compared with 22,369,748 bytes for A8R8G8B8. Encoding a synthetic 2048 flat-normal atlas took 5.55 seconds on this machine.
- Blender/Sollumz integration passes for 2048 DXT5 diffuse / 512 A8R8G8B8 normals, 256 A8R8G8B8 diffuse / 1024 DXT5 normals, and 512 DXT5 diffuse / 256 DXT5 normals. Both textures load at their chosen sizes. World-normal direction survives mirrored/nonuniform transforms within 0.03 per encoded component; all source UV8 channels remain unchanged. Sollumz CodeWalker XML export copies both DDS files byte-for-byte.
- Version 2.5 enables flexible rectangles by default. Weighted atlas partitioning fills available space, preserves padding and keeps tiny maps in a small band. The previous aspect-preserving packer remains selectable.
- Supplied-model tile content coverage increases from 80.65% to 91.23% at the same 2048 resolution. All 93,924 UV corners still match a per-material positive scale and translation, now allowing different horizontal/vertical scale.
- Two synthetic model sheets pack as rectangles; complete used/unused RGB, alpha and DirectX normal samples remain correct. Three equal sheets demonstrate a greater-than-15-percentage-point coverage gain over fixed-aspect packing.
- Square, portrait/landscape and tiny-map cases preserve atlas bounds and separation between tiles. Existing mirrored/nonuniform normal-direction, source preservation, rollback and Sollumz export tests pass with flexible packing.

- Version 2.4 defaults to whole material sheets. Every supplied-model UV corner matches the original coordinates after only per-material scale/translation; islands are not rotated or unwrapped.
- Synthetic partial-UV triangle verifies the complete original texture sheet is exported, including unused regions, all RGB/alpha quadrants and matching DirectX normal pixels. Transparent diffuse regions retain full-strength normals.
- Non-rotating rectangle packing reuses the upstream binary tree packer, fits padded tiles inside the atlas, scales source resolutions together and leaves tiny maps small.
- Optional Smart UV Project still runs successfully. Existing multi-mesh, repeated UV, transformed normals and failure rollback checks pass with the new default layout.
- Constant JSON material color replaces the GLB default vertex-color link; the supplied Zipcuff diffuse tile now renders its specified linear RGB 0.055 rather than white.

- Registration and unregistration of all 17 Material Combiner classes, including GTA atlas and GLB import operators.
- Multiple selected meshes produce one material and one `UVMap 0`; single-mesh/single-material inputs also work.
- Translated, rotated and negatively scaled input geometry retains world-space vertex positions after joining.
- Different source UV-layer names and repeated UV ranges produce expected atlas samples on both meshes.
- RGB, alpha, image orientation, DDS masks, byte count and mipmap count match expected values.
- Actual packed PNG inputs retain color and opacity through the separate bake passes, within Blender's low-alpha image-decoding rounding.
- Existing Sollumz `normal_spec.sps` source material supplies color/opacity while unused samplers do not block diffuse-only baking.
- Opaque, cutout and alpha output shaders create successfully.
- Source mesh data, materials and UV coordinates remain unchanged; visibility follows the selected option.
- Compatible armature copies retain rig references; version 2.6.1 removes all merged vertex groups and weights while preserving source groups and weights.
- Static and rigged drawables export through Sollumz 2.9.0 to CodeWalker XML, with one embedded DDS copied byte-for-byte.
- A simulated file-publication failure after mesh joining removes output copies and temporary data, and restores selection and source visibility.
- Normal atlas roundtrip preserves shader world-space direction through rotated source UVs, mirrored/nonuniform transforms and joining; output samples match within 0.012 per encoded component.
- Normal output selects `normal.sps`, `normal_cutout.sps` or `normal_alpha.sps`, uses BumpSampler with Non-Color images, DirectX green orientation and opaque alpha.
- Normal DDS decoding confirms flat normals encode as 128/128/255 without sRGB conversion. Vector mipmaps average and normalize correctly.
- Simulated failure publishing the second DDS removes the first published file and restores object, mesh, material, image and node-group counts.
- Linked missing normal images and eight referenced UV channels are rejected. Existing normal DDS files remain unchanged. Private normal node-group copies are removed after success/failure; source groups and fake-user flags remain unchanged.
- Actual supplied `Skinning_SWAT_Body_Armor_Paz_v02.glb` imports with five correctly matched diffuse textures, six normal textures and one constant base color. Unreal material JSON paths identify textures exactly; all imported images are packed.
- Its 31,308 source triangles, eight UV channels, original material references and vertex coordinates remain unchanged. Version 2.6 example output has one material and one `UVMap 0`, a 2048 A8R8G8B8 diffuse DDS with 12 mip levels and a 512 DXT5 normal DDS with 10 mip levels. Blender decodes varying normal RGB with opaque alpha; independent Pillow decoding verifies both files.
- Its rigged output exports successfully through Sollumz 2.9.0 to CodeWalker XML with both diffuse and normal DDS references/files. A self-contained example blend is included.
- Saved example reopens with packed 2048 diffuse / 512 normal atlas images, eight original source UV channels and source skin weights. Merged output has no vertex groups or weights.
- Malformed JSON and escaping texture paths roll back all GLB-created objects, meshes, armatures, materials, images, actions and collections and restore selection. Ambiguous texture matching and absolute/traversal paths are rejected.
- Repeated GLB imports resolve Blender-suffixed material names without editing previously imported materials. Bone widgets are excluded from selected models.
- Missing output directories, existing DDS files, invalid names, Edit Mode, non-finite UVs, zero-scale transforms, missing materials, shape keys and extra LOD meshes are rejected.
- Edit Mode remains active after an Edit Mode validation error.
- Geometry modifiers apply to copies; source modifiers and original LOD remain unchanged. Output contains only the HIGH LOD.
- External bake-target preferences and render engine/Cycles settings are preserved.
- Copied materials and meshes with inherited fake-user flags are cleaned up; source fake-user flags remain unchanged.
- Original PNG workflow preserves source UVs and slots when atlas saving fails, then succeeds on retry; direct execution, image resizing and unregister cleanup pass regression checks.
- Nine independent DDS checks cover square/rectangular/1Ã—1 dimensions, Pillow decoding, vertical orientation, complete mip-chain sizes, transparent-edge mip filtering and invalid buffer rejection.
- Python compilation and whitespace checks pass.
- The packaged ZIP imports, registers its GTA operator without Pillow, and unregisters successfully in a fresh Blender process. The patch applies cleanly against the upstream commit.

The diffuse-only synthetic `normal_spec.sps` test with unassigned ancillary images produces Cycles image-loading warnings; sampled diffuse/opacity data passes. Normal export validates linked normal textures; specular inputs are outside the atlas workflow.

CodeWalker source inspection confirms that its texture XML importer reads the DDS and replaces placeholder XML width, height, format and mip-count values with the actual DDS metadata. Its texture format enumeration includes `D3DFMT_A8R8G8B8`. [CodeWalker Texture.cs](https://github.com/dexyfex/CodeWalker/blob/master/CodeWalker.Core/GameFiles/Resources/Texture.cs)

## Verification limits

- Supplied GLB and texture export were tested; GTA skeleton retargeting was not performed.
- Actual GTA V rendering and CodeWalker application import were not run.
- Native binary YDR/YTD export was not tested; CodeWalker XML export was tested.
- DXT5 is lossy; visual quality depends on source detail and chosen resolution. Actual GTA V rendering of the new compressed output was not run. BC1/BC5 output is not offered.
- Shape keys, multiple LODs and specialized GTA shaders are outside the supported merge scope.

Installation archive includes source and licensing. `material_combiner_gta_changes.patch` records modifications against upstream commit `eed9ca2`.
