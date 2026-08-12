"""Small platform boundary for optional macOS application services."""

from pathlib import Path
import platform
import subprocess


class PlatformFeatureUnavailable(RuntimeError):
    """Raised when an operating-system integration is unavailable."""


class DesktopPlatformAdapter:
    def activate_application(self) -> None:
        """Activate the application when supported by the host platform."""

    def share_file(self, path: Path) -> bool:
        """Share a file and return whether a native share sheet was started."""
        raise PlatformFeatureUnavailable(
            "Native file sharing is only available on macOS.")

    def reveal_file(self, path: Path) -> None:
        raise PlatformFeatureUnavailable(
            "Revealing a file is not supported on this platform.")


class MacOSPlatformAdapter(DesktopPlatformAdapter):
    def __init__(self):
        try:
            from AppKit import NSApplication, NSSharingService, NSURL
            from Foundation import NSArray
        except ImportError as error:
            raise PlatformFeatureUnavailable(
                "PyObjC is required for macOS sharing. Install "
                "pyobjc-framework-Cocoa.") from error
        self._application = NSApplication
        self._sharing_service = NSSharingService
        self._url = NSURL
        self._array = NSArray

    def activate_application(self) -> None:
        self._application.sharedApplication().activateIgnoringOtherApps_(True)

    def share_file(self, path: Path) -> bool:
        file_url = self._url.fileURLWithPath_(str(Path(path).resolve()))
        items = self._array.arrayWithObject_(file_url)
        service = self._sharing_service.sharingServiceNamed_(
            "com.apple.share.AirDrop")
        if service is None:
            for candidate in self._sharing_service.sharingServicesForItems_(items):
                if "airdrop" in candidate.title().lower():
                    service = candidate
                    break
        if service is None or not service.canPerformWithItems_(items):
            return False
        service.performWithItems_(items)
        return True

    def reveal_file(self, path: Path) -> None:
        subprocess.run(["open", "-R", str(Path(path))], check=True)


def get_platform_adapter(system_name=None) -> DesktopPlatformAdapter:
    if (system_name or platform.system()) == "Darwin":
        return MacOSPlatformAdapter()
    return DesktopPlatformAdapter()
