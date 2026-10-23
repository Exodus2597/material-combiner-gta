"""Build the offline Windows OVL runtime from a patched Cobra source tree."""

import argparse
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--cobra', type=Path, required=True)
args = parser.parse_args()
vendor = root / 'vendor'
lock_path = vendor / 'ovl_runtime.json'
lock = json.loads(lock_path.read_text(encoding='utf-8'))
entries = {}
for part in ('generated', 'modules', 'utils', 'constants', 'source', 'codegen'):
    for path in (args.cobra / part).rglob('*'):
        if path.is_file() and path.suffix in {'.py', '.xml', '.xsd', '.json'} and '__pycache__' not in path.parts:
            entries['cobra/' + path.relative_to(args.cobra).as_posix()] = path.read_bytes()
for name in ('LICENSE', 'README.md', 'pyproject.toml', '__version__.py',
             'modules/formats/utils/texconv/texconv.exe', 'modules/formats/utils/texconv/LICENSE'):
    entries['cobra/' + name] = (args.cobra / name).read_bytes()

# Keep the game-owned Oodle DLL outside the distribution. The worker locates it.
name = 'cobra/modules/formats/utils/oodle/oodle.py'
text = entries[name].decode('utf-8').replace('\r\n', '\n')
old = 'oodle_dll = os.path.join(os.path.dirname(__file__), "oo2core_8_win64.dll")'
new = 'oodle_dll = os.environ.get("EXODUS_OVL_OODLE", "")'
assert old in text or new in text, 'Review Oodle adapter against this Cobra version'
entries[name] = text.replace(old, new).encode('utf-8')
for part in ('generated', 'source'):
    name = f'cobra/{part}/formats/ovl/__init__.py'
    text = entries[name].decode('utf-8').replace('\r\n', '\n')
    old = '\t\t\t\tif not oodle_compressor:\n\t\t\t\t\treporter.show_error(f"Can\'t run Oodle to decompress this archive")\n\t\t\t\t\traise'
    new = '\t\t\t\tif not oodle_compressor:\n\t\t\t\t\traise RuntimeError("Oodle decompression needs the game DLL. Keep the OVL in its installed game folder, or select Oodle Library under Advanced Paths")'
    assert old in text or new in text, 'Review Oodle error handling against this Cobra version'
    entries[name] = text.replace(old, new).encode('utf-8')

for wheel in lock['wheels']:
    request = urllib.request.Request(wheel['url'], headers={'User-Agent': 'Exodus-Material-Combiner-build'})
    with urllib.request.urlopen(request, timeout=60) as response:
        raw = response.read()
    assert hashlib.sha256(raw).hexdigest() == wheel['sha256'], wheel['filename']
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        for entry in archive.infolist():
            if not entry.is_dir():
                name = 'packages/' + entry.filename
                assert name not in entries
                entries[name] = archive.read(entry)

archive_path = vendor / lock['archive']
with zipfile.ZipFile(archive_path, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
    for name, raw in sorted(entries.items()):
        entry = zipfile.ZipInfo(name, date_time=(2026, 10, 23, 0, 0, 0))
        entry.compress_type = zipfile.ZIP_DEFLATED
        entry.external_attr = 0o100644 << 16
        archive.writestr(entry, raw)
lock['sha256'] = hashlib.sha256(archive_path.read_bytes()).hexdigest()
lock['unpacked_bytes'] = sum(map(len, entries.values()))
lock['files'] = len(entries)
lock_path.write_text(json.dumps(lock, indent=2) + '\n', encoding='utf-8')
print(archive_path.name, archive_path.stat().st_size, 'bytes;', len(entries), 'files;', lock['sha256'])
