"""Offline tests for the bundled decoder; no game files required."""

import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import unittest

BRIDGE = Path(__file__).resolve().parents[1] / "vendor/arma_bridge.exe"
ENTRY = struct.Struct("<4sIIII")


def lod(resolution, scale):
    points = [(0, 0, 0), (scale, 0, 0), (0, scale, 0)]
    return (b"P3DM" + struct.pack("<6I", 28, 256, 3, 1, 1, 0)
            + b"".join(struct.pack("<3fI", *point, 0) for point in points)
            + struct.pack("<3fI", 0, 0, 1, 3)
            + b"".join(struct.pack("<IIff", i, 0, float(i == 1), float(i == 2)) for i in range(3))
            + bytes(16 + 4 + 2) + b"TAGG\x01#EndOfFile#\x00" + bytes(4) + struct.pack("<f", resolution))


def mlod():
    return b"MLOD" + struct.pack("<II", 257, 3) + lod(10000, 12) + lod(4, 4) + lod(1, 1)


def literal_lzss(data):
    return (b"".join(b"\xff" + data[i:i + 8] for i in range(0, len(data), 8))
            + struct.pack("<I", sum(data)))


def pbo(entries):
    header = bytearray(b"\0" + ENTRY.pack(b"sreV", 0, 0, 0, 0) + b"prefix\0fixture\0\0")
    payload = bytearray()
    for name, raw, compressed in entries:
        data = literal_lzss(raw) if compressed else raw
        header.extend(name.encode() + b"\0" + ENTRY.pack(b"srpC" if compressed else bytes(4),
                                                         len(raw) if compressed else 0, 0, 0, len(data)))
        payload.extend(data)
    return header + bytes(21) + payload


@unittest.skipUnless(os.name == "nt", "Bundled Arma bridge targets Windows x64")
class ArmaBridgeTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def bridge(self, *args, ok=True):
        result = subprocess.run([str(BRIDGE), *map(str, args)], cwd=self.root, timeout=20,
                                env={**os.environ, "DOTNET_ROOT": "X:/no-dotnet", "PATH": "",
                                     "DOTNET_BUNDLE_EXTRACT_BASE_DIR": str(self.root / "runtime")},
                                capture_output=True, text=True, encoding="utf-8", errors="replace")
        self.assertEqual(result.returncode == 0, ok, result.stderr)
        return result

    def test_loose_and_compressed_member(self):
        raw = mlod()
        loose = self.root / "model.p3d"
        loose.write_bytes(raw)
        archive = self.root / "fixture.pbo"
        archive.write_bytes(pbo([("second\\model.P3D", raw, True),
                                 ("first\\model.p3d", raw, False), ("notes.txt", b"hello", False),
                                 ("../escape.p3d", raw, False)]))
        index = self.root / "list.json"
        self.bridge("list", archive, index)
        self.assertEqual(json.loads(index.read_text()), ["first/model.p3d", "second/model.P3D"])
        self.bridge("import", loose, "", self.root, "")
        output = self.root / "mesh.json"
        result = json.loads(output.read_text())
        self.assertEqual(result["Faces"], 1)
        self.assertEqual(result["Parts"][0]["Positions"], [0, 0, 0, 1, 0, 0, 0, 1, 0])
        self.bridge("import", archive, "second/model.P3D", self.root, "")
        self.assertEqual(result, json.loads(output.read_text()))
        self.assertFalse((self.root.parent / "escape.p3d").exists())

    def test_corrupt_archive_and_unknown_model(self):
        archive = self.root / "broken.pbo"
        archive.write_bytes(pbo([("model.p3d", mlod(), False)])[:-1])
        result = self.bridge("list", archive, self.root / "list.json", ok=False)
        self.assertIn("archive size", result.stderr)
        model = self.root / "unsupported.p3d"
        model.write_bytes(b"ODOL" + struct.pack("<II", 7, 1))
        result = self.bridge("import", model, "", self.root, "", ok=False)
        self.assertIn("ODOL v7 is unsupported", result.stderr)
        self.assertFalse((self.root / "mesh.json").exists())


if __name__ == "__main__":
    unittest.main()
