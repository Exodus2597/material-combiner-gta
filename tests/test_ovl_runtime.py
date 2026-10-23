"""Run with Blender's standalone Python 3.13; requires no installed Cobra."""

import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import zipfile

spec = importlib.util.spec_from_file_location('ovl_runtime', Path(__file__).resolve().parents[1] / 'utils/ovl_runtime.py')
runtime = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runtime)


class RuntimeValidation(unittest.TestCase):
    def test_archive_validation(self):
        for mode in ('hash', 'count', 'size', 'traversal', 'absolute', 'drive', 'backslash', 'symlink', 'duplicate'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                vendor = root / 'vendor'
                vendor.mkdir()
                name = {'traversal': '../escape', 'absolute': '/escape', 'drive': 'cobra/C:escape',
                        'backslash': 'cobra\\escape'}.get(mode, 'cobra/file.py')
                with zipfile.ZipFile(vendor / 'runtime.zip', 'w') as archive:
                    entry = zipfile.ZipInfo(name)
                    if mode == 'symlink':
                        entry.external_attr = 0o120777 << 16
                    archive.writestr(entry, b'test')
                    if mode == 'duplicate':
                        archive.writestr(name.upper(), b'test')
                if mode == 'backslash':
                    path = vendor / 'runtime.zip'
                    path.write_bytes(path.read_bytes().replace(b'cobra/escape', b'cobra' + bytes([92]) + b'escape'))
                digest = hashlib.sha256((vendor / 'runtime.zip').read_bytes()).hexdigest()
                lock = dict(archive='runtime.zip', sha256='0' * 64 if mode == 'hash' else digest,
                            files=99 if mode == 'count' else 2 if mode == 'duplicate' else 1,
                            unpacked_bytes=99 if mode == 'size' else 8 if mode == 'duplicate' else 4,
                            python=[3, 13])
                (vendor / 'ovl_runtime.json').write_text(json.dumps(lock))
                with patch.object(runtime, '__file__', str(root / 'utils/ovl_runtime.py')):
                    with self.assertRaises(ValueError):
                        runtime.unpack_runtime(root / 'out')
                self.assertFalse((root / 'out').exists())
                self.assertFalse((root / 'escape').exists())

    def test_platform_guard(self):
        with patch.object(runtime.platform, 'machine', return_value='ARM64'):
            with self.assertRaisesRegex(ValueError, 'Windows x64'):
                runtime.unpack_runtime('unused')

    def test_game_library_selection(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / 'Win64/ovldata/Content0/model.ovl'
            source.parent.mkdir(parents=True)
            source.write_bytes(b'not-read')
            v8, v9 = root / 'Win64/oo2core_8_win64.dll', root / 'oo2core_9_win64.dll'
            v8.write_bytes(b'not-executed')
            v9.write_bytes(b'not-executed')
            self.assertEqual(runtime.game_oodle_library(source), v9)
            self.assertEqual(runtime.game_oodle_library(source, v8), v8)
            self.assertIsNone(runtime.game_oodle_library(root / 'moved/model.ovl'))
            with self.assertRaisesRegex(ValueError, 'Oodle Library'):
                runtime.game_oodle_library(source, root / 'missing.dll')


if __name__ == '__main__':
    unittest.main()
