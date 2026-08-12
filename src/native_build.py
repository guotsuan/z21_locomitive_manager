"""Shared build support for small native Swift helpers on macOS."""

from pathlib import Path
import shutil
import subprocess
from typing import Iterable


class NativeBuildError(RuntimeError):
    """Raised when a bundled Swift helper cannot be compiled."""


def compile_swift(source_path: Path, output_path: Path,
                  module_cache: Path,
                  frameworks: Iterable[str]) -> None:
    compiler = shutil.which("swiftc")
    if not compiler:
        raise NativeBuildError(
            "Swift compiler not found. Install or update Xcode Command Line "
            "Tools.")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    module_cache.mkdir(parents=True, exist_ok=True)
    command_tail = [str(source_path)]
    for framework in frameworks:
        command_tail.extend(["-framework", framework])
    command_tail.extend([
        "-module-cache-path", str(module_cache),
        "-o", str(output_path),
    ])

    commands = [[compiler, *command_tail]]
    sdk_root = Path("/Library/Developer/CommandLineTools/SDKs")
    if sdk_root.is_dir():
        for sdk_path in sorted(sdk_root.glob("MacOSX*.sdk")):
            if not sdk_path.is_symlink():
                commands.append(
                    [compiler, "-sdk", str(sdk_path), *command_tail])

    process = None
    for command in commands:
        output_path.unlink(missing_ok=True)
        process = subprocess.run(command, capture_output=True, text=True,
                                 check=False)
        if process.returncode == 0:
            return

    output_path.unlink(missing_ok=True)
    detail = process.stderr.strip() if process else "Unknown compiler error"
    if "SDK is not supported by the compiler" in detail:
        detail = (
            "The installed Swift compiler and macOS SDK do not match. "
            "Update Xcode Command Line Tools, then try again.\n\n" +
            detail.splitlines()[-1]
        )
    raise NativeBuildError(detail)
