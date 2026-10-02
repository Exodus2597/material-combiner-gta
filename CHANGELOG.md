# Changelog

## 2.6.3 — 2026-10-02

- Show Created by Exodus (original by shotariya).
- Remove Discord, donations and Pillow installation panels and buttons.
- Check this repository's stable releases using version tags, excluding drafts and prereleases.
- Keep updates as manual release downloads.

## 2.6.2 — 2026-10-02

- Publish the GTA edition with installation, usage, feature and validation documentation.
- Point Blender documentation, issue reporting and update notices at this repository.
- Use manual release installation instead of replacing this edition with upstream archives.
- Retain the upstream GPL-3.0 license file and MIT notices present in individual files; correct the earlier MIT-only documentation.

## 2.6.1

- Remove every vertex group and weight from merged output, preserving source groups and weights.

## 2.6.0

- Add independent diffuse and normal atlas sizes.
- Add independent A8R8G8B8 and DXT5 (BC3) output formats, complete mipmaps and resolution-scaled normal bake margins.
- Preserve exact neutral flat normals in DXT5 encoding.

## Earlier GTA edition work

- Add GLB import with external diffuse/normal texture matching and Unreal material JSON support.
- Add merged Sollumz Drawables, one output UV map and diffuse/opacity plus normal DDS export.
- Preserve original material texture sheets and their UV island arrangement; add flexible rectangular packing.
- Preserve sources, validate unsupported inputs, handle transformed normal maps and roll back failed imports/exports.
- Fix validation, resizing and save-failure handling in the original workflow.

Based on upstream commit `eed9ca2` of [Grim-es/material-combiner-addon](https://github.com/Grim-es/material-combiner-addon).
