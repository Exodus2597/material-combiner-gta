"""Write optimized RAGE model assets through Sollumz's native exporter."""

import importlib
from pathlib import Path
import re
from tempfile import TemporaryDirectory
import traceback

import bpy
from bpy.props import EnumProperty, StringProperty

from .gta_atlas import sollumz_api
from ..utils.output_files import replace_outputs
from ..utils.rage_geometry import compact_geometry


EXPORTERS = {
    "sollumz_drawable": ("ydr.ydrexport", "export_ydr", ".ydr"),
    "sollumz_drawable_dictionary": ("ydd.yddexport", "export_ydd", ".ydd"),
    "sollumz_fragment": ("yft.yftexport", "export_yft", ".yft"),
}


class ExportCompactRage(bpy.types.Operator):
    bl_idname = "smc.export_compact_rage"
    bl_label = "Export Compact RAGE"
    bl_description = "Export selected Sollumz YDR, YDD and YFT assets with smaller geometry buffers"

    directory: StringProperty(name="Output Folder", subtype="DIR_PATH")
    game_version: EnumProperty(name="GTA V Version", items=(
        ("GEN8", "Legacy (Gen8)", "GTA V Legacy resource files"),
        ("GEN9", "Enhanced (Gen9)", "GTA V Enhanced resource files"),
    ), default="GEN8")

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and bool(context.selected_objects)

    def draw(self, context):
        self.layout.prop(self, "game_version")
        self.layout.label(text="Replaces files with matching export names.")

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {"RUNNING_MODAL"}

    def execute(self, context):
        try:
            paths = self.export(context)
        except (ValueError, OSError, RuntimeError) as error:
            self.report({"ERROR"}, str(error))
            return {"CANCELLED"}
        except Exception:
            traceback.print_exc()
            self.report({"ERROR"}, "Sollumz export failed. See Blender's system console for details.")
            return {"CANCELLED"}
        total = sum(path.stat().st_size for path in paths)
        self.report({"INFO"}, f"Exported {len(paths)} RAGE file(s), {total / 1024:.1f} KiB")
        return {"FINISHED"}

    def export(self, context):
        _, helper = sollumz_api()
        root = helper.__package__.rsplit(".tools", 1)[0]

        def module(name):
            return importlib.import_module(f"{root}.{name}")

        from szio.gta5 import AssetFormat, AssetTarget, AssetVersion, is_provider_available

        target = AssetTarget(AssetFormat.NATIVE, AssetVersion[self.game_version])
        if not is_provider_available(target):
            raise ValueError("Enable PyMateria in Sollumz to export native RAGE files")
        parent = module("sollumz_helper").find_sollumz_parent
        selected = {parent(obj) for obj in context.selected_objects}
        assets = sorted((obj for obj in selected if obj and obj.sollum_type in EXPORTERS), key=lambda obj: obj.name)
        if not assets:
            raise ValueError("Select a Sollumz Drawable, Drawable Dictionary or Fragment")
        destination = Path(bpy.path.abspath(self.directory))
        if not self.directory or not destination.is_dir():
            raise ValueError("Choose an existing output folder")

        ie = module("iecontext")
        logger = module("logger")
        settings = module("sollumz_preferences").get_export_settings().to_export_context_settings()
        settings.targets = (target,)
        name_for = module("tools.blenderhelper").remove_number_suffix
        exporter = module("ydr.ydrexport")
        cloth = module("ydr.cloth_env")
        if not all(hasattr(cloth, name) for name in ("cloth_env_export", "_cloth_env_export")):
            raise ValueError("This Sollumz exporter version is incompatible. Use Sollumz 2.9.0.")

        outputs = []
        with TemporaryDirectory(dir=destination, prefix=".smc_export_") as folder:
            staging = Path(folder)
            expected = set()
            with logger.use_operator_logger(self) as log, compact_geometry(exporter):
                for index, obj in enumerate(assets):
                    name = name_for(obj.name.lower())
                    if not name or name in {".", ".."} or re.search(r'[<>:"/\\|?*\x00-\x1f]', name):
                        raise ValueError(f"{obj.name}: use a valid filename for the Sollumz asset")
                    path, function, extension = EXPORTERS[obj.sollum_type]
                    log.clear_log_counts()
                    with ie.export_context_scope(ie.ExportContext(name, settings)):
                        bundle = getattr(module(path), function)(obj)
                    if not bundle:
                        raise ValueError(f"{obj.name}: Sollumz produced no exportable asset")
                    output = staging / str(index)
                    output.mkdir()
                    bundle.save(output, settings.targets)
                    if log._num_logs["ERROR"]:
                        raise ValueError(f"{obj.name}: Sollumz reported an export error")
                    if not (output / (name + extension)).is_file():
                        raise ValueError(f"{obj.name}: Sollumz did not write the expected {extension}")
                    for file in sorted(output.iterdir()):
                        target_path = destination / file.name
                        if not file.is_file() or not file.stat().st_size:
                            raise ValueError(f"{file.name}: invalid Sollumz export")
                        if file.name.casefold() in expected:
                            raise ValueError(f"Selected assets export the same filename: {file.name}")
                        expected.add(file.name.casefold())
                        outputs.append((file, target_path))
            replace_outputs(outputs)
        return [target for _, target in outputs]
