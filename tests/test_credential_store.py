import subprocess
import unittest
from unittest import mock

from src.credential_store import DeepSeekCredentialStore


class DeepSeekCredentialStoreTests(unittest.TestCase):
    def setUp(self):
        self.store = DeepSeekCredentialStore(
            system_name="Darwin", security_command="/usr/bin/security")

    @mock.patch("src.credential_store.subprocess.run")
    def test_set_sends_key_through_stdin_not_argv(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="", stderr="")
        self.store.set("secret-api-key")

        command = run.call_args.args[0]
        self.assertNotIn("secret-api-key", command)
        self.assertEqual(command, ["/usr/bin/security", "-i"])
        self.assertIn("-w secret-api-key",
                      run.call_args.kwargs["input"])

    @mock.patch("src.credential_store.subprocess.run")
    def test_get_returns_saved_key(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=0, stdout="secret-api-key\n", stderr="")
        self.assertEqual(self.store.get(), "secret-api-key")

    @mock.patch("src.credential_store.subprocess.run")
    def test_missing_key_returns_none(self, run):
        run.return_value = subprocess.CompletedProcess(
            args=[], returncode=44, stdout="", stderr="not found")
        self.assertIsNone(self.store.get())
