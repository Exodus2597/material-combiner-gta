"""Import Cobra OVL assets through the existing textured GLB workflow."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

import addon_utils
import bpy
from bpy.props import BoolProperty, EnumProperty, StringProperty
from bpy_extras.io_utils import ImportHelper


def cobra_directory(explicit):
    if explicit:
        roots = [Path(bpy.path.abspath(explicit)).resolve()]
    else:
        roots = sorted({Path(module.__file__).resolve().parent for module in addon_utils.modules()
                        if module.bl_info.get("name") == "Frontier's Cobra Engine Formats"})
    if len(roots) != 1:
        raise ValueError("Install Cobra Tools, or choose its folder under Advanced Paths")
    root = roots[0]
    if not all((root / name).is_file() for name in ("generated/formats/ovl/__init__.py", "modules/formats/DDS.py")):
        raise ValueError("Choose the Cobra Tools folder containing generated and modules")
    return root


def python_executable(explicit):
    if explicit:
        candidates = [Path(bpy.path.abspath(explicit))]
    else:
        candidates = []
        if os.name == "nt":
            import winreg
            for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
                try:
                    with winreg.OpenKey(hive, r"Software\Python\PythonCore\3.11\InstallPath") as key:
                        candidates.append(Path(winreg.QueryValueEx(key, "ExecutablePath")[0]))
                except OSError:
                    pass
            candidates.append(Path(os.environ.get("LOCALAPPDATA", "")) / "Programs/Python/Python311/python.exe")
        found = shutil.which("python3.11")
        if found:
            candidates.append(Path(found))
    for candidate in candidates:
        if candidate.is_file() and candidate.suffix.lower() not in {".bat", ".cmd"}:
            return candidate.resolve()
    raise ValueError("Cobra extraction needs Python 3.11 with Cobra's dependencies. Choose Python Executable under Advanced Paths")


class ImportTexturedOVL(bpy.types.Operator, ImportHelper):
    bl_idname = "smc.import_textured_ovl"
    bl_label = "Import OVL + Diffuse / Normal Textures"
    bl_description = "Extract highest-detail static meshes and textures with Cobra Tools, ready for GTA atlas merging"
    bl_options = {"REGISTER", "UNDO"}
    filename_ext = ".ovl"
    filter_glob: StringProperty(default="*.ovl", options={"HIDDEN"})
    game: EnumProperty(name="Source Game", default="AUTO", items=[
        ("AUTO", "Automatic", "Use Cobra detection, including the original Planet Zoo 2 folder path"),
        ("Planet Zoo 2", "Planet Zoo 2", "Requires the Planet Zoo 2 Cobra patch"),
        ("Planet Zoo", "Planet Zoo", "Use Planet Zoo archive decoding"),
        ("Planet Coaster 2", "Planet Coaster 2", "Use Planet Coaster 2 archive decoding"),
        ("Jurassic World Evolution 2", "Jurassic World Evolution 2", "Use Jurassic World Evolution 2 archive decoding")])
    shared_archive: StringProperty(name="Shared Textures OVL", subtype="FILE_PATH",
                                   description="Optional second archive containing externally referenced materials/textures")
    texture_folder: StringProperty(name="Shared Texture Folder", subtype="DIR_PATH",
                                   description="Optional folder of Cobra-extracted PNGs for missing shared textures")
    invert_green: BoolProperty(name="Invert Normal Green", default=False,
                               description="Reverse green after Cobra's PNG conversion; leave off for Cobra-converted normals")
    remove_modifiers: BoolProperty(name="Remove All Modifiers", default=True,
                                   description="Use the same modifier cleanup as GLB import")
    advanced_paths: BoolProperty(name="Advanced Paths", default=False)
    cobra_folder: StringProperty(name="Cobra Tools Folder", subtype="DIR_PATH",
                                 description="Leave empty to find the installed Cobra add-on")
    python_path: StringProperty(name="Python Executable", subtype="FILE_PATH",
                                description="Leave empty to find Python 3.11 with Cobra's dependencies")

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "game")
        layout.prop(self, "shared_archive")
        layout.prop(self, "texture_folder")
        layout.prop(self, "invert_green")
        layout.prop(self, "remove_modifiers")
        layout.label(text="Highest-detail static meshes; textures packed into blend.")
        layout.prop(self, "advanced_paths")
        if self.advanced_paths:
            layout.prop(self, "cobra_folder")
            layout.prop(self, "python_path")

    def execute(self, context):
        try:
            if context.mode != "OBJECT":
                raise ValueError("Switch to Object Mode first")
            path = Path(bpy.path.abspath(self.filepath)).resolve()
            if path.suffix.lower() != ".ovl" or not path.is_file():
                raise ValueError("Choose an existing .ovl file and keep its .ovs/.aux companions alongside it")
            cobra = cobra_directory(self.cobra_folder)
            python = python_executable(self.python_path)
            worker = Path(__file__).resolve().parent.parent / "utils/ovl_extract.py"
            with tempfile.TemporaryDirectory(prefix="smc_ovl_") as folder:
                output = Path(folder)
                command = [str(python), str(worker), "--cobra", str(cobra), "--source", str(path), "--output", folder]
                if self.game != "AUTO":
                    command.extend(("--game", self.game))
                for option, value, directory in (("--shared-archive", self.shared_archive, False),
                                                  ("--texture-folder", self.texture_folder, True)):
                    if value:
                        asset = Path(bpy.path.abspath(value)).resolve()
                        if (directory and not asset.is_dir()) or (not directory and (not asset.is_file() or asset.suffix.lower() != ".ovl")):
                            raise ValueError(f"Invalid path for {option[2:].replace('-', ' ')}")
                        command.extend((option, str(asset)))
                if self.invert_green:
                    command.append("--invert-green")
                result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                        timeout=300, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
                if result.returncode:
                    error = output / "error.json"
                    detail = json.loads(error.read_text(encoding="utf-8"))["error"] if error.is_file() else result.stderr[-1200:]
                    raise ValueError("Cobra OVL extraction failed: " + detail)
                manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
                if bpy.ops.smc.import_textured_glb(filepath=str(output / "model.glb"),
                                                  remove_modifiers=self.remove_modifiers, pack_images=True) != {"FINISHED"}:
                    raise RuntimeError("Extracted OVL model could not be imported")
            for warning in manifest["warnings"]:
                self.report({"WARNING"}, warning)
            self.report({"INFO"}, f"Imported OVL: {manifest['meshes']} meshes, {manifest['diffuse_maps']} diffuse maps, "
                                  f"{manifest['normal_maps']} normal maps. Use Merge Selected + DDS Atlas next")
            return {"FINISHED"}
        except subprocess.TimeoutExpired:
            self.report({"ERROR"}, "Cobra extraction timed out; choose a model-specific OVL rather than a large combined archive")
            return {"CANCELLED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
