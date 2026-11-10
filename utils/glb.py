"""Minimal GLB writer for textured model import bridges."""

import json
import struct


class GLB:
    def __init__(self):
        self.data = bytearray()
        self.doc = dict(asset={"version": "2.0", "generator": "Exodus Material Combiner"},
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
