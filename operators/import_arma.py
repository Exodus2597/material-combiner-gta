"""Import a loose P3D or pick a P3D member from an Arma PBO."""

import json
import os
from pathlib import Path
import platform
import re
import struct
import subprocess
import tempfile

import bpy
from bpy.props import CollectionProperty, IntProperty, StringProperty
from bpy_extras.io_utils import ImportHelper
import numpy as np

from ..utils.glb import GLB


def source_path(filepath, suffixes):
    path = Path(bpy.path.abspath(filepath)).resolve()
    if not path.is_file() or path.suffix.lower() not in suffixes:
        raise ValueError("Choose an existing Arma .p3d or .pbo file")
    return path


def run_bridge(output, *args):
    if os.name != "nt" or platform.machine().lower() not in {"amd64", "x86_64"}:
        raise ValueError("Bundled Arma import requires Windows x64")
    bridge = Path(__file__).resolve().parents[1] / "vendor/arma_bridge.exe"
    if not bridge.is_file():
        raise ValueError("Arma decoder is missing; reinstall the complete add-on ZIP")
    env = {name: value for name, value in os.environ.items()
           if not name.upper().startswith(("DOTNET_", "COMPLUS_"))}
    env["DOTNET_BUNDLE_EXTRACT_BASE_DIR"] = str(output / "runtime")
    try:
        result = subprocess.run([str(bridge), *map(str, args)], cwd=output, env=env,
                                creationflags=subprocess.CREATE_NO_WINDOW, timeout=120,
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired as error:
        raise ValueError("Arma decoding timed out") from error
    if result.returncode:
        detail = result.stderr.strip().splitlines()
        raise ValueError("Arma import failed: " + (detail[-1][:350] if detail else "decoder stopped unexpectedly"))


def list_pbo_models(path):
    with tempfile.TemporaryDirectory(prefix="smc_pbo_") as folder:
        output = Path(folder)
        index = output / "models.json"
        run_bridge(output, "list", path, index)
        return json.loads(index.read_text(encoding="utf-8"))


def make_glb(data, output):
    glb = GLB()
    primitives = []
    images = {}

    def texture(name):
        if name not in images:
            if not re.fullmatch(r"texture_[0-9]+\.png", name):
                raise ValueError("Invalid Arma texture output")
            path = output / name
            with path.open("rb") as file:
                header = file.read(24)
                if len(header) != 24 or header[:16] != b"\x89PNG\r\n\x1a\n\0\0\0\rIHDR":
                    raise ValueError("Invalid PNG in Arma texture output")
                if not all(1 <= size <= 8192 for size in struct.unpack(">II", header[16:])):
                    raise ValueError("Arma texture exceeds the 8192-pixel limit")
            images[name] = glb.image(path)
        return images[name]

    for part in data["Parts"]:
        points = np.asarray(part["Positions"], dtype="<f4").reshape(-1, 3)
        normals = np.asarray(part["Normals"], dtype="<f4").reshape(-1, 3)
        uv = np.asarray(part["Uvs"], dtype="<f4").reshape(-1, 2)
        triangles = np.asarray(part["Indices"], dtype="<u4").reshape(-1, 3)
        if (not len(points) or not len(triangles) or len(points) != len(uv) or normals.shape != points.shape
                or triangles.max() >= len(points) or not all(np.isfinite(a).all() for a in (points, normals, uv))):
            raise ValueError("Invalid geometry in Arma decoder output")
        zero = np.linalg.norm(normals, axis=1) < 1e-6
        if zero.any():
            faces = points[triangles]
            cross = np.cross(faces[:, 1] - faces[:, 0], faces[:, 2] - faces[:, 0])
            fallback = np.zeros_like(normals)
            np.add.at(fallback, triangles.ravel(), np.repeat(cross, 3, axis=0))
            lengths = np.linalg.norm(fallback, axis=1)
            valid = zero & (lengths > 1e-20)
            normals[valid] = fallback[valid] / lengths[valid, None]
            normals[zero & ~valid] = (0, 1, 0)
        pbr = {"metallicFactor": 0.0, "roughnessFactor": 0.55}
        material = {"name": part["Name"], "pbrMetallicRoughness": pbr, "doubleSided": True}
        if part["Diffuse"]:
            pbr["baseColorTexture"] = texture(part["Diffuse"])
            if part["Alpha"]:
                material["alphaMode"] = "BLEND"
        if part["NormalMap"]:
            material["normalTexture"] = texture(part["NormalMap"])
        index = len(glb.doc["materials"])
        glb.doc["materials"].append(material)
        primitives.append(dict(
            attributes={"POSITION": glb.accessor(points, "VEC3", 5126),
                        "NORMAL": glb.accessor(normals, "VEC3", 5126),
                        "TEXCOORD_0": glb.accessor(uv, "VEC2", 5126)},
            indices=glb.accessor(triangles.ravel(), "SCALAR", 5125), material=index))
    if not primitives:
        raise ValueError("The selected P3D has no importable geometry")
    glb.doc["meshes"].append(dict(name=data["Name"], primitives=primitives))
    glb.doc["nodes"].append(dict(name=data["Name"], mesh=0))
    glb.doc["scenes"][0]["nodes"].append(0)
    target = output / "model.glb"
    glb.save(target)
    return target


def import_model(operator, context, path, member=""):
    if context.mode != "OBJECT":
        raise ValueError("Switch to Object Mode first")
    root = Path(bpy.path.abspath(operator.texture_root)).resolve() if operator.texture_root else None
    if root is not None and not root.is_dir():
        raise ValueError("Texture folder does not exist")
    with tempfile.TemporaryDirectory(prefix="smc_arma_") as folder:
        output = Path(folder)
        run_bridge(output, "import", path, member, output, root or "")
        data = json.loads((output / "mesh.json").read_text(encoding="utf-8"))
        target = make_glb(data, output)
        result = bpy.ops.smc.import_textured_glb(filepath=str(target), pack_images=True)
        if result != {"FINISHED"}:
            raise RuntimeError("Could not load the decoded Arma model into Blender")
    warnings = data["Warnings"]
    if warnings:
        operator.report({"WARNING"}, warnings[0][:250] + (f" (+{len(warnings) - 1} more)" if len(warnings) > 1 else ""))
    else:
        operator.report({"INFO"}, f"Imported {data['Name']}; ready for Merge Selected + DDS Atlas")
    return {"FINISHED"}


class ArmaModelEntry(bpy.types.PropertyGroup):
    pass


class ChoosePboModel(bpy.types.Operator):
    bl_idname = "smc.choose_pbo_model"
    bl_label = "Select a P3D Model"
    bl_options = {"INTERNAL", "UNDO"}

    filepath: StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    texture_root: StringProperty(options={"HIDDEN", "SKIP_SAVE"})
    models: CollectionProperty(type=ArmaModelEntry, options={"HIDDEN", "SKIP_SAVE"})
    active_model: IntProperty(default=0, min=0, options={"HIDDEN", "SKIP_SAVE"})

    def invoke(self, context, _event):
        try:
            path = source_path(self.filepath, {".pbo"})
            models = list_pbo_models(path)
            if not models:
                raise ValueError("This PBO contains no .p3d models")
            self.models.clear()
            for name in models:
                self.models.add().name = name
            self.active_model = 0
            return context.window_manager.invoke_props_dialog(self, width=620, confirm_text="Import Model")
        except (OSError, ValueError, RuntimeError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}

    def draw(self, _context):
        self.layout.label(text=f"{Path(self.filepath).name} · {len(self.models)} models")
        self.layout.template_list("UI_UL_list", "arma_pbo_models", self, "models", self, "active_model",
                                  rows=min(12, max(3, len(self.models))), sort_lock=True)

    def execute(self, context):
        try:
            if self.active_model >= len(self.models):
                raise ValueError("Select a P3D from the archive")
            return import_model(self, context, source_path(self.filepath, {".pbo"}),
                                self.models[self.active_model].name)
        except (OSError, ValueError, RuntimeError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}


class ImportArma(bpy.types.Operator, ImportHelper):
    bl_idname = "smc.import_arma"
    bl_label = "Import Arma P3D / PBO"
    bl_description = "Import a textured Arma P3D or choose a model from a PBO archive"
    bl_options = {"UNDO"}

    filter_glob: StringProperty(default="*.p3d;*.pbo", options={"HIDDEN"})
    texture_root: StringProperty(name="Texture Folder", subtype="DIR_PATH",
                                 description="Optional folder containing unpacked texture and material paths")

    def draw(self, _context):
        self.layout.prop(self, "texture_root")

    def execute(self, context):
        try:
            if context.mode != "OBJECT":
                raise ValueError("Switch to Object Mode first")
            path = source_path(self.filepath, {".p3d", ".pbo"})
            if path.suffix.lower() == ".p3d":
                return import_model(self, context, path)
            result = bpy.ops.smc.choose_pbo_model("INVOKE_DEFAULT", filepath=str(path), texture_root=self.texture_root)
            return {"FINISHED"} if result == {"RUNNING_MODAL"} else result
        except (OSError, ValueError, RuntimeError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
