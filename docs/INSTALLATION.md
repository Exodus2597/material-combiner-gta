# Installation and updates

Tested configuration: **Blender 5.2.1 LTS, Sollumz 2.9.0, Windows**. Other Blender/Sollumz combinations have not been validated for the GTA workflow.

1. Install and enable [Sollumz](https://github.com/Sollumz/Sollumz).
2. Download **`material_combiner_gta_2_7_0.zip`** from [Releases](https://github.com/Exodus2597/material-combiner-gta/releases/latest). Use this asset, rather than GitHub's automatically generated source archives.
3. Disable any previous Material Combiner installation. Different editions share operator names and must not run together.
4. Open **Edit → Preferences → Add-ons → menu → Install from Disk** in Blender.
5. Select the ZIP without extracting it and enable **Exodus' Material Combiner**.
6. In the 3D viewport, press **N** and open **MatCombiner**. The GTA section contains **Import GLB + Textures** and **Merge Selected + DDS Atlas**.

Version **2.7.0** also includes **Import OVL + Textures**, the optional backface merge setting and **Misc. Tools → Create Backfaces**. The standalone tool requires only Blender; Sollumz is needed for the GTA merge/export workflow. See [usage](USAGE.md).

Older published versions appear under the original add-on name. Version 2.6.6 appears as **Exodus' Material Combiner**.

Cycles must be available. DDS export uses Blender's bundled NumPy and does not require Pillow, texconv or an external DDS encoder. Pillow is needed only for the original PNG/PBR combining workflow.

## OVL requirements

- Install [Cobra Tools](https://github.com/OpenNaja/cobra-tools) separately, including its texture converter. The selected source folder must contain `generated` and `modules`; Cobra sources and game assets are not distributed here.
- Install external **Python 3.11** with Cobra's dependencies, including `numpy`, `Pillow` and `imageio`. Use the dependency instructions supplied with your Cobra version.
- The tested Planet Zoo 2 setup uses Cobra Tools 2026.10.11 with local format-54 patches for archive/game detection, model decoding and texture extraction. These external Cobra patches are not bundled; an unmodified Cobra installation is not validated for Planet Zoo 2. The add-on's Sea Fan/foliage adapters do not replace that dependency. Updating Cobra may remove local patches.
- In **Import OVL + Textures → Advanced Paths**, choose **Cobra Tools Folder** and **Python Executable** if automatic discovery does not locate them. Keep the archive's `.ovs`/`.aux` companions beside its `.ovl`.
- OVL support depends on Cobra's game/format support. Unsupported or malformed archives stop with an error. GLB import, DDS generation and standalone backfaces do not need external Python or Cobra.

## Updating

Save your blend, disable the older GTA edition and install the new release ZIP. Restart Blender if it retains an older module. Existing projects and exported DDS files remain separate from the add-on installation.

**Check now for update** checks stable releases at **Exodus2597/material-combiner-gta** using version tags. Drafts and prereleases are excluded. Updates use manual installation from this repository's release page. When the installed version matches or exceeds the newest stable release, the panel reports that the add-on is up to date.

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

For unresolved issues, [open a bug report](https://github.com/Exodus2597/material-combiner-gta/issues) with Blender, Sollumz and add-on versions, selected atlas settings, reproduction steps and the error text. Remove private paths or assets before posting.
