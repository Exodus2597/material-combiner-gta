# Installation and updates

Tested configuration: **Blender 5.2.1 LTS, Sollumz 2.9.0, Windows**. Other Blender/Sollumz combinations have not been validated for the GTA workflow.

1. Install and enable [Sollumz](https://github.com/Sollumz/Sollumz).
2. Download **`material_combiner_gta_2_6_2.zip`** from [Releases](https://github.com/Exodus2597/material-combiner-gta/releases/latest). Use this asset, rather than GitHub's automatically generated source archives.
3. Disable any previous Material Combiner installation. Different editions share operator names and must not run together.
4. Open **Edit → Preferences → Add-ons → menu → Install from Disk** in Blender.
5. Select the ZIP without extracting it and enable **Shotariya's Material Combiner**.
6. In the 3D viewport, press **N** and open **MatCombiner**. The GTA section contains **Import GLB + Textures** and **Merge Selected + DDS Atlas**.

Cycles must be available. DDS export uses Blender's bundled NumPy and does not require Pillow, texconv or an external DDS encoder. Pillow is needed only for the original PNG/PBR combining workflow.

## Updating

Save your blend, disable the older GTA edition and install the new release ZIP. Restart Blender if it retains an older module. Existing projects and exported DDS files remain separate from the add-on installation.

Update notices point to this repository's releases. Updates use manual installation to preserve the GTA edition's packaging; they do not install the upstream edition over this fork.

## Troubleshooting

| Problem | Check |
| --- | --- |
| GTA buttons missing | Enable this edition; disable duplicate Material Combiner editions; reopen the viewport sidebar. |
| Sollumz unavailable | Enable Sollumz 2.9.0 in the same Blender installation. |
| Merge cancelled in Edit Mode | Return to Object Mode and select mesh objects. |
| Output already exists | Choose a new lowercase filename containing letters, digits and underscores. Existing files are protected. |
| Textures not found on GLB import | Set Texture Export Folder to the export root; retain material JSON sidecars and their relative texture paths. |
| Ambiguous texture match | Use an export with exact material JSON references or correct the material/texture names. |
| Normal map looks inverted | Select the source normal convention on import. Unreal exports normally use DirectX; Blender materials use OpenGL (+Y). Output normals use GTA DirectX (-Y). |
| Pillow installation repeats in original PNG workflow | The GTA DDS workflow does not use Pillow. See [upstream Pillow troubleshooting](https://github.com/Grim-es/material-combiner-addon#pillow-installation-process-is-repeated) for the legacy workflow. |

For unresolved issues, [open a bug report](https://github.com/Exodus2597/material-combiner-gta/issues) with Blender, Sollumz and add-on versions, selected atlas settings, reproduction steps and the error text. Remove private paths or assets before posting.
