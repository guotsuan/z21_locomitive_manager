"""Bridge between the Python GUI and the native Continuity Camera helper."""

from dataclasses import dataclass
from enum import Enum
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Optional


class CaptureMode(str, Enum):
    SCAN = "scan"
    PHOTO = "photo"


@dataclass(frozen=True)
class CaptureResult:
    path: Path
    mode: CaptureMode


class ContinuityCameraError(RuntimeError):
    """Raised when the native helper cannot build or capture a document."""


class ContinuityCameraService:
    """Build and execute the isolated Swift/AppKit camera helper."""

    def __init__(self, source_path: Optional[Path] = None,
                 cache_directory: Optional[Path] = None,
                 info_plist_path: Optional[Path] = None):
        self.source_path = source_path or (
            Path(__file__).resolve().parent / "native" /
            "continuity_camera_helper.swift")
        self.info_plist_path = info_plist_path or (
            Path(__file__).resolve().parent / "native" /
            "ContinuityCameraHelper-Info.plist")
        self.cache_directory = cache_directory or (
            Path.home() / "Library" / "Caches" /
            "z21-locomotive-manager" / "continuity-camera")
        self.app_path = self.cache_directory / "Continuity Camera Helper.app"
        self.contents_path = self.app_path / "Contents"
        self.binary_path = (
            self.contents_path / "MacOS" / "continuity-camera-helper")
        self.built_info_plist_path = self.contents_path / "Info.plist"

    def capture(self, mode: CaptureMode) -> Optional[CaptureResult]:
        helper_app = self._ensure_helper()
        output_directory = Path(
            tempfile.mkdtemp(prefix="z21lm-continuity-camera-"))
        result_file = output_directory / "result.json"
        opener = shutil.which("open")
        if not opener:
            shutil.rmtree(output_directory, ignore_errors=True)
            raise ContinuityCameraError("The macOS 'open' command was not found.")
        process = subprocess.run(
            [opener, "-W", "-n", str(helper_app), "--args",
             "--mode", mode.value, "--output-dir", str(output_directory),
             "--result-file", str(result_file)],
            capture_output=True,
            text=True,
            check=False,
        )
        payload = self._read_result(result_file)
        if payload and payload.get("status") == "cancelled":
            shutil.rmtree(output_directory, ignore_errors=True)
            return None
        if process.returncode != 0 or not payload:
            detail = (payload or {}).get("message") or process.stderr.strip()
            shutil.rmtree(output_directory, ignore_errors=True)
            raise ContinuityCameraError(
                detail or "Continuity Camera helper exited without a result.")
        if payload.get("status") != "ok" or not payload.get("path"):
            shutil.rmtree(output_directory, ignore_errors=True)
            raise ContinuityCameraError(
                payload.get("message") or "Continuity Camera capture failed.")
        captured_path = Path(payload["path"])
        if not captured_path.is_file():
            shutil.rmtree(output_directory, ignore_errors=True)
            raise ContinuityCameraError(
                f"Continuity Camera returned a missing file: {captured_path}")
        return CaptureResult(path=captured_path, mode=mode)

    def _ensure_helper(self) -> Path:
        if not self.source_path.is_file():
            raise ContinuityCameraError(
                f"Continuity Camera helper source is missing: {self.source_path}")
        if not self.info_plist_path.is_file():
            raise ContinuityCameraError(
                "Continuity Camera helper Info.plist is missing: "
                f"{self.info_plist_path}")
        newest_source = max(self.source_path.stat().st_mtime,
                            self.info_plist_path.stat().st_mtime)
        if (self.binary_path.is_file() and
                self.built_info_plist_path.is_file() and
                min(self.binary_path.stat().st_mtime,
                    self.built_info_plist_path.stat().st_mtime) >=
                newest_source):
            return self.app_path

        compiler = shutil.which("swiftc")
        if not compiler:
            raise ContinuityCameraError(
                "Swift compiler not found. Install or update Xcode Command Line Tools.")
        self.cache_directory.mkdir(parents=True, exist_ok=True)
        module_cache = self.cache_directory / "module-cache"
        module_cache.mkdir(parents=True, exist_ok=True)
        executable_directory = self.binary_path.parent
        executable_directory.mkdir(parents=True, exist_ok=True)
        temporary_binary = executable_directory / "helper.building"
        command_tail = [
            str(self.source_path), "-framework", "AppKit",
            "-module-cache-path", str(module_cache),
            "-o", str(temporary_binary),
        ]
        commands = [[compiler, *command_tail]]
        # A partially updated Command Line Tools installation can expose a
        # compiler newer than its default SDK. Try installed real SDKs before
        # reporting that the native bridge is unavailable.
        sdk_root = Path("/Library/Developer/CommandLineTools/SDKs")
        if sdk_root.is_dir():
            for sdk_path in sorted(sdk_root.glob("MacOSX*.sdk")):
                if not sdk_path.is_symlink():
                    commands.append(
                        [compiler, "-sdk", str(sdk_path), *command_tail])

        process = None
        for command in commands:
            temporary_binary.unlink(missing_ok=True)
            process = subprocess.run(command,
                                     capture_output=True,
                                     text=True,
                                     check=False)
            if process.returncode == 0:
                break
        if process is None or process.returncode != 0:
            temporary_binary.unlink(missing_ok=True)
            detail = process.stderr.strip() if process else "Unknown compiler error"
            if "SDK is not supported by the compiler" in detail:
                detail = (
                    "The installed Swift compiler and macOS SDK do not match. "
                    "Update Xcode Command Line Tools, then try again.\n\n" +
                    detail.splitlines()[-1]
                )
            raise ContinuityCameraError(
                "Unable to build Continuity Camera helper.\n\n" + detail)
        os.replace(temporary_binary, self.binary_path)
        self.binary_path.chmod(0o755)
        temporary_plist = self.contents_path / "Info.plist.building"
        shutil.copyfile(self.info_plist_path, temporary_plist)
        os.replace(temporary_plist, self.built_info_plist_path)

        signer = shutil.which("codesign")
        if signer:
            signed = subprocess.run(
                [signer, "--force", "--deep", "--sign", "-",
                 str(self.app_path)],
                capture_output=True,
                text=True,
                check=False,
            )
            if signed.returncode != 0:
                raise ContinuityCameraError(
                    "Unable to sign Continuity Camera helper.\n\n" +
                    signed.stderr.strip())
        return self.app_path

    @staticmethod
    def _read_result(result_file: Path):
        try:
            value = json.loads(result_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        return value if isinstance(value, dict) else None
