# Bundled OVL runtime

`ovl_runtime_win64_cp313.zip` contains the offline OVL decoder, its source and dependency licenses. Install the normal add-on release ZIP; do not install this archive separately. Runtime files unpack into the import's private temporary directory and are removed after the worker exits. No dependency downloads, pip installs or changes to Blender's Python environment occur during use.

## Contents and provenance

- [Cobra Tools](https://github.com/OpenNaja/cobra-tools), version **2026.10.11**, upstream commit **fe5d39d34adbd5c080c6d1b4c489ce6ab73a36a9**. GPL-3.0 license, runtime Python sources, source schemas and code generator are included under `cobra/`.
- Exodus modifications include Planet Zoo 2 archive/game detection and dependency ordering, format-54 model/weight decoding, MS2 game sidecars, intact PZ2 texture channel extraction, a game-owned Oodle DLL adapter and an actionable missing-Oodle error. Additional static Sea Fan/32-byte foliage handling remains in the add-on's extraction worker.
- Microsoft's **texconv** is included with its MIT license under `cobra/modules/formats/utils/texconv/`. No other Cobra executables or third-party Oodle DLL are redistributed.
- **Pillow 13.0.0**, **imageio 2.37.2** and **bitarray 3.8.0** come from the official PyPI wheels recorded in `ovl_runtime.json`. Their complete wheel contents and original licenses are retained under `packages/`. The manifest pins wheel URLs/SHA256 hashes and the final runtime archive hash. Blender supplies Python and NumPy.

The bundled dependencies target **Windows x64 / CPython 3.13**, as supplied by tested Blender **5.2.1 LTS**. The Cobra GUI, Blender operators, unrelated audio tools and game files are excluded. This is a static OVL import runtime, not a separate installation of the complete Cobra application.

## Oodle-compressed archives

The proprietary Oodle DLL is **not included**. The worker automatically locates an existing `oo2core_*_win64.dll` in the installed game's root/Win64 folders around `ovldata`, using the newest numbered candidate. For archives copied elsewhere, select that existing game DLL under **Advanced Paths → Oodle Library**. The DLL is loaded from its original location and never copied into a release or written to. The tested Planet Zoo 2 installation uses its own version-9 DLL. Zlib/uncompressed archives do not need it.

## Rebuilding

`tools/build_ovl_runtime.py --cobra /path/to/patched-cobra` builds a deterministic archive from the patched Cobra source tree, retaining source schemas and licensing. It downloads only the pinned official wheels, verifies their SHA256 hashes, applies the Oodle adapter/error changes and updates the archive manifest. No game DLL is packaged. To inspect, modify or rebuild the bundled Cobra version, extract `cobra/` from the archive and use it as that source tree. Review all dependency/provenance changes before replacing the manifest or archive.
