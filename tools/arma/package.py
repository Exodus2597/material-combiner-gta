"""Package the built Arma bridge, licensing and exact corresponding sources."""

import argparse
from pathlib import Path
import shutil
from zipfile import ZIP_DEFLATED, ZipFile

PIN = "17570f2296df6c4526e8769a02d6a76891c47c13"

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--bridge", type=Path, required=True)
parser.add_argument("--bis-source", type=Path, required=True)
parser.add_argument("--dotnet-runtime", type=Path, required=True)
args = parser.parse_args()

tools = Path(__file__).resolve().parent
root = tools.parents[1]
vendor = root / "vendor"
shutil.copyfile(args.bridge, vendor / "arma_bridge.exe")
with ZipFile(vendor / "arma_bridge_source.zip", "w", ZIP_DEFLATED) as archive:
    for name in ("ArmaBridge.csproj", "PboArchive.cs", "Program.cs", "Terminal.cs", "package.py"):
        archive.write(tools / name, name)
    for package in ("BIS.Core", "BIS.P3D", "BIS.PAA"):
        for path in sorted((args.bis_source / package).rglob("*.cs")):
            relative = path.relative_to(args.bis_source)
            if not {"bin", "obj"}.intersection(relative.parts):
                archive.write(path, "upstream/" + relative.as_posix())
    archive.write(args.bis_source / "LICENSE", "licenses/UKSFTA-BIS-MIT.txt")
    archive.write(root / "LICENSE", "licenses/GPL-3.0.txt")
    archive.write(args.dotnet_runtime / "LICENSE.txt", "licenses/dotnet-LICENSE.txt")
    archive.write(args.dotnet_runtime / "ThirdPartyNotices.txt", "licenses/dotnet-ThirdPartyNotices.txt")
    archive.writestr("UPSTREAM.txt", f"https://github.com/UKSFTA/UKSFTA-BIS/commit/{PIN}\n"
                     "BIS.Core includes a MiniLZO port under GPL-2.0-or-later; source notices retained.\n"
                     "Bundled Microsoft .NET runtime: 10.0.14, Windows x64.\n")
