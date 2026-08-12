"""Secure credential persistence for external model providers."""

import platform
import shlex
import shutil
import subprocess
from typing import Optional


class CredentialStoreError(RuntimeError):
    """Raised when the operating-system credential store is unavailable."""


class KeychainCredentialStore:
    """Store one provider secret in the macOS Keychain."""

    SERVICE = ""
    ACCOUNT = "api-key"
    DISPLAY_NAME = "API key"

    def __init__(self, system_name: Optional[str] = None,
                 security_command: Optional[str] = None):
        self.system_name = system_name or platform.system()
        self.security_command = security_command or shutil.which("security")

    def get(self) -> Optional[str]:
        command = self._command()
        process = subprocess.run([
            command, "find-generic-password",
            "-a", self.ACCOUNT, "-s", self.SERVICE, "-w",
        ], capture_output=True, text=True, check=False)
        if process.returncode == 44:
            return None
        if process.returncode != 0:
            raise CredentialStoreError(
                process.stderr.strip() or "Unable to read the macOS Keychain.")
        value = process.stdout.rstrip("\r\n")
        return value or None

    def set(self, api_key: str) -> None:
        api_key = api_key.strip()
        if not api_key:
            raise CredentialStoreError(f"The {self.DISPLAY_NAME} cannot be empty.")
        command = self._command()
        # Interactive mode reads the complete command from stdin, so the key
        # never appears in argv or project configuration.
        interactive_command = " ".join([
            "add-generic-password", "-U",
            "-a", shlex.quote(self.ACCOUNT),
            "-s", shlex.quote(self.SERVICE),
            "-w", shlex.quote(api_key),
        ]) + "\n"
        process = subprocess.run([
            command, "-i",
        ], input=interactive_command, capture_output=True, text=True,
            check=False)
        if process.returncode != 0:
            raise CredentialStoreError(
                process.stderr.strip() or "Unable to save to the macOS Keychain.")

    def delete(self) -> bool:
        command = self._command()
        process = subprocess.run([
            command, "delete-generic-password",
            "-a", self.ACCOUNT, "-s", self.SERVICE,
        ], capture_output=True, text=True, check=False)
        if process.returncode == 44:
            return False
        if process.returncode != 0:
            raise CredentialStoreError(
                process.stderr.strip() or
                "Unable to remove the key from the macOS Keychain.")
        return True

    def _command(self) -> str:
        if self.system_name != "Darwin" or not self.security_command:
            raise CredentialStoreError(
                f"Saving the {self.DISPLAY_NAME} currently requires macOS "
                "Keychain.")
        return self.security_command


class DeepSeekCredentialStore(KeychainCredentialStore):
    SERVICE = "com.z21locomotivemanager.deepseek"
    DISPLAY_NAME = "DeepSeek API key"
