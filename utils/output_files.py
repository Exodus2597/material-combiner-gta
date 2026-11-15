"""Replace staged export files and restore the previous set on failure."""

import os
from pathlib import Path
import shutil
import stat
import tempfile


def output_state(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(info.st_mode):
        raise OSError(f"Cannot replace {path.name}: expected a regular file")
    return info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns


def replace_outputs(outputs):
    outputs = tuple(outputs)
    states = {target: output_state(target) for _, target in outputs}
    if len(outputs) == 1:
        os.replace(*outputs[0])
        return

    backups = {}
    published = {}
    folder = Path(tempfile.mkdtemp(prefix=".smc_previous_", dir=outputs[0][1].parent))
    keep_backups = False
    try:
        for index, (target, state) in enumerate(states.items()):
            if state is not None:
                backup = folder / str(index)
                shutil.copy2(target, backup, follow_symlinks=False)
                backups[target] = backup
        for source, target in outputs:
            if output_state(target) != states[target]:
                raise OSError(f"{target.name} changed during export. Retry the export.")
            state = output_state(Path(source))
            os.replace(source, target)
            published[target] = state
    except OSError:
        failures = []
        for target, state in reversed(published.items()):
            try:
                if output_state(target) != state:
                    raise OSError("file changed during export")
                if target in backups:
                    os.replace(backups[target], target)
                else:
                    target.unlink()
            except OSError as error:
                failures.append(f"{target.name}: {error}")
        if failures:
            keep_backups = True
            raise OSError(
                f"Could not restore output files ({', '.join(failures)}). "
                f"Remaining backups: {folder}"
            ) from None
        raise
    finally:
        if not keep_backups:
            shutil.rmtree(folder, ignore_errors=True)
