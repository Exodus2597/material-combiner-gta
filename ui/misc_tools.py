"""Standalone mesh tools in the MatCombiner sidebar."""

import bpy


class MiscToolsPanel(bpy.types.Panel):
    bl_label = "Misc. Tools"
    bl_idname = "SMC_PT_Misc_Tools"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "MatCombiner"

    def draw(self, context):
        self.layout.operator("smc.create_backfaces", text="Create Backfaces", icon="MOD_SOLIDIFY")
