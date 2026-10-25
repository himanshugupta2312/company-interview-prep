import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import scripts.fetch_sources as fetch_sources


class FetchSourceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.sources_directory = Path(self.temporary_directory.name)
        self.source = fetch_sources.Source(
            name="sample",
            url="https://github.com/example/sample.git",
        )

    def test_clones_source_when_destination_is_missing(self) -> None:
        with patch.object(fetch_sources, "SOURCES_DIRECTORY", self.sources_directory):
            with patch.object(fetch_sources, "run_git") as run_git:
                self.assertTrue(fetch_sources.fetch_source(self.source))

        run_git.assert_called_once_with(
            "clone",
            "--depth",
            "1",
            "--",
            self.source.url,
            str(self.sources_directory / self.source.name),
        )

    def test_pulls_source_when_destination_is_existing_clone(self) -> None:
        destination = self.sources_directory / self.source.name
        (destination / ".git").mkdir(parents=True)
        remote = SimpleNamespace(stdout=f"{self.source.url}\n")

        with patch.object(fetch_sources, "SOURCES_DIRECTORY", self.sources_directory):
            with patch.object(fetch_sources, "run_git", side_effect=[remote, None]) as run_git:
                self.assertFalse(fetch_sources.fetch_source(self.source))

        self.assertEqual(run_git.call_count, 2)
        run_git.assert_any_call(
            "remote",
            "get-url",
            "origin",
            cwd=destination,
            capture_output=True,
        )
        run_git.assert_any_call("pull", "--ff-only", cwd=destination)

    def test_refuses_existing_non_clone_directory(self) -> None:
        (self.sources_directory / self.source.name).mkdir()

        with patch.object(fetch_sources, "SOURCES_DIRECTORY", self.sources_directory):
            with self.assertRaises(fetch_sources.SourceUpdateError):
                fetch_sources.fetch_source(self.source)

    def test_refuses_unexpected_origin(self) -> None:
        destination = self.sources_directory / self.source.name
        (destination / ".git").mkdir(parents=True)

        with patch.object(fetch_sources, "SOURCES_DIRECTORY", self.sources_directory):
            with patch.object(
                fetch_sources,
                "run_git",
                return_value=SimpleNamespace(stdout="https://github.com/other/repo.git\n"),
            ):
                with self.assertRaises(fetch_sources.SourceUpdateError):
                    fetch_sources.fetch_source(self.source)


if __name__ == "__main__":
    unittest.main()
