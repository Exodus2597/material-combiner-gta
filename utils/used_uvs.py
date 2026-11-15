"""Pack evaluated source UV islands by mesh surface area, before DDS baking."""

import bpy
import numpy as np


def uv_coords(layer):
    coords = np.empty((len(layer.uv), 2), dtype=np.float32)
    layer.uv.foreach_get("vector", coords.ravel())
    return coords


def prepare_uvs(objects, atlas_uv, source_uvs):
    """Give materials comparable texel density and separate their packing inputs."""
    offset = 0.0
    tangent_uvs = {}
    for obj in objects:
        mesh = obj.data
        object_name, render_uv, material_uvs = source_uvs[obj]
        points = np.empty((len(mesh.vertices), 3), dtype=np.float32)
        mesh.vertices.foreach_get("co", points.ravel())
        # Translation does not affect area; scale and shear do.
        points = points @ np.asarray(obj.matrix_world.to_3x3(), dtype=np.float64).T
        loop_vertices = np.empty(len(mesh.loops), dtype=np.int32)
        mesh.loops.foreach_get("vertex_index", loop_vertices)
        mesh.calc_loop_triangles()
        triangles = np.empty((len(mesh.loop_triangles), 3), dtype=np.int32)
        mesh.loop_triangles.foreach_get("loops", triangles.ravel())
        indices = np.empty(len(triangles), dtype=np.int32)
        mesh.loop_triangles.foreach_get("material_index", indices)
        world_tri = points[loop_vertices[triangles]]
        area = np.linalg.norm(np.cross(world_tri[:, 1] - world_tri[:, 0],
                                       world_tri[:, 2] - world_tri[:, 0]), axis=1)
        layers = {}
        for name in {render_uv}.union(*material_uvs.values()):
            if name not in mesh.uv_layers:
                raise ValueError(f"{object_name}: missing source UV map '{name}' after modifiers")
            uv = uv_coords(mesh.uv_layers[name])
            source_tri = uv[triangles].astype(np.float64)
            a, b = source_tri[:, 1] - source_tri[:, 0], source_tri[:, 2] - source_tri[:, 0]
            layers[name] = (uv, abs(a[:, 0] * b[:, 1] - a[:, 1] * b[:, 0]))
        packed = np.empty((len(mesh.loops), 2), dtype=np.float32)
        all_loops = {}
        for face in mesh.polygons:
            all_loops.setdefault(face.material_index, []).extend(face.loop_indices)
        for index, loops in all_loops.items():
            material = obj.material_slots[index].material
            explicit = material_uvs[material]
            candidates = sorted(explicit | {render_uv}, key=lambda name: (name not in explicit, name != render_uv, name))
            faces = (indices == index) & (area > 0)
            coverage = {name: faces & (layers[name][1] > 1e-14) for name in candidates}
            source = max(candidates, key=lambda name: area[coverage[name]].sum())
            uv, uv_area = layers[source]
            use = coverage[source]
            if not use.any():
                maps = "', '".join(candidates)
                raise ValueError(f"{object_name}: material '{material.name}' has no usable UV area in '{maps}'. "
                                 "Check the material's UV maps or try Unwrap Geometry.")
            # Preserve implicit tangent UVs when the render layer covers these faces.
            if not coverage[render_uv].any():
                tangent_uvs[material] = source
            coords = uv[loops].astype(np.float64)
            coords = (coords - coords.min(0)) * np.sqrt(area[use].sum() / uv_area[use].sum())
            coords[:, 0] += offset
            packed[loops] = coords
            # Do not weld adjacent UVs that belong to different bake materials.
            offset = float(coords[:, 0].max()) + max(float(np.ptp(coords, axis=0).max()), 1e-6)
        if not np.isfinite(packed).all():
            raise ValueError(f"{object_name}: UV scale is too large to pack")
        mesh.uv_layers[atlas_uv].uv.foreach_set("vector", packed.ravel())
    return tangent_uvs


def pack_used_uvs(context, objects, atlas_uv, margin, source_uvs):
    tangent_uvs = prepare_uvs(objects, atlas_uv, source_uvs)
    settings = context.scene.tool_settings
    sync = settings.use_uv_select_sync
    selection_mode = tuple(settings.mesh_select_mode)
    try:
        settings.use_uv_select_sync = True
        bpy.ops.object.mode_set(mode="EDIT")
        bpy.ops.mesh.reveal(select=True)
        bpy.ops.mesh.select_all(action="SELECT")
        # Separate stacks of disconnected islands so different surface normals
        # cannot overwrite one another in the intermediate world-normal bake.
        if bpy.ops.uv.pack_islands(udim_source="ACTIVE_UDIM", rotate=True, rotate_method="CARDINAL",
                                   scale=True, merge_overlap=False,
                                   shape_method="CONCAVE", margin_method="FRACTION", margin=margin) != {"FINISHED"}:
            raise RuntimeError("Used UV island packing failed")
    finally:
        if context.mode == "EDIT_MESH":
            bpy.ops.object.mode_set(mode="OBJECT")
        settings.use_uv_select_sync = sync
        settings.mesh_select_mode = selection_mode
    # ACTIVE_UDIM may use the current UV editor's tile. Normalize to the atlas tile.
    layers = [obj.data.uv_layers[atlas_uv] for obj in objects]
    arrays = [uv_coords(layer) for layer in layers]
    low = np.min([uv.min(0) for uv in arrays], axis=0)
    high = np.max([uv.max(0) for uv in arrays], axis=0)
    tile = np.floor(low + (high - low) / 2)
    if not np.isfinite([low, high]).all() or (low - tile < -1e-5).any() or (high - tile > 1.00001).any():
        raise ValueError("UV islands cannot fit; reduce Island Gutter or increase the atlas sizes")
    for layer, uv in zip(layers, arrays):
        if np.any(tile):
            uv -= tile
        layer.uv.foreach_set("vector", np.clip(uv, 0, 1).ravel())
    return tangent_uvs
