# Installation and updates

Tested configuration: **Blender 5.2.1 LTS, Sollumz 2.9.0, Windows**. Other Blender/Sollumz combinations have not been validated for the GTA workflow.

1. Install and enable [Sollumz](https://github.com/Sollumz/Sollumz).
2. Download **`material_combiner_gta_2_7_1.zip`** from [Releases](https://github.com/Exodus2597/material-combiner-gta/releases/latest). Use this asset, rather than GitHub's automatically generated source archives.
3. Disable any previous Material Combiner installation. Different editions share operator names and must not run together.
4. Open **Edit → Preferences → Add-ons → menu → Install from Disk** in Blender.
5. Select the ZIP without extracting it and enable **Exodus' Material Combiner**.
6. In the 3D viewport, press **N** and open **MatCombiner**. The GTA section contains **Import GLB + Textures** and **Merge Selected + DDS Atlas**.

Version **2.7.1** also includes **Import OVL + Textures**, the optional backface merge setting and **Misc. Tools → Create Backfaces**. The standalone tool requires only Blender; Sollumz is needed for the GTA merge/export workflow. See [usage](USAGE.md).

Older published versions appear under the original add-on name. Version 2.6.6 appears as **Exodus' Material Combiner**.

Cycles must be available. DDS export uses Blender's bundled NumPy and does not require Pillow, texconv or an external DDS encoder. The original PNG/PBR workflow still needs Pillow in Blender itself; the isolated OVL bundle does not install it there.

## OVL requirements

**No separate Cobra Tools or Python installation is needed.** The release ZIP includes the patched Cobra Tools 2026.10.11 decoder, Planet Zoo 2 format-54 support, texconv and pinned Pillow/imageio/bitarray dependencies. It uses Blender's own **Python 3.13 and NumPy**. The bundled OVL runtime supports **Windows x64 / Blender 5.2**; other platforms/Python ABIs are not supported by this bundle.

1. Install the add-on ZIP normally. Do not install or unpack its nested runtime ZIP yourself.
2. Open **N → MatCombiner → Import OVL + Textures** and select the `.ovl`. Keep matching `.ovs`/`.aux` files beside it.
3. For Oodle compression, retain the game's existing `oo2core_*_win64.dll` in its game root/Win64 folder. The importer locates it around the selected archive's `ovldata` directory. Nothing is copied into the game or add-on folder.
4. For archives copied outside the game, use **Advanced Paths → Oodle Library** to select that existing game DLL. **Source Game** can override archive detection.
5. Leave **Cobra Tools Folder** and **Python Executable** blank to use the bundle. These fields are optional advanced overrides; a custom Cobra installation/runtime must supply its own compatible dependencies. The bundled dependencies require Python 3.13.

OVL import runs offline in an isolated child process. The packaged runtime is hash-checked and extracted to the import's private temporary directory, then removed after the process exits. It does not run pip, download dependencies, scan installed Cobra add-ons or modify Blender's Python packages. Cobra sources and dependency licenses are included in the runtime archive; see [bundled components](../vendor/README.md). The proprietary Oodle DLL and game assets are not included.

OVL support remains limited to supported static model formats; unsupported/malformed archives cancel import. All previous GLB, DDS and backface tools remain available.

## Updating

Save your blend, disable the older GTA edition and install the new release ZIP. Restart Blender if it retains an older module. Existing projects and exported DDS files remain separate from the add-on installation.

**Check now for update** checks stable releases at **Exodus2597/material-combiner-gta** using version tags. Drafts and prereleases are excluded. Updates use manual installation from this repository's release page. When the installed version matches or exceeds the newest stable release, the panel reports that the add-on is up to date.

## Troubleshooting

| Problem | Check |
| --- | --- |
| Oodle decompression unavailable | Keep the OVL under its installed game ovldata folder, or select the existing game DLL under Advanced Paths → Oodle Library. |
| Bundled runtime damaged | Reinstall the official release ZIP; do not alter the nested runtime archive. |
| GTA buttons missing | Enable this edition; disable duplicate Material Combiner editions; reopen the viewport sidebar. |
| Sollumz unavailable | Enable Sollumz 2.9.0 in the same Blender installation. |
| Merge cancelled in Edit Mode | Return to Object Mode and select mesh objects. |
| Output already exists | Choose a new lowercase filename containing letters, digits and underscores. Existing files are protected. |
| Textures not found on GLB import | Set Texture Export Folder to the export root; retain material JSON sidecars and their relative texture paths. |
| Ambiguous texture match | Use an export with exact material JSON references or correct the material/texture names. |
| Normal map looks inverted | Select the source normal convention on import. Unreal exports normally use DirectX; Blender materials use OpenGL (+Y). Output normals use GTA DirectX (-Y). |

For unresolved issues, [open a bug report](https://github.com/Exodus2597/material-combiner-gta/issues) with Blender, Sollumz and add-on versions, selected atlas settings, reproduction steps and the error text. Remove private paths or assets before posting.
