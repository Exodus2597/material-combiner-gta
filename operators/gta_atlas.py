"""Bake selected meshes to one DDS, one mesh and one Sollumz UV map.

Work happens on copies. Source geometry, UVs and materials are never edited.
"""

import importlib
import os
import re
import sys
import tempfile
import traceback
from pathlib import Path

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, IntProperty, StringProperty
from bpy_extras.io_utils import ExportHelper

from ..utils.dds import write_dds
from ..utils.material_tiles import arrange_material_tiles, tile_proxy

ATLAS_UV = "__smc_atlas"


def referenced_uvs(obj):
    render = next((u.name for u in obj.data.uv_layers if u.active_render),
                  obj.data.uv_layers.active.name)
    names = {render}
    available = {u.name for u in obj.data.uv_layers}
    visited = set()
    def visit(tree):
        if tree is None or tree in visited:
            return
        visited.add(tree)
        for node in tree.nodes:
            if (node.type == "UVMAP" or node.type == "NORMAL_MAP" and node.space == "TANGENT") and node.uv_map:
                names.add(node.uv_map)
            if node.type == "ATTRIBUTE" and node.attribute_name in available:
                names.add(node.attribute_name)
            if node.type == "GROUP":
                visit(node.node_tree)
    for slot in obj.material_slots:
        if slot.material:
            visit(slot.material.node_tree)
    return names, render


def pin_source_uvs(tree, uv_name, groups, memo):
    """Freeze implicit UV and tangent inputs before changing the baking UV."""
    uv_node = None
    def source_uv():
        nonlocal uv_node
        if uv_node is None:
            uv_node = tree.nodes.new("ShaderNodeUVMap")
            uv_node.uv_map = uv_name
        return uv_node.outputs[0]
    for node in list(tree.nodes):
        if node.type == "NORMAL_MAP" and node.space == "TANGENT" and not node.uv_map:
            node.uv_map = uv_name
        elif node.type == "TEX_IMAGE" and not node.inputs["Vector"].is_linked:
            tree.links.new(source_uv(), node.inputs["Vector"])
        elif node.type == "TEX_COORD":
            for link in list(node.outputs["UV"].links):
                tree.links.new(source_uv(), link.to_socket)
        elif node.type == "GROUP" and node.node_tree:
            original = node.node_tree
            if original not in memo:
                copied = original.copy()
                copied.use_fake_user = False
                memo[original] = copied
                groups.append(copied)
                pin_source_uvs(copied, uv_name, groups, memo)
            node.node_tree = memo[original]


def sollumz_api():
    # Supports both legacy add-ons and Blender extension package names.
    modules = [m for name, m in tuple(sys.modules.items())
               if name.endswith(".ydr.shader_materials")
               and hasattr(m, "create_shader")]
    if len(modules) != 1 or not hasattr(bpy.types.Object, "sollum_type"):
        raise ValueError("Enable exactly one Sollumz installation first")
    root = modules[0].__package__.rsplit(".ydr", 1)[0]
    return modules[0], importlib.import_module(root + ".tools.drawablehelper")


def surface_inputs(mat):
    """Accept an unambiguous surface; never guess a branch of a mixed shader."""
    if not mat or not mat.node_tree:
        raise ValueError("Every face needs a node-based material")
    outputs = [n for n in mat.node_tree.nodes
               if n.type == "OUTPUT_MATERIAL" and n.is_active_output
               and n.target in {"ALL", "CYCLES"}]
    output = next((n for n in outputs if n.target == "CYCLES"),
                  next(iter(outputs), None))
    if output is None or not output.inputs["Surface"].is_linked:
        raise ValueError(f"{mat.name}: missing active Cycles material output")
    if output.inputs["Displacement"].is_linked:
        raise ValueError(f"{mat.name}: bake/apply shader displacement first")
    node = output.inputs["Surface"].links[0].from_node
    visited = set()
    while node.type == "REROUTE" and node not in visited:
        visited.add(node)
        if not node.inputs[0].is_linked:
            break
        node = node.inputs[0].links[0].from_node
    if node.type == "BSDF_PRINCIPLED":
        return output, node.inputs["Base Color"], node.inputs["Alpha"]
    if node.type in {"BSDF_DIFFUSE", "EMISSION"}:
        return output, node.inputs["Color"], None
    raise ValueError(f"{mat.name}: surface must be Principled, Diffuse or Emission; "
                     "resolve mixed/group surfaces before combining")


def validate_sources(context, objects):
    if context.mode != "OBJECT":
        raise ValueError("Switch to Object Mode first")
    if not objects:
        raise ValueError("Select at least one mesh")
    rigs = []
    for obj in objects:
        mesh = obj.data
        if obj.hide_get() or not obj.visible_get():
            raise ValueError(f"{obj.name}: selected mesh must be visible")
        if not mesh.polygons or not mesh.uv_layers:
            raise ValueError(f"{obj.name}: mesh needs faces and source UVs")
        required, _ = referenced_uvs(obj)
        missing = required.difference(mesh.uv_layers.keys())
        if missing:
            raise ValueError(f"{obj.name}: material references missing UV maps: {', '.join(sorted(missing))}")
        if len(required.intersection(mesh.uv_layers.keys())) >= 8 or ATLAS_UV in mesh.uv_layers:
            raise ValueError(f"{obj.name}: leave one free UV slot (maximum seven referenced source UVs)")
        if mesh.shape_keys:
            raise ValueError(f"{obj.name}: shape keys require a separate merge workflow")
        if not np.isfinite(np.asarray(obj.matrix_world)).all():
            raise ValueError(f"{obj.name}: invalid object transform")
        coordinates = np.empty(len(mesh.vertices) * 3, dtype=np.float32)
        mesh.vertices.foreach_get("co", coordinates)
        if not np.isfinite(coordinates).all():
            raise ValueError(f"{obj.name}: invalid vertex coordinates")
        if abs(obj.matrix_world.determinant()) < 1e-12:
            raise ValueError(f"{obj.name}: zero-scale transform")
        for uv in mesh.uv_layers:
            values = np.empty(len(uv.data) * 2, dtype=np.float32)
            uv.data.foreach_get("uv", values)
            if not np.isfinite(values).all():
                raise ValueError(f"{obj.name}: invalid UV coordinates in {uv.name}")
        used = {p.material_index for p in mesh.polygons}
        for index in used:
            if index >= len(obj.material_slots) or not obj.material_slots[index].material:
                raise ValueError(f"{obj.name}: a face has no material")
            surface_inputs(obj.material_slots[index].material)
        armatures = [m for m in obj.modifiers if m.type == "ARMATURE"]
        if len(armatures) > 1 or any(m.object is None for m in armatures):
            raise ValueError(f"{obj.name}: unsupported armature setup")
        if armatures:
            mod = armatures[0]
            if obj.modifiers[-1] != mod:
                raise ValueError(f"{obj.name}: apply modifiers after the armature first")
            rigs.append((mod.object, mod.vertex_group, mod.invert_vertex_group,
                         mod.use_vertex_groups, mod.use_bone_envelopes,
                         mod.use_deform_preserve_volume, mod.show_viewport, mod.show_render))
        else:
            rigs.append(None)
        if hasattr(obj, "sz_lods"):
            lods = obj.sz_lods
            present = [lod.mesh for lod in (lods.very_high, lods.high, lods.medium,
                                           lods.low, lods.very_low) if lod.mesh]
            if len(present) > 1 or any(m != mesh for m in present):
                raise ValueError(f"{obj.name}: select single-LOD meshes; extra LODs cannot be merged safely")
    if any(rig != rigs[0] for rig in rigs):
        raise ValueError("Selected meshes must use the same armature settings; do not mix rigged and static meshes")
    if rigs[0] and any((o.parent, o.parent_type, o.parent_bone) !=
                       (objects[0].parent, objects[0].parent_type, objects[0].parent_bone)
                       for o in objects):
        raise ValueError("Rigged meshes must share the same parent and bone attachment")
    return rigs[0]


def select_only(context, objects):
    for obj in context.selected_objects:
        obj.select_set(False)
    for obj in objects:
        obj.select_set(True)
    context.view_layer.objects.active = objects[0] if objects else None


def validate_shader_inputs(mat, sockets):
    # Cycles cannot evaluate Eevee's Shader to RGB, including inside groups.
    def check_node(node, visited):
        if node in visited:
            return
        visited.add(node)
        if node.type == "SHADER_TO_RGB":
            raise ValueError(f"{mat.name}: Shader to RGB cannot be baked in Cycles")
        if node.type == "TEX_IMAGE":
            # Reading dimensions loads Blender's lazily decoded file images.
            if node.image is None or min(node.image.size) <= 0:
                raise ValueError(f"{mat.name}: missing or unreadable image on {node.name}")
        if node.type == "GROUP" and node.node_tree:
            for inner in node.node_tree.nodes:
                check_node(inner, visited)
        for socket in node.inputs:
            for link in socket.links:
                check_node(link.from_node, visited)
    visited = set()
    for socket in sockets:
        if socket is not None:
            for link in socket.links:
                check_node(link.from_node, visited)


def setup_bake_material(mat, image):
    output, color, alpha = surface_inputs(mat)
    tree = mat.node_tree
    validate_shader_inputs(mat, (color, alpha))
    emission = tree.nodes.new("ShaderNodeEmission")
    tree.links.new(emission.outputs[0], output.inputs["Surface"])
    if alpha is not None and alpha.is_linked:
        # Cycles premultiplies image Color when its Alpha output is unused.
        # Keep the original opacity branch live during RGB baking, with unit
        # emission strength, so straight-alpha textures do not bake dark.
        strength = tree.nodes.new("ShaderNodeMath")
        strength.operation = "MULTIPLY_ADD"
        strength.inputs[1].default_value = 0.0
        strength.inputs[2].default_value = 1.0
        tree.links.new(alpha.links[0].from_socket, strength.inputs[0])
        tree.links.new(strength.outputs[0], emission.inputs["Strength"])
    target = tree.nodes.new("ShaderNodeTexImage")
    target.image = image
    for node in tree.nodes:
        node.select = False
    target.select = True
    tree.nodes.active = target
    return mat, emission, color, alpha


def set_bake_channel(records, image, alpha=False):
    for mat, emission, color, opacity in records:
        tree = mat.node_tree
        tree.nodes.active.image = image
        socket = emission.inputs["Color"]
        for link in list(socket.links):
            tree.links.remove(link)
        source = opacity if alpha else color
        if source is not None and source.is_linked:
            tree.links.new(source.links[0].from_socket, socket)
        elif alpha:
            value = float(source.default_value) if source is not None else 1.0
            socket.default_value = (value, value, value, 1.0)
        else:
            socket.default_value = color.default_value


def setup_world_normal(mat, image):
    """Capture original shading before applying object transforms."""
    output, color, _ = surface_inputs(mat)
    tree = mat.node_tree
    previous = output.inputs["Surface"].links[0].from_socket
    normal = color.node.inputs.get("Normal")
    validate_shader_inputs(mat, (normal,))
    if normal is not None and normal.is_linked:
        source = normal.links[0].from_socket
    else:
        source = tree.nodes.new("ShaderNodeNewGeometry").outputs["Normal"]
    scale = tree.nodes.new("ShaderNodeVectorMath")
    scale.operation = "SCALE"
    scale.inputs[3].default_value = 0.5
    add = tree.nodes.new("ShaderNodeVectorMath")
    add.operation = "ADD"
    add.inputs[1].default_value = (0.5, 0.5, 0.5)
    emit = tree.nodes.new("ShaderNodeEmission")
    tree.links.new(source, scale.inputs[0])
    tree.links.new(scale.outputs[0], add.inputs[0])
    tree.links.new(add.outputs[0], emit.inputs["Color"])
    tree.links.new(emit.outputs[0], output.inputs["Surface"])
    target = tree.nodes.new("ShaderNodeTexImage")
    target.image = image
    tree.nodes.active = target
    return tree, output, previous


def intact_tangent_sheets(obj, used):
    """Uniform transforms and ordinary UV normals need no geometry reprojection."""
    matrix = np.asarray(obj.matrix_world.to_3x3())
    gram = matrix.T @ matrix
    if np.linalg.det(matrix) <= 0 or not np.allclose(gram, np.eye(3) * gram[0, 0], rtol=1e-5, atol=1e-10):
        return False
    source_uv = next(u.name for u in obj.data.uv_layers if u.active_render)
    def uv_only(socket, visited):
        for link in socket.links:
            node = link.from_node
            if node in visited:
                continue
            visited.add(node)
            if node.type in {"GROUP", "NEW_GEOMETRY", "OBJECT_INFO", "ATTRIBUTE", "VERTEX_COLOR", "BUMP"}:
                return False
            if node.type == "TEX_COORD" and link.from_socket.name != "UV":
                return False
            if node.type == "UVMAP" and node.uv_map not in {"", source_uv}:
                return False
            if not all(uv_only(s, visited) for s in node.inputs):
                return False
        return True
    for i in used:
        normal = surface_inputs(obj.material_slots[i].material)[1].node.inputs.get("Normal")
        if normal is None or not normal.is_linked:
            continue
        node = normal.links[0].from_node
        if node.type != "NORMAL_MAP" or node.space != "TANGENT" or node.uv_map not in {"", source_uv}:
            return False
        if not all(uv_only(socket, set()) for socket in node.inputs):
            return False
    return True


DDS_SIZES = [(str(n), f"{n} x {n}", "") for n in (256, 512, 1024, 2048, 4096)]
DDS_FORMATS = [("A8R8G8B8", "A8R8G8B8", "Uncompressed RGBA, preserves baked pixel values"),
               ("DXT5", "DXT5 (BC3)", "Lossy block compression with alpha; approximately one quarter of RGBA size")]


class GTAAtlas(bpy.types.Operator, ExportHelper):
    bl_idname = "smc.gta_atlas"
    bl_label = "Merge Selected to GTA DDS Atlas"
    bl_description = "Create a merged copy, bake diffuse and normal DDS atlases, and build a Sollumz drawable"
    bl_options = {"REGISTER", "UNDO"}
    filename_ext = ".dds"
    filter_glob: StringProperty(default="*.dds", options={"HIDDEN"})
    resolution: EnumProperty(name="Diffuse Size", default="2048", items=DDS_SIZES)
    normal_resolution: EnumProperty(name="Normal Size", default="SAME",
                                    items=[("SAME", "Match Diffuse", "Use the diffuse atlas dimensions")] + DDS_SIZES)
    diffuse_format: EnumProperty(name="Diffuse DDS Format", default="A8R8G8B8", items=DDS_FORMATS)
    normal_format: EnumProperty(name="Normal DDS Format", default="A8R8G8B8", items=DDS_FORMATS)
    padding: IntProperty(name="Padding (pixels)", default=16, min=4, max=64)
    uv_layout: EnumProperty(name="UV Layout", default="MATERIAL_TILES", items=[
        ("MATERIAL_TILES", "Keep Material Texture Sheets", "Keep original UV islands; resize and move whole material sheets"),
        ("SMART_PROJECT", "Unwrap Geometry", "Create new UV islands using Smart UV Project")])
    flexible_tiles: BoolProperty(name="Flexible Material Rectangles", default=True,
                                description="Fill spare atlas space with rectangular sheets; UVs and textures resize together")
    shader: EnumProperty(name="GTA Shader", default="default.sps", items=[
        ("default.sps", "Opaque", "Diffuse color; opacity is stored in DDS but ignored by this shader"),
        ("cutout.sps", "Cutout", "Diffuse color with alpha-tested transparency"),
        ("alpha.sps", "Alpha", "Diffuse color with blended transparency")])
    hide_sources: BoolProperty(name="Hide Source Models", default=True,
                              description="Hide originals in this view layer and renders after success")
    export_normals: BoolProperty(name="Export Normal DDS", default=True,
                                description="Bake tangent normals to a second DDS and assign BumpSampler")

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "resolution")
        layout.prop(self, "diffuse_format")
        layout.prop(self, "export_normals")
        normals = layout.column()
        normals.enabled = self.export_normals
        normals.prop(self, "normal_resolution")
        normals.prop(self, "normal_format")
        layout.prop(self, "uv_layout")
        if self.uv_layout == "MATERIAL_TILES":
            layout.prop(self, "flexible_tiles")
        layout.prop(self, "padding")
        layout.prop(self, "shader")
        layout.prop(self, "hide_sources")
        layout.label(text="Diffuse + opacity, plus optional normal atlas. Specular is not baked.")
        layout.label(text="DDS: shared UV layout, independent sizes/formats, full mipmaps.")

    def execute(self, context):
        objects = sorted((o for o in context.selected_objects if o.type == "MESH"), key=lambda o: o.name)
        previous_selected = list(context.selected_objects)
        previous_active = context.view_layer.objects.active
        scene = context.scene
        copies, meshes, materials, images, armatures, groups = [], [], [], [], [], []
        drawable = None
        temp_path = None
        normal_temp_path = None
        published = []
        success = False
        original_hiding = [(o, o.hide_get(), o.hide_render) for o in objects]
        engine = scene.render.engine
        cycles_device = scene.cycles.device
        cycles_samples = scene.cycles.samples
        try:
            shaders, helper = sollumz_api()
            rig = validate_sources(context, objects)
            size = int(self.resolution)
            normal_size = size if self.normal_resolution == "SAME" else int(self.normal_resolution)
            world_size = max(size, normal_size) if self.export_normals else size
            normal_margin = max(1, round(self.padding * normal_size / size / 2))
            world_margin = max(1, round(self.padding * world_size / size / 2))
            if self.padding * 4 >= size:
                raise ValueError("Padding must be less than one quarter of atlas size")
            path = Path(bpy.path.abspath(self.filepath)).resolve()
            if not self.filepath or path.suffix.lower() != ".dds" or not path.parent.is_dir():
                raise ValueError("Choose a .dds file in an existing output folder")
            if path.exists():
                raise ValueError("Output already exists; choose a new filename to preserve existing textures")
            name = re.sub(r"[^a-z0-9_]+", "_", path.stem.lower()).strip("_")
            if not name or path.stem != name:
                raise ValueError("Use a lowercase DDS filename containing only letters, digits and underscores")
            normal_path = path.with_name(name + "_normal.dds") if self.export_normals else None
            if normal_path and normal_path.exists():
                raise ValueError("Normal DDS already exists; choose a new filename")
            # Reserve output before any expensive work. Final publication is atomic.
            fd, temp_path = tempfile.mkstemp(suffix=".dds", dir=str(path.parent))
            os.close(fd)
            shader = {"default.sps": "normal.sps", "cutout.sps": "normal_cutout.sps",
                      "alpha.sps": "normal_alpha.sps"}.get(self.shader, self.shader) if self.export_normals else self.shader
            final_material = shaders.create_shader(shader)
            materials.append(final_material)
            final_material.name = name + "_atlas"
            if final_material.node_tree.nodes.get("DiffuseSampler") is None:
                raise ValueError("Selected Sollumz shader has no DiffuseSampler")
            depsgraph = context.evaluated_depsgraph_get()
            for original in objects:
                obj = original.copy()
                obj.data = original.data.copy()
                obj.data.use_fake_user = False
                meshes.append(obj.data)
                copies.append(obj)
                context.collection.objects.link(obj)
                lods = obj.sz_lods
                for lod in (lods.very_high, lods.high, lods.medium, lods.low, lods.very_low):
                    lod.mesh = None
                world = original.evaluated_get(depsgraph).matrix_world.copy()
                obj.animation_data_clear()
                obj.constraints.clear()
                obj.matrix_world = world
                obj.hide_render = False
                obj.hide_set(False)
                obj.hide_viewport = False
                select_only(context, [obj])
                for mod in list(obj.modifiers):
                    if mod.type != "ARMATURE":
                        if mod.show_viewport:
                            bpy.ops.object.modifier_apply(modifier=mod.name)
                        else:
                            obj.modifiers.remove(mod)
                if not obj.data.polygons or not obj.data.uv_layers:
                    raise ValueError(f"{original.name}: modifiers removed faces or UVs")
                # Object-linked materials must become private data-linked slots.
                for slot in obj.material_slots:
                    mat = slot.material
                    if mat:
                        copied = mat.copy()
                        copied.use_fake_user = False
                        materials.append(copied)
                        slot.link = "DATA"
                        slot.material = copied
                required, source_uv_name = referenced_uvs(obj)
                if len(obj.data.uv_layers) >= 8:
                    for uv in list(obj.data.uv_layers):
                        if uv.name not in required:
                            obj.data.uv_layers.remove(uv)
                if len(obj.data.uv_layers) >= 8:
                    raise ValueError(f"{original.name}: no free UV slot after modifiers")
                for mat in {slot.material for slot in obj.material_slots if slot.material}:
                    pin_source_uvs(mat.node_tree, source_uv_name, groups, {})
                target = obj.data.uv_layers.new(name=ATLAS_UV)
                obj.data.uv_layers.active = target
                obj.data.uv_layers[source_uv_name].active_render = True
                for mod in obj.modifiers:
                    if mod.type == "ARMATURE":
                        mod.show_viewport = mod.show_render = False
            tiles = []
            if self.uv_layout == "MATERIAL_TILES":
                tiles = arrange_material_tiles(copies, ATLAS_UV, size, self.padding, self.flexible_tiles)
            else:
                select_only(context, copies)
                bpy.ops.object.mode_set(mode="EDIT")
                bpy.ops.mesh.select_all(action="SELECT")
                bpy.ops.uv.smart_project(angle_limit=1.1519173,
                                         island_margin=self.padding / size,
                                         margin_method="ADD", rotate_method="AXIS_ALIGNED",
                                         area_weight=0.0, correct_aspect=False, scale_to_bounds=True)
                bpy.ops.object.mode_set(mode="OBJECT")
            color_image = bpy.data.images.new(name + "_bake", width=size, height=size,
                                             alpha=True, float_buffer=True)
            opacity_image = bpy.data.images.new(name + "_opacity", width=size, height=size,
                                               alpha=True, float_buffer=True)
            images.extend((color_image, opacity_image))
            color_image.colorspace_settings.name = "Linear Rec.709"
            opacity_image.colorspace_settings.name = "Non-Color"
            scene.render.engine = "CYCLES"
            scene.cycles.device = "CPU"
            scene.cycles.samples = 1
            normal_image = None
            world_normal_image = None
            if self.export_normals:
                normal_image = bpy.data.images.new(name + "_normal_bake", width=normal_size, height=normal_size,
                                                  alpha=True, float_buffer=True)
                images.append(normal_image)
                normal_image.colorspace_settings.name = "Non-Color"
                flat = np.empty((normal_size, normal_size, 4), dtype=np.float32)
                flat[:] = (0.5, 0.5, 1.0, 1.0)
                normal_image.pixels.foreach_set(flat.ravel())
                normal_image.update()
                world_normal_image = bpy.data.images.new(name + "_world_normal", width=world_size, height=world_size,
                                                        alpha=True, float_buffer=True)
                images.append(world_normal_image)
                world_normal_image.colorspace_settings.name = "Non-Color"
            for tile in tiles:
                proxy = tile_proxy(context, tile, ATLAS_UV, size)
                try:
                    select_only(context, [proxy])
                    mat = tile["material"]
                    output = surface_inputs(mat)[0]
                    previous = output.inputs["Surface"].links[0].from_socket
                    tree = mat.node_tree
                    if normal_image:
                        validate_shader_inputs(mat, (surface_inputs(mat)[1].node.inputs.get("Normal"),))
                        target = tree.nodes.new("ShaderNodeTexImage")
                        target.image = normal_image
                        tree.nodes.active = target
                        alpha_socket = surface_inputs(mat)[2]
                        alpha_source = alpha_socket.links[0].from_socket if alpha_socket and alpha_socket.is_linked else None
                        alpha_value = alpha_socket.default_value if alpha_socket else None
                        if alpha_socket:
                            for link in list(alpha_socket.links):
                                tree.links.remove(link)
                            alpha_socket.default_value = 1.0
                        try:
                            result = bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT",
                                                        normal_r="POS_X", normal_g="NEG_Y", normal_b="POS_Z",
                                                        use_clear=False, use_selected_to_active=False,
                                                        target="IMAGE_TEXTURES", save_mode="INTERNAL", margin=normal_margin,
                                                        margin_type="EXTEND", uv_layer=ATLAS_UV)
                        finally:
                            if alpha_socket:
                                alpha_socket.default_value = alpha_value
                                if alpha_source:
                                    tree.links.new(alpha_source, alpha_socket)
                        if result != {"FINISHED"}:
                            raise RuntimeError("Material sheet normal bake failed")
                    records = [setup_bake_material(mat, color_image)]
                    for alpha, image in ((False, color_image), (True, opacity_image)):
                        set_bake_channel(records, image, alpha)
                        result = bpy.ops.object.bake(type="EMIT", use_clear=False, use_selected_to_active=False,
                                                    target="IMAGE_TEXTURES", save_mode="INTERNAL", margin=self.padding // 2,
                                                    margin_type="EXTEND", uv_layer=ATLAS_UV)
                        if result != {"FINISHED"}:
                            raise RuntimeError("Material sheet diffuse bake failed")
                    tree.links.new(previous, output.inputs["Surface"])
                finally:
                    mesh = proxy.data
                    bpy.data.objects.remove(proxy, do_unlink=True)
                    bpy.data.meshes.remove(mesh)
            for obj in copies:
                select_only(context, [obj])
                used = {p.material_index for p in obj.data.polygons}
                reproject_normals = bool(normal_image) and (self.uv_layout != "MATERIAL_TILES" or
                                                            not intact_tangent_sheets(obj, used))
                if reproject_normals:
                    records = [setup_world_normal(obj.material_slots[i].material, world_normal_image) for i in used]
                    result = bpy.ops.object.bake(type="EMIT",
                                                use_clear=False, use_selected_to_active=False,
                                                target="IMAGE_TEXTURES", save_mode="INTERNAL",
                                                margin=world_margin, margin_type="EXTEND",
                                                uv_layer=ATLAS_UV)
                    for tree, output, previous in records:
                        tree.links.new(previous, output.inputs["Surface"])
                    if result != {"FINISHED"}:
                        raise RuntimeError(f"{obj.name}: world-normal bake failed")
                records = [setup_bake_material(obj.material_slots[i].material, color_image) for i in used]
                for alpha, image in ((False, color_image), (True, opacity_image)):
                    set_bake_channel(records, image, alpha)
                    result = bpy.ops.object.bake(type="EMIT", use_clear=False,
                                                use_selected_to_active=False,
                                                target="IMAGE_TEXTURES", save_mode="INTERNAL",
                                                margin=max(1, self.padding // 2),
                                                margin_type="EXTEND", uv_layer=ATLAS_UV)
                    if result != {"FINISHED"}:
                        raise RuntimeError(f"{obj.name}: texture bake failed")
                # Match the final joined tangent frame, including mirrored scales.
                bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
                if reproject_normals:
                    for i in used:
                        tree = obj.material_slots[i].material.node_tree
                        uv = tree.nodes.new("ShaderNodeUVMap")
                        uv.uv_map = ATLAS_UV
                        source = tree.nodes.new("ShaderNodeTexImage")
                        source.image = world_normal_image
                        tree.links.new(uv.outputs[0], source.inputs["Vector"])
                        normal = tree.nodes.new("ShaderNodeNormalMap")
                        normal.space = "WORLD"
                        tree.links.new(source.outputs["Color"], normal.inputs["Color"])
                        diffuse = tree.nodes.new("ShaderNodeBsdfDiffuse")
                        tree.links.new(normal.outputs[0], diffuse.inputs["Normal"])
                        output = surface_inputs(obj.material_slots[i].material)[0]
                        tree.links.new(diffuse.outputs[0], output.inputs["Surface"])
                        tree.nodes.active.image = normal_image
                    result = bpy.ops.object.bake(type="NORMAL", normal_space="TANGENT",
                                                normal_r="POS_X", normal_g="NEG_Y", normal_b="POS_Z",
                                                use_clear=False, use_selected_to_active=False,
                                                target="IMAGE_TEXTURES", save_mode="INTERNAL",
                                                margin=normal_margin, margin_type="EXTEND",
                                                uv_layer=ATLAS_UV)
                    if result != {"FINISHED"}:
                        raise RuntimeError(f"{obj.name}: tangent-normal bake failed")
            pixels = np.empty(size * size * 4, dtype=np.float32)
            color_image.pixels.foreach_get(pixels)
            pixels = pixels.reshape(size, size, 4)
            opacity = np.empty(size * size * 4, dtype=np.float32)
            opacity_image.pixels.foreach_get(opacity)
            pixels[..., 3] = np.clip(opacity.reshape(size, size, 4)[..., 0], 0, 1)
            with open(temp_path, "wb") as stream:
                write_dds(stream, pixels, pixel_format=self.diffuse_format)
                stream.flush()
                os.fsync(stream.fileno())
            atlas = bpy.data.images.load(temp_path, check_existing=False)
            images.append(atlas)
            atlas.name = name
            atlas.colorspace_settings.name = "sRGB"
            atlas.alpha_mode = "CHANNEL_PACKED"
            sampler = final_material.node_tree.nodes["DiffuseSampler"]
            sampler.image = atlas
            sampler.texture_properties.embedded = True
            normal_atlas = None
            if normal_image:
                values = np.empty(normal_size * normal_size * 4, dtype=np.float32)
                normal_image.pixels.foreach_get(values)
                values = values.reshape(normal_size, normal_size, 4)
                values[..., 3] = 1.0
                fd, normal_temp_path = tempfile.mkstemp(suffix=".dds", dir=str(path.parent))
                with os.fdopen(fd, "wb") as stream:
                    write_dds(stream, values, normal_map=True, pixel_format=self.normal_format)
                    stream.flush()
                    os.fsync(stream.fileno())
                normal_atlas = bpy.data.images.load(normal_temp_path, check_existing=False)
                images.append(normal_atlas)
                normal_atlas.name = name + "_normal"
                normal_atlas.colorspace_settings.name = "Non-Color"
                normal_atlas.alpha_mode = "CHANNEL_PACKED"
                bump = final_material.node_tree.nodes.get("BumpSampler")
                if bump is None:
                    raise ValueError("Selected Sollumz shader has no BumpSampler")
                bump.image = normal_atlas
                bump.texture_properties.embedded = True
            # Only the completed atlas UV survives. White colors prevent double tinting.
            for obj in copies:
                for uv in list(obj.data.uv_layers):
                    if uv.name != ATLAS_UV:
                        obj.data.uv_layers.remove(uv)
                obj.data.uv_layers[0].name = "UVMap 0"
                obj.data.uv_layers[0].active_render = True
                obj.data.materials.clear()
                obj.data.materials.append(final_material)
                for face in obj.data.polygons:
                    face.material_index = 0
                for attr in list(obj.data.color_attributes):
                    obj.data.color_attributes.remove(attr)
                attr = obj.data.color_attributes.new(name="Color 1", type="BYTE_COLOR", domain="CORNER")
                attr.data.foreach_set("color", np.ones(len(attr.data) * 4, dtype=np.float32))
            select_only(context, copies)
            if len(copies) > 1:
                bpy.ops.object.join()
            merged = context.view_layer.objects.active
            copies[:] = [merged]
            merged.vertex_groups.clear()
            merged.name = name + ".model"
            if rig:
                mod = next(m for m in merged.modifiers if m.type == "ARMATURE")
                mod.show_viewport, mod.show_render = rig[-2:]
                drawable = rig[0].copy()
                drawable.data = rig[0].data.copy()
                drawable.data.use_fake_user = False
                armatures.append(drawable.data)
                context.collection.objects.link(drawable)
                drawable.name = name
                drawable.hide_viewport = drawable.hide_render = False
                drawable.hide_set(False)
                drawable.sollum_type = helper.SollumType.DRAWABLE
                mod.object = drawable
                world = merged.matrix_world.copy()
                merged.parent = drawable
                merged.matrix_world = world
                helper.convert_obj_to_model(merged)
            else:
                # Fresh drawable avoids altering an existing source hierarchy.
                world = merged.matrix_world.copy()
                merged.parent = None
                merged.matrix_world = world
                drawable = helper.convert_obj_to_drawable(merged)
                drawable.name = name
                merged.name = name + ".model"
            merged.data.name = name + "_mesh"
            if len(merged.data.uv_layers) != 1 or len(merged.data.materials) != 1:
                raise RuntimeError("Merged mesh did not produce exactly one UV map and material")
            if self.hide_sources:
                for source in objects:
                    source.hide_set(True)
                    source.hide_render = True
            # Publish last. Windows rename and POSIX link refuse an existing target.
            atlas.filepath = str(path)
            if normal_atlas:
                normal_atlas.filepath = str(normal_path)
            for temporary, destination in ((normal_temp_path, normal_path), (temp_path, path)):
                if temporary is None:
                    continue
                stat = os.stat(temporary)
                if os.name == "nt":
                    os.rename(temporary, destination)
                else:
                    os.link(temporary, destination)
                published.append((destination, stat.st_dev, stat.st_ino))
            success = True
            files = path.name + (f" + {normal_path.name}" if normal_path else "")
            self.report({"INFO"}, f"Merged {len(objects)} meshes; one UVMap 0 and {files}")
            return {"FINISHED"}
        except Exception as exc:
            if not isinstance(exc, ValueError):
                traceback.print_exc()
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        finally:
            if copies and context.mode != "OBJECT" and context.view_layer.objects.active:
                bpy.ops.object.mode_set(mode="OBJECT")
            scene.render.engine = engine
            scene.cycles.device = cycles_device
            scene.cycles.samples = cycles_samples
            for temporary in (temp_path, normal_temp_path):
                if temporary and os.path.exists(temporary):
                    try:
                        os.unlink(temporary)
                    except OSError as exc:
                        self.report({"WARNING"}, f"Could not remove temporary file {temporary}: {exc}")
            if not success:
                for destination, device, inode in published:
                    try:
                        stat = destination.stat()
                        if (stat.st_dev, stat.st_ino) == (device, inode):
                            destination.unlink()
                    except FileNotFoundError:
                        pass
                    except OSError as exc:
                        self.report({"WARNING"}, f"Could not remove incomplete atlas {destination}: {exc}")
                for obj in copies + ([drawable] if drawable else []):
                    if obj.name in bpy.data.objects:
                        bpy.data.objects.remove(obj, do_unlink=True)
                for source, hidden, render_hidden in original_hiding:
                    source.hide_set(hidden)
                    source.hide_render = render_hidden
                if context.mode == "OBJECT":
                    select_only(context, previous_selected)
                    context.view_layer.objects.active = previous_active
            for mesh in meshes:
                try:
                    if mesh.users == 0:
                        bpy.data.meshes.remove(mesh)
                except ReferenceError:
                    pass  # Blender freed a joined source mesh.
            for armature in armatures:
                if armature.users == 0:
                    bpy.data.armatures.remove(armature)
            for mat in materials:
                if mat.users == 0:
                    bpy.data.materials.remove(mat)
            for group in groups:
                # Copied parent groups release their copied children in this order.
                if group.users == 0:
                    bpy.data.node_groups.remove(group)
            for image in images:
                if image.users == 0:
                    bpy.data.images.remove(image)
