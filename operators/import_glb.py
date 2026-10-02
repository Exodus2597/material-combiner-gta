"""GLB import with exported Unreal material sidecars and exact texture paths."""

import json
import math
import re
from pathlib import Path, PurePosixPath

import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

from .gta_atlas import select_only

IMAGE_EXTENSIONS = {".png", ".dds", ".tga", ".jpg", ".jpeg", ".bmp", ".tif", ".tiff", ".exr"}


def infer_texture_root(filepath):
    for parent in filepath.parents:
        if parent.name.casefold() == "content":
            return parent.parent.parent
    return filepath.parent


def asset_index(root):
    index = {}
    for path in root.rglob("*"):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS | {".json"}:
            index.setdefault((path.stem.casefold(), path.suffix.lower() == ".json"), []).append(path)
    return index


def unique(paths, label):
    paths = list(dict.fromkeys(paths))
    if len(paths) > 1:
        raise ValueError(f"Ambiguous {label}: " + ", ".join(str(p) for p in paths))
    return paths[0] if paths else None


def metadata_for(name, index):
    name = re.sub(r"\.\d{3}$", "", name)
    path = unique(index.get((name.casefold(), True), []), f"material sidecar for {name}")
    if path is None:
        return None
    if path.stat().st_size > 16 * 1024 * 1024:
        raise ValueError(f"Material sidecar is too large: {path.name}")
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(data, dict) or not isinstance(data.get("Textures", {}), dict):
        raise ValueError(f"Invalid material sidecar: {path.name}")
    return data


def resolve_texture(reference, root, index):
    if not isinstance(reference, dict):
        raise ValueError("Texture reference must contain ObjectPath/ObjectName")
    raw = reference.get("ObjectPath", "")
    if not isinstance(raw, str):
        raise ValueError("Invalid texture ObjectPath")
    posix = PurePosixPath(raw.replace("\\", "/"))
    if posix.is_absolute() or ".." in posix.parts or any(":" in p for p in posix.parts):
        raise ValueError(f"Texture path escapes the export folder: {raw}")
    if raw:
        relative = posix.with_suffix("") if posix.suffix and posix.suffix[1:].isdigit() else posix
        candidate = (root / str(relative)).resolve()
        if not candidate.is_relative_to(root):
            raise ValueError(f"Texture path escapes the export folder: {raw}")
        if candidate.suffix.lower() in IMAGE_EXTENSIONS and candidate.is_file():
            return candidate
        exact = unique([candidate.with_suffix(ext) for ext in sorted(IMAGE_EXTENSIONS)
                        if candidate.with_suffix(ext).is_file()], f"texture {relative}")
        if exact:
            if not exact.resolve().is_relative_to(root):
                raise ValueError(f"Texture symlink escapes the export folder: {raw}")
            return exact
        stem = relative.stem
    else:
        object_name = reference.get("ObjectName", "")
        if not isinstance(object_name, str):
            raise ValueError("Invalid texture ObjectName")
        match = re.search(r"'([^']+)'", object_name)
        stem = (match.group(1) if match else object_name).rsplit(".", 1)[-1]
        if not stem or "/" in stem or "\\" in stem or ":" in stem:
            raise ValueError("Invalid texture ObjectName")
    path = unique(index.get((stem.casefold(), False), []), f"texture {stem}")
    if path is None or not path.resolve().is_relative_to(root):
        raise ValueError(f"Referenced texture not found inside export folder: {raw or stem}")
    return path


def map_reference(data, role):
    aliases = ("PM_Diffuse", "Color Texture", "Base Color", "BaseColor", "Diffuse", "Albedo", "B") if role == "diffuse" else (
        "PM_Normals", "Normal Texture", "Normal Map", "Normals", "Normal", "N")
    textures = {re.sub(r"[^a-z0-9]", "", key.casefold()): value
                for key, value in data.get("Textures", {}).items()}
    for alias in aliases:
        key = re.sub(r"[^a-z0-9]", "", alias.casefold())
        if key in textures:
            return textures[key]
    suffixes = ("_b", "_d", "_diffuse", "_basecolor", "_albedo") if role == "diffuse" else ("_n", "_normal", "_normals")
    candidates = [value for key, value in data.get("Textures", {}).items() if key.casefold().endswith(suffixes)]
    # Multiple unrelated layers (e.g. rain + garment normals) need an explicit role.
    if len(candidates) == 1:
        return candidates[0]
    if candidates:
        raise ValueError(f"Multiple {role} layers need a PM_Diffuse/PM_Normals reference")
    return None


def fallback_texture(material_name, role, index):
    name = re.sub(r"\.\d{3}$", "", material_name)
    bases = {name.casefold(), re.sub(r"^(?:mi_|m_)", "", name.casefold())}
    suffixes = ("_b", "_d", "_diffuse", "_basecolor", "_albedo") if role == "diffuse" else ("_n", "_normal", "_normals")
    return unique([path for base in bases for suffix in suffixes
                   for path in index.get((base + suffix, False), [])], f"{role} for {name}")


class ImportTexturedGLB(bpy.types.Operator, ImportHelper):
    bl_idname = "smc.import_textured_glb"
    bl_label = "Import GLB + Diffuse / Normal Textures"
    bl_description = "Import GLB and attach textures from matching material JSON sidecars or filenames"
    bl_options = {"REGISTER", "UNDO"}
    filename_ext = ".glb"
    filter_glob: StringProperty(default="*.glb", options={"HIDDEN"})
    texture_root: StringProperty(name="Texture Export Folder", subtype="DIR_PATH",
                                 description="Optional export root; inferred from the Content folder when empty")
    normal_convention: EnumProperty(name="Source Normal Convention", default="AUTO", items=[
        ("AUTO", "Automatic", "Unreal JSON sidecars use DirectX; ordinary GLB uses OpenGL"),
        ("DIRECTX", "DirectX (-Y)", "Invert green before Blender's Normal Map node"),
        ("OPENGL", "OpenGL (+Y)", "Use the texture without green inversion")])
    pack_images: BoolProperty(name="Pack Images into Blend", default=True)

    def draw(self, context):
        self.layout.prop(self, "texture_root")
        self.layout.prop(self, "normal_convention")
        self.layout.prop(self, "pack_images")

    def execute(self, context):
        selected, active = list(context.selected_objects), context.view_layer.objects.active
        collections = (bpy.data.objects, bpy.data.meshes, bpy.data.armatures, bpy.data.materials,
                       bpy.data.node_groups, bpy.data.images, bpy.data.actions, bpy.data.collections)
        before = [set(items) for items in collections]
        success = False
        try:
            if context.mode != "OBJECT":
                raise ValueError("Switch to Object Mode first")
            filepath = Path(bpy.path.abspath(self.filepath)).resolve()
            if not filepath.is_file() or filepath.suffix.lower() != ".glb":
                raise ValueError("Choose an existing .glb file")
            root = Path(bpy.path.abspath(self.texture_root)).resolve() if self.texture_root else infer_texture_root(filepath)
            if not root.is_dir():
                raise ValueError("Texture export folder does not exist")
            index = asset_index(root)
            result = bpy.ops.import_scene.gltf(filepath=str(filepath), import_pack_images=self.pack_images,
                                               import_select_created_objects=True)
            if result != {"FINISHED"}:
                raise RuntimeError("Blender GLB import failed")
            imported = [o for o in bpy.data.objects if o not in before[0]]
            # Bone widgets are meshes too, but are not part of the GLB model.
            widgets = {bone.custom_shape for obj in imported if obj.type == "ARMATURE"
                       for bone in obj.pose.bones if bone.custom_shape}
            meshes = [o for o in imported if o.type == "MESH" and o not in widgets
                      and o.name in context.view_layer.objects]
            if not meshes:
                raise ValueError("GLB contains no mesh objects")
            for obj in meshes:
                for slot in obj.material_slots:
                    if slot.material in before[3]:
                        slot.material = slot.material.copy()
                        slot.material.use_fake_user = False
            materials = {slot.material for obj in meshes for slot in obj.material_slots if slot.material}
            loaded = {}
            diffuse_count = normal_count = constant_count = 0
            def load(path, role):
                key = (path.resolve(), role)
                if key not in loaded:
                    image = bpy.data.images.load(str(path), check_existing=False)
                    if min(image.size) <= 0:
                        raise ValueError(f"Texture is unreadable: {path}")
                    image.colorspace_settings.name = "sRGB" if role == "diffuse" else "Non-Color"
                    image.alpha_mode = "CHANNEL_PACKED"
                    if self.pack_images:
                        image.pack()
                    loaded[key] = image
                return loaded[key]
            for mat in materials:
                data = metadata_for(mat.name, index)
                tree = mat.node_tree
                bsdf = next((n for n in tree.nodes if n.type == "BSDF_PRINCIPLED"), None) if tree else None
                if bsdf is None:
                    raise ValueError(f"{mat.name}: imported material has no Principled shader")
                maps = {}
                for role, socket in (("diffuse", "Base Color"), ("normal", "Normal")):
                    reference = map_reference(data, role) if data else None
                    if reference:
                        maps[role] = resolve_texture(reference, root, index)
                    elif not bsdf.inputs[socket].is_linked:
                        maps[role] = fallback_texture(mat.name, role, index)
                uv_name = next((u.name for obj in meshes if mat in obj.data.materials[:]
                                for u in obj.data.uv_layers if u.active_render), "")
                uv = tree.nodes.new("ShaderNodeUVMap") if any(maps.values()) else None
                if uv:
                    uv.uv_map = uv_name
                if maps.get("diffuse"):
                    tex = tree.nodes.new("ShaderNodeTexImage")
                    tex.label = "Imported Diffuse"
                    tex.image = load(maps["diffuse"], "diffuse")
                    tree.links.new(uv.outputs[0], tex.inputs["Vector"])
                    color = tex.outputs["Color"]
                    tint = data.get("Colors", {}).get("ColorTint") if data else None
                    if tint:
                        rgba = tuple(float(tint.get(c, 1)) for c in ("R", "G", "B")) + (1.0,)
                        if not all(math.isfinite(c) for c in rgba):
                            raise ValueError(f"{mat.name}: invalid ColorTint")
                        multiply = tree.nodes.new("ShaderNodeMixRGB")
                        multiply.blend_type = "MULTIPLY"
                        multiply.inputs[0].default_value = 1
                        multiply.inputs[2].default_value = rgba
                        tree.links.new(color, multiply.inputs[1])
                        color = multiply.outputs[0]
                    tree.links.new(color, bsdf.inputs["Base Color"])
                    if data and data.get("BlendMode") in {1, 2, 3, 4, 5}:
                        tree.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
                        mat.surface_render_method = "DITHERED"
                    diffuse_count += 1
                elif data:
                    color = data.get("Colors", {}).get("Base_Colour") or data.get("Colors", {}).get("Base_Color")
                    if color:
                        rgba = tuple(float(color.get(c, 0)) for c in ("R", "G", "B")) + (1.0,)
                        if not all(math.isfinite(c) for c in rgba):
                            raise ValueError(f"{mat.name}: invalid base color")
                        for link in list(bsdf.inputs["Base Color"].links):
                            tree.links.remove(link)
                        bsdf.inputs["Base Color"].default_value = rgba
                        constant_count += 1
                if maps.get("normal"):
                    tex = tree.nodes.new("ShaderNodeTexImage")
                    tex.label = "Imported Normal"
                    tex.image = load(maps["normal"], "normal")
                    tree.links.new(uv.outputs[0], tex.inputs["Vector"])
                    color = tex.outputs["Color"]
                    directx = self.normal_convention == "DIRECTX" or (self.normal_convention == "AUTO" and data is not None)
                    if directx:
                        split = tree.nodes.new("ShaderNodeSeparateColor")
                        combine = tree.nodes.new("ShaderNodeCombineColor")
                        invert = tree.nodes.new("ShaderNodeMath")
                        invert.operation = "SUBTRACT"
                        invert.inputs[0].default_value = 1
                        tree.links.new(color, split.inputs[0])
                        tree.links.new(split.outputs[0], combine.inputs[0])
                        tree.links.new(split.outputs[1], invert.inputs[1])
                        tree.links.new(invert.outputs[0], combine.inputs[1])
                        tree.links.new(split.outputs[2], combine.inputs[2])
                        color = combine.outputs[0]
                    normal = tree.nodes.new("ShaderNodeNormalMap")
                    normal.uv_map = uv_name
                    tree.links.new(color, normal.inputs["Color"])
                    tree.links.new(normal.outputs[0], bsdf.inputs["Normal"])
                    normal_count += 1
                if data:
                    bsdf.inputs["Metallic"].default_value = 0
                    roughness = float(data.get("Scalars", {}).get("Roughness", 0.5))
                    if not math.isfinite(roughness):
                        raise ValueError(f"{mat.name}: invalid roughness")
                    bsdf.inputs["Roughness"].default_value = min(1, max(0, roughness))
            select_only(context, meshes)
            success = True
            self.report({"INFO"}, f"Imported {len(meshes)} meshes: {diffuse_count} diffuse maps, "
                        f"{normal_count} normal maps, {constant_count} base colors")
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        finally:
            if not success:
                for items, previous in zip(collections, before):
                    for item in list(items):
                        if item not in previous:
                            items.remove(item, do_unlink=True)
                if context.mode == "OBJECT":
                    select_only(context, selected)
                    context.view_layer.objects.active = active
