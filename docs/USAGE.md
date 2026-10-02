# Import and merge

## Import GLB with textures

1. Open **N → MatCombiner → Import GLB + Textures** and choose a `.glb` file.
2. Set **Texture Export Folder** to the export root containing the model, material JSON sidecars and texture directories. Leave it empty to infer the root from an Unreal-style `Content` directory.
3. Keep **Source Normal Convention: Automatic** for Unreal JSON exports, or select the actual source convention explicitly.
4. Enable **Pack Images into Blend** to keep imported textures with the blend file.

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
8. Run the operation. Baking uses CPU Cycles; larger textures need more memory and bake time.

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
- One merged model, one material and exactly one `UVMap 0`, with **all vertex groups and weights removed**.
- A Sollumz **Drawable → Drawable Model** hierarchy. `DiffuseSampler` and optional `BumpSampler` are marked embedded; BumpSampler uses Non-Color.
- White `Color 1` prevents source vertex colors already baked into the texture from applying a second tint.

Normal export selects `normal.sps`, `normal_cutout.sps` or `normal_alpha.sps` for Opaque, Cutout or Alpha. Disabling normal export selects `default.sps`, `cutout.sps` or `alpha.sps`.

Both atlases share normalized UV rectangles even when their resolutions differ. Keep Material Texture Sheets preserves existing overlaps within each material. If overlapping faces need different geometry-dependent shading, choose Unwrap Geometry to give them separate space. Repeated UVs outside 0..1 retain their tiled range in expanded rectangles.

Source models keep their geometry, UVs, materials and weights. **Hide Source Models** controls whether successful merges hide originals in this view layer and renders. Failures restore selection and remove temporary data; existing DDS files are protected. Blender Undo restores scene changes, but exported files remain on disk.

## Export through Sollumz

Select the new Drawable and export through Sollumz. CodeWalker XML export with both DDS references/files has been validated. This add-on does not automatically create YTD/YTYP files or install assets into GTA V.

For skeletal deformation, add the correct GTA vertex groups and weights and retarget the skeleton as required. Imported GLB weights stay only on original meshes; merged output deliberately starts without them.
