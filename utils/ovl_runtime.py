"""Offline OVL dependencies, loaded only by the isolated extraction process."""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import sys
import zipfile


def unpack_runtime(destination):
    vendor = Path(__file__).resolve().parent.parent / 'vendor'
    lock = json.loads((vendor / 'ovl_runtime.json').read_text(encoding='utf-8'))
    if (os.name != 'nt' or platform.machine().lower() not in {'amd64', 'x86_64'}
            or list(sys.version_info[:2]) != lock['python']):
        raise ValueError('Bundled OVL import requires Windows x64 and Blender 5.2 Python 3.13')
    archive_path = vendor / lock['archive']
    with archive_path.open('rb') as stream:
        if hashlib.file_digest(stream, 'sha256').hexdigest() != lock['sha256']:
            raise ValueError('Bundled OVL runtime is damaged; reinstall the release ZIP')
    with zipfile.ZipFile(archive_path) as archive:
        entries = archive.infolist()
        names = set()
        for entry in entries:
            name = entry.orig_filename
            path = PurePosixPath(name)
            if (not path.parts or path.is_absolute() or '..' in path.parts or chr(92) in name
                    or ':' in name or '\0' in name or (entry.external_attr >> 16) & 0o170000 == 0o120000
                    or path.parts[0] not in {'cobra', 'packages'} or name.lower() in names):
                raise ValueError('Unsafe path in bundled OVL runtime')
            names.add(name.lower())
        if len(entries) != lock['files'] or sum(entry.file_size for entry in entries) != lock['unpacked_bytes']:
            raise ValueError('Invalid bundled OVL runtime contents')
        archive.extractall(destination)
    destination = Path(destination)
    sys.path.insert(0, str(destination / 'packages'))
    return destination / 'cobra'


def game_oodle_library(source, explicit=None):
    if explicit:
        path = Path(explicit).resolve()
        if not path.is_file() or not re.fullmatch(r'oo2core_\d+_win64\.dll', path.name, re.IGNORECASE):
            raise ValueError('Choose an existing game oo2core_*_win64.dll for Oodle Library')
        return path
    # Search only the game folders around ovldata, never PATH or unrelated installs.
    for parent in Path(source).resolve().parents:
        if parent.name.lower() == 'ovldata':
            folders = (parent.parent, parent.parent.parent)
            candidates = [path for folder in folders for path in folder.glob('oo2core_*_win64.dll')
                          if path.is_file() and re.fullmatch(r'oo2core_\d+_win64\.dll', path.name, re.IGNORECASE)]
            return max(candidates, key=lambda path: (int(path.name.split('_')[1]), str(path)), default=None)
    return None
