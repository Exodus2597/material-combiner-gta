"""Build the Blender installation ZIP from tracked files in this Git checkout."""

import ast
from pathlib import Path
import subprocess
import zipfile

root = Path(__file__).resolve().parent.parent
tree = ast.parse((root / '__init__.py').read_text(encoding='utf-8'))
info = next(ast.literal_eval(node.value) for node in tree.body
            if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and target.id == 'bl_info'
                                                   for target in node.targets))
version = '_'.join(map(str, info['version']))
files = subprocess.check_output(['git', '-c', 'safe.directory=' + root.as_posix(), 'ls-files', '-z'], cwd=root)
destination = root / 'dist' / f'material_combiner_gta_{version}.zip'
destination.parent.mkdir(exist_ok=True)
with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
    for name in sorted(files.decode('utf-8').split('\0')):
        if name and not name.startswith(('.github/', '.vscode/', 'tests/', 'tools/')):
            archive.write(root / name, 'material_combiner_gta/' + name)
with zipfile.ZipFile(destination) as archive:
    if archive.testzip() is not None:
        raise RuntimeError('Installation ZIP failed integrity check')
print(destination)
