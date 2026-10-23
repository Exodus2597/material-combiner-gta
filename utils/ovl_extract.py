"""Cobra extraction worker. Runs in an isolated Python process, never in Blender.

Outputs a standard, self-contained GLB for the existing Blender import pipeline.
The release bundles patched Cobra sources and dependencies; no game assets are bundled.
"""

import argparse
import json
import logging
import os
from pathlib import Path
import struct
import sys

sys.dont_write_bytecode = True


def safe_name(name):
    if not name or name in {".", ".."} or any(c in name for c in ("/", "\\", ":", "\0")):
        raise ValueError(f"Unsafe archive filename: {name!r}")
    return name


def read_pz2_foliage32(mesh):
    """Read static PZ2 format 4: a 16-byte box, then 32-byte vertex records."""
    if not (getattr(mesh.context, "planet_zoo_2", False) and mesh.context.version == 54):
        return False
    import numpy as np
    from generated.formats.ms2.structs.packing_utils import unpack_swizzle_vectorized

    mesh.read_chunk_infos()
    formats = {int(chunk.weights_flag) & 7 for chunk in mesh.vert_chunks}
    if 4 not in formats:
        return False
    if formats != {4} or any(int(chunk.weights_flag) != 4 for chunk in mesh.vert_chunks):
        raise ValueError("Unsupported mixed/weighted PZ2 foliage-32 layout")
    if (not len(mesh.vert_chunks) or len(mesh.vert_chunks) != len(mesh.tri_chunks)
            or sum(chunk.vertex_count for chunk in mesh.vert_chunks) != mesh.vertex_count
            or sum(chunk.tris_count for chunk in mesh.tri_chunks) != mesh.tris_count):
        raise ValueError("PZ2 foliage-32 chunk counts disagree with the mesh header")

    def read(stream, offset, size):
        if offset < 0 or size < 0:
            raise ValueError("Invalid PZ2 foliage-32 buffer range")
        stream.seek(offset)
        data = stream.read(size)
        if len(data) != size:
            raise ValueError("Truncated PZ2 foliage-32 vertex/triangle buffer")
        return data

    dtype = np.dtype(dict(names=["pos", "u", "v"], formats=[("<f2", 3), "<f2", "<f2"],
                          offsets=[0, 6, 14], itemsize=32))
    positions, uvs, triangles = [], [], []
    vertex_offset = triangle_offset = 0
    for vert, tri in zip(mesh.vert_chunks, mesh.tri_chunks):
        count = int(vert.vertex_count)
        if not count or tri.value_min != vertex_offset or tri.tris_index != triangle_offset:
            raise ValueError("Unsupported PZ2 foliage-32 chunk index ranges")
        data = read(mesh.buffer_info.verts, int(vert.vertex_offset), 16 + count * 32)
        bounds = np.frombuffer(data, dtype="<f2", count=6).astype(np.float32)
        records = np.frombuffer(data, dtype=dtype, count=count, offset=16)
        coords = records["pos"].astype(np.float32)
        texcoords = np.column_stack((records["u"], 1.0 - records["v"])).astype(np.float32)
        if (not np.isfinite(bounds).all() or np.any(bounds[:3] > bounds[3:])
                or not np.isfinite(coords).all() or not np.isfinite(texcoords).all()
                or np.any(coords < bounds[:3] - .002) or np.any(coords > bounds[3:] + .002)):
            raise ValueError("Invalid PZ2 foliage-32 positions, bounds or UVs")
        indices = np.frombuffer(read(mesh.buffer_info.tris, int(tri.tris_offset), int(tri.tris_count) * 3), dtype=np.uint8)
        if len(indices) and int(indices.max()) >= count:
            raise ValueError("PZ2 foliage-32 triangle refers outside its vertex chunk")
        positions.append(coords)
        uvs.append(texcoords)
        triangles.append(indices.astype(np.uint32) + vertex_offset)
        vertex_offset += count
        triangle_offset += int(tri.tris_count)
    mesh.vertices = np.concatenate(positions)
    unpack_swizzle_vectorized(mesh.vertices)
    mesh.uvs = np.concatenate(uvs)[:, None, :]
    mesh.tri_indices = np.concatenate(triangles)
    mesh.mesh_format = 4
    return True


def load_static_model(model_file, path):
    from generated.formats.ms2.structs.ModelReader import ModelReader
    from generated.formats.ms2.structs.ChunkedMesh import ChunkedMesh

    original = ModelReader.assign_bone_info
    original_vertices = ChunkedMesh.read_verts
    vertex_errors = []
    size = path.stat().st_size

    def read_vertices(mesh):
        try:
            if not read_pz2_foliage32(mesh):
                return original_vertices(mesh)
        except Exception as exc:
            # Cobra logs and swallows population errors. Do not import partial meshes.
            vertex_errors.append(exc)
            raise

    def assign(reader, index, model, stream):
        if not (getattr(reader.context, "planet_zoo_2", False) and reader.context.version == 54):
            return original(reader, index, model, stream)
        # PZ2 keeps geometry separate from its unsupported vegetation/rig data.
        # Skip the declared bone block, never guess alignment or suppress errors.
        start = reader.buffer_1_start
        end = start + reader.arg.bone_info_size
        if not 0 <= start <= end <= size:
            raise ValueError("MS2 bone block extends outside the model file")
        stream.seek(end)
        model.bone_info = None
        return index + bool(model.increment_flag)

    ModelReader.assign_bone_info = assign
    ChunkedMesh.read_verts = read_vertices
    try:
        model_file.load(str(path), read_editable=True)
        if vertex_errors:
            raise ValueError(f"Cobra could not decode mesh vertices: {vertex_errors[0]}") from vertex_errors[0]
    finally:
        ModelReader.assign_bone_info = original
        ChunkedMesh.read_verts = original_vertices


class GLB:
    def __init__(self):
        self.data = bytearray()
        self.doc = dict(asset={"version": "2.0", "generator": "Exodus Material Combiner OVL bridge"},
                        scene=0, scenes=[{"nodes": []}], nodes=[], meshes=[], materials=[],
                        textures=[], images=[], bufferViews=[], accessors=[], buffers=[])

    def view(self, data):
        self.data.extend(b"\0" * (-len(self.data) % 4))
        index = len(self.doc["bufferViews"])
        self.doc["bufferViews"].append(dict(buffer=0, byteOffset=len(self.data), byteLength=len(data)))
        self.data.extend(data)
        return index

    def accessor(self, values, kind, component):
        view = self.view(values.tobytes())
        accessor = dict(bufferView=view, componentType=component, count=len(values), type=kind)
        if kind == "VEC3":
            accessor.update(min=values.min(axis=0).tolist(), max=values.max(axis=0).tolist())
        index = len(self.doc["accessors"])
        self.doc["accessors"].append(accessor)
        return index

    def image(self, path):
        image_index = len(self.doc["images"])
        self.doc["images"].append(dict(bufferView=self.view(path.read_bytes()), mimeType="image/png", name=path.name))
        index = len(self.doc["textures"])
        self.doc["textures"].append(dict(source=image_index))
        return {"index": index}

    def save(self, path):
        self.doc["buffers"] = [{"byteLength": len(self.data)}]
        body = json.dumps(self.doc, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        body += b" " * (-len(body) % 4)
        binary = bytes(self.data) + b"\0" * (-len(self.data) % 4)
        path.write_bytes(struct.pack("<III", 0x46546C67, 2, 28 + len(body) + len(binary))
                         + struct.pack("<I4s", len(body), b"JSON") + body
                         + struct.pack("<I4s", len(binary), b"BIN\0") + binary)


def extract(args):
    # Import only after choosing the external runtime and Cobra source directory.
    sys.path.insert(0, str(args.cobra))
    import numpy as np
    from PIL import Image
    from generated.formats.ovl import OvlFile
    from generated.formats.ms2 import Ms2File

    logging.basicConfig(level=logging.ERROR)
    if not hasattr(logging, "success"):
        logging.success = logging.info
    out = args.output
    out.mkdir(parents=True, exist_ok=True)
    archives = []
    for source in (args.source, args.shared_archive):
        if source is None:
            continue
        archive = OvlFile()
        game = args.game or (archives[0].game if archives else "")
        commands = {"game": game} if game else {}
        archive.load(str(source), commands=commands)
        archives.append(archive)
    archive = archives[0]
    model_names = [safe_name(name) for name in archive.loaders if name.endswith(".ms2")]
    if not model_names:
        raise ValueError("OVL contains no MS2 models; select an archive containing a model")
    for current in archives:
        names = [safe_name(name) for name in current.loaders if name.endswith((".ms2", ".fgm"))]
        if names:
            # No material/texture file from another archive may silently overwrite one.
            names = [name for name in names if not (out / name).exists()]
            if names:
                current.extract(str(out), only_names=names)
    textures = {}
    materials = {}
    glb = GLB()
    shared_index = None
    report = dict(game=archive.game, meshes=0, triangles=0, diffuse_maps=0, normal_maps=0,
                  warnings=["OVL import creates static geometry; skeletons and animations are not imported"], source=str(args.source))

    def texture(reference, role):
        nonlocal shared_index
        name = safe_name(reference.strip())
        key = (name.lower(), role)
        if key in textures:
            return textures[key]
        base = Path(name).stem
        compression = ""
        owner = next((item for item in archives if name in item.loaders), None)
        if owner:
            loader = owner.loaders[name]
            if not hasattr(loader, "compression_name"):
                raise ValueError("Cobra texture decoder is unavailable. Install Cobra's imageio/Pillow dependencies in the selected Python runtime")
            compression = loader.compression_name
            owner.extract(str(out), only_names=[name])
        suffixes = (".png", "_RGBA.png", "_RGB.png") if role == "diffuse" else (
            ("_RG.png", ".png", "_RGBA.png", "_RGB.png") if role == "normal" else ("_R.png", ".png"))
        image_path = next((out / (base + suffix) for suffix in suffixes if (out / (base + suffix)).is_file()), None)
        if image_path is None and args.texture_folder:
            if shared_index is None:
                shared_index = {}
                for path in args.texture_folder.rglob("*.png"):
                    shared_index.setdefault(path.name.lower(), []).append(path)
            for suffix in suffixes:
                candidates = shared_index.get((base + suffix).lower(), [])
                if len(candidates) > 1:
                    raise ValueError(f"Ambiguous shared texture: {base + suffix}")
                if candidates:
                    image_path = candidates[0]
                    break
        if image_path is None:
            raise ValueError(f"Required {role} texture {name} is missing. Select its Shared Textures OVL or a folder of Cobra-extracted PNGs")
        with Image.open(image_path) as opened:
            image = opened.convert("RGBA")
        pixels = np.asarray(image).copy()
        if role == "normal":
            if args.invert_green:
                pixels[..., 1] = 255 - pixels[..., 1]
            # BC5 stores X/Y. Some PZ2 BC7 maps also have packed X/Y: their
            # entire blue channel is below neutral, not a tangent normal's Z.
            packed_bc7 = archive.game == "Planet Zoo 2" and "BC7" in compression and np.max(pixels[..., 2]) < 128
            if "BC5" in compression or packed_bc7 or image_path.stem.lower().endswith("_rg") or not np.any(pixels[..., 2]):
                xy = pixels[..., :2].astype(np.float32) / 127.5 - 1.0
                z = np.sqrt(np.maximum(0, 1 - np.sum(xy * xy, axis=-1)))
                pixels[..., 2] = np.rint((z * .5 + .5) * 255).astype(np.uint8)
            pixels[..., 3] = 255
        normalized = out / f"image_{len(textures)}_{role}.png"
        Image.fromarray(pixels).save(normalized)
        index = glb.image(normalized)
        textures[key] = (index, pixels)
        return index, pixels

    def material(name):
        import xml.etree.ElementTree as ET
        key = name.lower()
        safe_name(key)
        if key in materials:
            return materials[key]
        path = out / (key + ".fgm")
        if not path.is_file():
            raise ValueError(f"Required material {key}.fgm is missing from the selected archives")
        xml = ET.parse(path).getroot()
        slots = {item.get("name", "").lower(): item for item in xml.findall("./textures/textureinfo")}
        def slot(names):
            return next((slots[value.lower()] for value in names if value.lower() in slots), None)
        diffuse = slot(("pBaseColourAndMaskMap", "pBaseColourTexture", "pBaseColorTexture",
                        "pBaseColourAndMaskTexture", "pDiffuseTexture", "pDiffuseAlphaTexture", "pAlbedoTexture", "pDiffuse"))
        normal = slot(("pNormalTexture", "pNormalMapTexture", "pBaseNormalTexture", "pNormalMapTextureUnique", "pNormalTextureUnique"))
        opacity = slot(("pOpacityTexture", "pOpacityMap", "pOpacity"))
        entry = dict(name=name, pbrMetallicRoughness={"metallicFactor": 0.0, "roughnessFactor": 0.5}, doubleSided=True)
        if diffuse is None:
            raise ValueError(f"{name}: no supported base-color texture slot in FGM")
        reference = diffuse.findtext("dependency_name")
        if reference:
            info, diffuse_pixels = texture(reference, "diffuse")
            entry["pbrMetallicRoughness"]["baseColorTexture"] = info
            report["diffuse_maps"] += 1
        else:
            color = diffuse.find("./value/bytecolor")
            if color is None:
                raise ValueError(f"{name}: unsupported constant base-color value")
            rgb = np.array([int(color.get(channel, "255")) / 255 for channel in "rgb"])
            rgb = np.where(rgb <= .04045, rgb / 12.92, ((rgb + .055) / 1.055) ** 2.4)
            entry["pbrMetallicRoughness"]["baseColorFactor"] = [*rgb.tolist(), 1.0]
            diffuse_pixels = None
        if normal is not None and normal.findtext("dependency_name"):
            entry["normalTexture"] = texture(normal.findtext("dependency_name"), "normal")[0]
            report["normal_maps"] += 1
        shader = xml.get("shader_name", "").lower()
        transparent = any(token in shader for token in ("clip", "alpha", "blend", "transparent"))
        if transparent:
            entry["alphaMode"] = "BLEND" if "blend" in shader else "MASK"
            if opacity is not None and opacity.findtext("dependency_name"):
                # Dedicated opacity maps can contain translucent fin membranes.
                # MASK's default 0.5 cutoff discards those surfaces entirely.
                entry["alphaMode"] = "BLEND"
                opacity_pixels = texture(opacity.findtext("dependency_name"), "opacity")[1]
                if diffuse_pixels is None:
                    factor = entry["pbrMetallicRoughness"].pop("baseColorFactor")
                    linear = np.array(factor[:3])
                    srgb = np.where(linear <= .0031308, linear * 12.92, 1.055 * linear ** (1 / 2.4) - .055)
                    diffuse_pixels = np.full((opacity_pixels.shape[0], opacity_pixels.shape[1], 4), 255, dtype=np.uint8)
                    diffuse_pixels[..., :3] = np.rint(srgb * 255).astype(np.uint8)
                rgba = diffuse_pixels.copy()
                # Some PZ2 foliage pOpacity maps store the mask only in green.
                channel = 1 if (archive.game == "Planet Zoo 2" and opacity.get("name", "").lower() == "popacity"
                                and not np.any(opacity_pixels[..., 0]) and np.any(opacity_pixels[..., 1])) else 0
                alpha = Image.fromarray(opacity_pixels[..., channel]).resize((rgba.shape[1], rgba.shape[0]), Image.Resampling.BILINEAR)
                rgba[..., 3] = np.asarray(alpha)
                combined = out / f"material_{len(materials)}_rgba.png"
                Image.fromarray(rgba).save(combined)
                entry["pbrMetallicRoughness"]["baseColorTexture"] = glb.image(combined)
        index = len(glb.doc["materials"])
        glb.doc["materials"].append(entry)
        materials[key] = index
        return index

    for name in model_names:
        model_path = out / name
        if not model_path.is_file():
            raise ValueError(f"Cobra could not extract {name}")
        model_file = Ms2File()
        load_static_model(model_file, model_path)
        for model in model_file.model_infos:
            lod = next((lod for lod in model.model.lods if len(lod.objects)), None)
            if lod is None:
                continue
            for part_index, part in enumerate(lod.objects):
                mesh = part.mesh
                if hasattr(mesh, "tri_chunks") and len(mesh.tri_chunks) and mesh.tri_chunks[0].shell_index:
                    continue
                if not all(hasattr(mesh, field) for field in ("vertices", "uvs", "tris")):
                    raise ValueError(f"{model.name}: Cobra did not decode {type(mesh).__name__} geometry; the mesh layout may be unsupported")
                vertices = np.asarray(mesh.vertices, dtype="<f4")
                triangles = np.asarray(mesh.tris, dtype="<u4")
                source_uvs = np.asarray(mesh.uvs)
                if source_uvs.ndim != 3 or source_uvs.shape[1] < 1:
                    raise ValueError(f"{model.name}: decoded mesh has no UV0")
                uvs = np.asarray(source_uvs[:, 0], dtype="<f4")
                if (vertices.ndim != 2 or vertices.shape[1] != 3 or not len(vertices)
                        or triangles.ndim != 2 or triangles.shape[1] != 3 or not len(triangles)
                        or int(triangles.max()) >= len(vertices) or uvs.shape != (len(vertices), 2)
                        or not np.isfinite(vertices).all() or not np.isfinite(uvs).all()):
                    raise ValueError(f"{model.name}: Cobra returned invalid geometry/UVs")
                # glTF is Y-up; rotate native Blender/Cobra Z-up coordinates so
                # Blender's GLB importer restores the original orientation.
                positions = np.column_stack((vertices[:, 0], vertices[:, 2], -vertices[:, 1])).astype("<f4")
                faces = positions[triangles]
                face_normals = np.cross(faces[:, 1] - faces[:, 0], faces[:, 2] - faces[:, 0])
                normals = np.zeros_like(positions)
                for corner in range(3):
                    np.add.at(normals, triangles[:, corner], face_normals)
                lengths = np.linalg.norm(normals, axis=1)
                normals[lengths > 0] /= lengths[lengths > 0, None]
                normals[lengths == 0] = (0, 1, 0)
                if not np.isfinite(normals).all():
                    raise ValueError(f"{model.name}: geometry produced invalid normals")
                attributes = {"POSITION": glb.accessor(positions, "VEC3", 5126),
                              "NORMAL": glb.accessor(normals, "VEC3", 5126),
                              "TEXCOORD_0": glb.accessor(uvs, "VEC2", 5126)}
                primitive = dict(attributes=attributes,
                                 indices=glb.accessor(triangles.ravel(), "SCALAR", 5125),
                                 material=material(part.material.name))
                index = len(glb.doc["meshes"])
                glb.doc["meshes"].append(dict(name=f"{model.name}_{part_index}", primitives=[primitive]))
                glb.doc["nodes"].append(dict(name=f"{model.name}_{part_index}", mesh=index))
                glb.doc["scenes"][0]["nodes"].append(index)
                report["meshes"] += 1
                report["triangles"] += len(triangles)
    if not report["meshes"]:
        raise ValueError("Cobra decoded no importable highest-detail meshes")
    glb.save(out / "model.glb")
    report["warnings"] = sorted(set(report["warnings"]))
    (out / "manifest.json").write_text(json.dumps(report), encoding="utf-8")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--cobra", type=Path)
    parser.add_argument("--oodle-library", type=Path)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--game", default="")
    parser.add_argument("--shared-archive", type=Path)
    parser.add_argument("--texture-folder", type=Path)
    parser.add_argument("--invert-green", action="store_true")
    args = parser.parse_args()
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        from ovl_runtime import unpack_runtime, game_oodle_library
        if args.cobra is None:
            args.cobra = unpack_runtime(args.output / 'runtime')
        library = game_oodle_library(args.source, args.oodle_library)
        os.environ.pop('EXODUS_OVL_OODLE', None)
        if library:
            os.environ['EXODUS_OVL_OODLE'] = str(library)
        extract(args)
    except Exception as exc:
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "error.json").write_text(json.dumps({"error": str(exc)}), encoding="utf-8")
        raise


if __name__ == "__main__":
    main()
