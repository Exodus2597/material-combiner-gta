# Import and merge

## Misc. Tools — Create Backfaces

1. In Object Mode, select the mesh objects to edit.
2. Open **N → MatCombiner → Misc. Tools → Create Backfaces**.
3. Set **Backface Offset** (default **0.0001 Blender world units**) and confirm. Zero is supported. Object transforms are retained, including nonuniform and mirrored scale.

The standalone tool appends reversed, slightly offset faces directly to the selected meshes. Each run doubles the face count. It retains UVs, colors, weights, custom normals, materials, material culling settings and modifiers; no DDS files, texture baking or material merging are involved. Unselected objects sharing the original mesh stay unchanged. Use **Undo** to revert. Shape-key meshes are rejected to protect their data. With unapplied modifiers, this edits the underlying base mesh.

For Sollumz models, only the current/displayed LOD is edited. Switch LODs before running it on another level. The merge-dialog backface option continues to cover High and generated Medium/Low together. The standalone tool works without Sollumz, Cobra or Pillow and accepts meshes without UVs/materials.

## Import OVL with textures

1. Install Cobra Tools and Python 3.11 with Cobra's dependencies (`numpy`, `Pillow`, `imageio`, plus any dependencies required by your Cobra version). OVL extraction also uses Cobra's existing texture converter. The tested Planet Zoo 2 setup uses Cobra Tools 2026.10.11 with local format-54 patches for archive/game detection, model decoding and texture extraction. These external Cobra patches are not bundled; an unmodified Cobra installation is not validated for Planet Zoo 2. The add-on's Sea Fan/foliage adapters do not replace that dependency. Updating Cobra may remove local patches. See [installation requirements](INSTALLATION.md#ovl-requirements).
2. Open **N → MatCombiner → Import OVL + Textures** and select an `.ovl`. Leave matching `.ovs` and `.aux` files beside it. Source game files are read only; extraction uses a temporary folder.
3. **Source Game → Automatic** uses Cobra detection, including the original Planet Zoo 2 folder path. Choose the game explicitly if you moved an archive out of its game directory.
4. Leave **Shared Textures OVL** and **Shared Texture Folder** empty when all required textures are in the main archive. Otherwise select the second archive or a folder containing already extracted Cobra PNGs. FGM references choose the actual textures; ambiguous or missing required maps cancel import.
5. Leave **Invert Normal Green** off for Cobra-converted normal maps. Enable it only when the imported normals need the opposite green convention. BC5 X/Y maps receive a reconstructed Z channel before import.
6. **Advanced Paths** optionally sets **Cobra Tools Folder** and **Python Executable** if automatic detection cannot locate your installation. The Cobra folder must contain `generated` and `modules`.
7. After import, the highest-detail static mesh parts are selected in the current scene. Diffuse, normal and supported opacity maps are connected to Principled materials and packed into the blend. Use **Merge Selected + DDS Atlas** exactly as for GLB models.

Dedicated opacity maps retain graded transparency, including translucent fish fins. When merging these models, choose **Shader → Alpha** to retain that transparency in Sollumz. **Cutout** applies a hard alpha test and can hide translucent surfaces; **Opaque** ignores transparency.

Some PZ2 foliage stores `pOpacity` entirely in green, with an empty red channel. The importer uses green in that case; reading red would make every leaf transparent. Aquatic Seaweed Wrack and Aquatic Grass Eel are tested. Restart Blender and reimport after updating from 2.6.10 or earlier to replace affected imported materials.

Planet Zoo 2 format-54 static imports skip the separate bone block using its declared byte size. This avoids Cobra's vegetation bone-reader failure on Common Sea Fan without modifying Cobra or bypassing geometry decoding. The archive contains three model variants; all three import and are selected. Deselect or delete unwanted variants before merging. Vegetation's `pOpacity` map is supported; wind, collisions and skeletons are not imported.

PZ2's format-4, 32-byte foliage vertices are supported for static geometry. Magnificent Sea Anemone imports three variants, each with a body and tentacle mesh. Keep both parts of the variant you want selected before merging. Malformed/unsupported vertex data stops extraction with its decoder error. For PZ2 BC7 normals whose blue channel is entirely below neutral, the importer infers packed X/Y data and reconstructs positive Z. The anemone render was checked; this does not reproduce the game's complete material shader.

OVL import creates static geometry, not a skeleton or animation. It does not recreate fur, iridescence, material variants or every specialized game shader. Meshes without a referenced normal texture use their geometric normals. Unused unsupported maps are not extracted. Original archive data and existing scene objects/materials remain unchanged. The GLB workflow remains available without Cobra or an external Python installation.

## Import GLB with textures

1. Open **N → MatCombiner → Import GLB + Textures** and choose a `.glb` file.
2. Set **Texture Export Folder** to the export root containing the model, material JSON sidecars and texture directories. Leave it empty to infer the root from an Unreal-style `Content` directory.
3. Keep **Source Normal Convention: Automatic** for Unreal JSON exports, or select the actual source convention explicitly.
4. Enable **Pack Images into Blend** to keep imported textures with the blend file.
5. **Remove All Modifiers** is enabled by default. It removes modifiers, including Armature, from newly imported objects without applying them. Vertex groups, weights and armature objects remain. Turn this off to retain armature deformation, including when you intend to keep a working rig through the merge option.

JSON references identify diffuse and normal textures by their exported paths. Without JSON, external textures can match material names with `_B`, `_D`, `_Diffuse`, `_BaseColor`, `_Albedo`, `_N`, `_Normal` or `_Normals` suffixes. Missing explicitly referenced files and ambiguous matches cancel import and restore the previous scene. Ordinary GLB materials retain embedded textures.

Unreal DirectX normals have their green channel flipped for Blender's Normal Map node. Source diffuse textures use sRGB; source normal textures use Non-Color. Bone display widgets are excluded from selected meshes.

## Merge selected meshes

1. Switch to **Object Mode** and select the mesh objects to combine. The old material checklist applies only to the original PNG workflow.
2. Click **Merge Selected + DDS Atlas**.
3. Choose an existing output folder and a new lowercase `.dds` filename, using letters, digits and underscores, for example `my_prop.dds`.
4. Choose **Diffuse Size** and **Diffuse DDS Format**.
5. Enable **Export Normal DDS**, then choose **Normal Size** and **Normal DDS Format**. These controls are independent of diffuse settings.
6. Keep **UV Layout → Keep Material Texture Sheets** for a readable map. **Flexible Material Rectangles** fills spare space by resizing material sheets and their UVs together. Disable it to preserve original sheet aspect ratios. **Unwrap Geometry** uses Smart UV Project for fresh islands instead.
7. Choose padding and a shader. Padding is measured in diffuse pixels; normal bake margins scale with normal resolution.
8. Choose the optional mesh settings in the same DDS save dialog:
   - **Keep Vertex Groups (Rigging)** retains source group names and weights in the merged copy. Compatible rigged inputs retain a copied armature; no retargeting or new weighting is performed. Disabled by default, which removes all output groups and weights.
   - **Set GTA Vertex Colors** creates byte color layers **Color 1: #FF8000FF** (orange) and **Color 2: #00000000** (transparent black). Values use sRGB bytes, including green = 128. Disabled by default, which retains the previous white Color 1 output.
   - **Generate Medium + Low LODs** uses Collapse Decimate at ratio **0.6** for Medium from High, then **0.6** for Low from Medium. Targets are approximately 60% and 36% of High's triangle count; actual counts depend on topology. High remains unchanged and active. Disabled by default.
   - **Create Backfaces (Two-Sided Mesh)** adds reversed copies behind the original faces so thin leaf cards render from either side with backface culling. **Backface Offset** defaults to **0.0001 Blender units**; choose a smaller value or zero when needed. Copies move opposite the original vertex normals and retain UVs, material, colors, weights and reversed custom normals. Backfaces are added after baking and LOD decimation to High and generated Medium/Low meshes. The atlas size stays unchanged; face count doubles. Disabled by default. It applies to every face in the selected output, so select the foliage you want to process. Source objects remain unchanged.
9. Run the operation. Baking uses CPU Cycles; larger textures need more memory and bake time.

Example settings:

| Setting | Value |
| --- | --- |
| Diffuse Size | 2048 × 2048 |
| Diffuse DDS Format | A8R8G8B8 |
| Export Normal DDS | Enabled |
| Normal Size | 512 × 512 |
| Normal DDS Format | DXT5 (BC3) |
| UV Layout | Keep Material Texture Sheets |
| Flexible Material Rectangles | Enabled |

With full mipmaps, a 2048 atlas is about 21.3 MiB in A8R8G8B8 or 5.3 MiB in DXT5. A 512 DXT5 normal atlas is about 341.5 KiB. DXT5 is lossy; it can introduce visible normal-map artifacts.

## Output

- `my_prop.dds`: sRGB base color with opacity in alpha.
- `my_prop_normal.dds`: optional linear tangent normals, GTA DirectX (-Y), opaque alpha.
- One merged model, one material and exactly one `UVMap 0`. Vertex groups and weights are removed unless **Keep Vertex Groups (Rigging)** is enabled.
- A Sollumz **Drawable → Drawable Model** hierarchy. `DiffuseSampler` and optional `BumpSampler` are marked embedded; BumpSampler uses Non-Color.
- White `Color 1` prevents source vertex colors already baked into the texture from applying a second tint. **Set GTA Vertex Colors** replaces this with the requested orange Color 1 and transparent black Color 2.
- Optional Medium and Low meshes appear in the model's Sollumz LOD slots, sharing its material and atlas UV layout. Retained weights and chosen vertex colors carry into both LODs. No Very High/Very Low meshes are generated. Very small meshes may not reduce further.

Normal export selects `normal.sps`, `normal_cutout.sps` or `normal_alpha.sps` for Opaque, Cutout or Alpha. Disabling normal export selects `default.sps`, `cutout.sps` or `alpha.sps`.

Both atlases share normalized UV rectangles even when their resolutions differ. Keep Material Texture Sheets preserves existing overlaps within each material. If overlapping faces need different geometry-dependent shading, choose Unwrap Geometry to give them separate space. Repeated UVs outside 0..1 retain their tiled range in expanded rectangles.

Source models keep their geometry, UVs, materials and weights. **Hide Source Models** controls whether successful merges hide originals in this view layer and renders. Failures restore selection and remove temporary data; existing DDS files are protected. Blender Undo restores scene changes, but exported files remain on disk.

## Export through Sollumz

Select the new Drawable and export through Sollumz. CodeWalker XML export with both DDS references/files has been validated. This add-on does not automatically create YTD/YTYP files or install assets into GTA V.

Enable **Keep Vertex Groups (Rigging)** to retain imported GLB weights in the merged model and generated LODs. GTA skeleton compatibility and retargeting remain separate steps. When this option is off, merged output starts without weights. Sollumz exports the vertex color channels used by the selected shader; both requested color layers remain available on the Blender meshes.
