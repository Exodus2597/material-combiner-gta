# GTA edition additions

The original Material Combiner PNG workflow remains available. This edition adds a separate GTA/Sollumz workflow to the viewport sidebar.

| Addition | Behavior |
| --- | --- |
| GLB import with external textures | Blender's GLB importer loads geometry; material JSON or unambiguous name matching attaches diffuse and normal maps. Images can be packed into the blend. |
| One merged mesh | All selected mesh objects become one output copy with one material and a Sollumz Drawable hierarchy. |
| One UV map | Output retains exactly `UVMap 0`. Source UV layers remain intact. |
| Readable material sheets | Whole original texture sheets move into atlas tiles through scale and translation. Original island arrangement is preserved, including unused texture areas and repeated UV ranges. |
| Flexible rectangles | Weighted rectangular packing uses spare space more effectively. Textures and UVs resize together; tiny source textures use a small band. Original-aspect packing remains selectable. |
| Diffuse DDS | Base color and opacity become one sRGB diffuse atlas. |
| Separate normal DDS | Tangent normals become a Non-Color DirectX (-Y) atlas using the same normalized UV rectangles. Transform-sensitive normals rebake into the final tangent frame. |
| Independent dimensions | Diffuse and normal sizes are selected independently: 256, 512, 1024, 2048 or 4096 square pixels. Normal Size defaults to Match Diffuse. |
| Independent DDS formats | Each atlas can use uncompressed A8R8G8B8 or lossy DXT5 (BC3). Defaults remain A8R8G8B8. |
| Complete mipmaps | Diffuse mipmaps filter linear color with premultiplied alpha; normal mipmaps average and normalize vectors before encoding. Both reach 1×1. |
| Vertex-group cleanup | Every group and weight is removed from the merged output after modifiers and joining. Source groups and weights remain intact. |
| Data protection | Source geometry, UVs and materials remain unchanged. Existing outputs are never overwritten. Failed merges remove temporary copies and incomplete output files. |

## Fixes

- Preserve source UV references during baking, including implicit texture coordinates and private normal-node groups.
- Apply enabled geometry modifiers on copies and preserve original objects, LODs, bake preferences and render settings.
- Handle negative/nonuniform transforms when converting normal maps to the final tangent frame.
- Keep transparent diffuse materials from weakening normal baking.
- Correct constant-color materials imported from JSON and resolve repeated imports with Blender-suffixed names.
- Validate texture paths, missing images, ambiguous references, invalid UVs, zero scale and unsupported mesh/rig arrangements before losing data.
- Restore selection and scene data after failed imports or merges.
- Fix legacy workflow validation, image resizing and save-failure handling.

## Scope and limits

- GTA output includes diffuse/opacity and optional normals. Specular, roughness, metallic and emission are not included in the GTA bake.
- Shape keys, multiple populated LOD meshes, incompatible armatures, mixed static/rigged selections and certain modifier orders are rejected.
- Specialized vehicle, cloth and light-map shader behavior is not recreated.
- The merged mesh is **unweighted**. A copied compatible armature can remain in the Drawable hierarchy, but no skeleton retargeting or new weighting is performed.
- DXT5 and lower resolutions can reduce detail. Choose A8R8G8B8 when preserving baked normal values matters more than file size.
- Blender/Sollumz CodeWalker XML export has been tested. Actual GTA V rendering, CodeWalker application import and native binary YDR/YTD export have not been verified.
- Tested game-export fixtures are not distributed with the repository.
