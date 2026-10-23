"""Standalone backface creation for selected mesh objects."""

import bpy
import numpy as np
from bpy.props import FloatProperty

from .gta_atlas import add_backfaces


class CreateBackfaces(bpy.types.Operator):
    bl_idname = "smc.create_backfaces"
    bl_label = "Create Backfaces"
    bl_description = "Add offset, reversed faces to selected meshes without merging or baking textures"
    bl_options = {"REGISTER", "UNDO"}

    backface_offset: FloatProperty(name="Backface Offset", default=0.0001, min=0.0, soft_max=0.01,
                                  subtype="DISTANCE", unit="LENGTH", precision=6,
                                  description="Distance behind the surface in Blender world units; object transforms are preserved")

    @classmethod
    def poll(cls, context):
        return context.mode == "OBJECT" and any(obj.type == "MESH" for obj in context.selected_objects)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=360)

    def draw(self, context):
        self.layout.prop(self, "backface_offset")
        self.layout.label(text="Each run doubles the face count.")
        self.layout.label(text="Selected meshes; current Sollumz LOD only.")

    def execute(self, context):
        objects = [obj for obj in context.selected_objects if obj.type == "MESH"]
        copies = []
        success = False
        try:
            if context.mode != "OBJECT" or not objects:
                raise ValueError("Select mesh objects in Object Mode")
            if not np.isfinite(self.backface_offset) or self.backface_offset < 0:
                raise ValueError("Backface Offset must be finite and nonnegative")
            for obj in objects:
                if not obj.is_editable:
                    raise ValueError(f"{obj.name}: object is read only")
                if obj.data.shape_keys:
                    raise ValueError(f"{obj.name}: shape keys are not supported by Create Backfaces")
                if not obj.data.polygons:
                    raise ValueError(f"{obj.name}: mesh has no faces")
                if not np.isfinite(np.asarray(obj.matrix_world)).all() or obj.matrix_world.determinant() == 0:
                    raise ValueError(f"{obj.name}: object transform must be finite with nonzero scale")
                if not np.isfinite(np.array([vertex.co[:] for vertex in obj.data.vertices])).all():
                    raise ValueError(f"{obj.name}: mesh has non-finite vertex coordinates")
            # Prepare every mesh before committing any object-data changes.
            for obj in objects:
                mesh = obj.data.copy()
                mesh.use_fake_user = False
                copies.append((obj, obj.data, mesh))
                add_backfaces(mesh, self.backface_offset, obj.matrix_world)
            for obj, original, mesh in copies:
                obj.data = mesh
            success = True
            self.report({"INFO"}, f"Created backfaces on {len(objects)} mesh(es)")
            return {"FINISHED"}
        except Exception as exc:
            self.report({"ERROR"}, str(exc))
            return {"CANCELLED"}
        finally:
            if not success:
                for obj, original, mesh in copies:
                    if obj.data == mesh:
                        obj.data = original
                    if mesh.users == 0:
                        bpy.data.meshes.remove(mesh)
