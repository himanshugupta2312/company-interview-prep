import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import app


class QuestionDataTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary_directory.cleanup)
        self.root = Path(self.temporary_directory.name)
        self.sources = self.root / "sources"
        leetcode = self.sources / app.SOURCES[0].name / "Example Co"
        leetcode.mkdir(parents=True)
        for filename in ("1. Thirty Days.csv", "5. All.csv"):
            with (leetcode / filename).open("w", encoding="utf-8", newline="") as file:
                writer = csv.DictWriter(
                    file,
                    fieldnames=[
                        "Difficulty",
                        "Title",
                        "Frequency",
                        "Acceptance Rate",
                        "Link",
                        "Topics",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "Difficulty": "MEDIUM",
                        "Title": "Example Problem",
                        "Frequency": "50",
                        "Acceptance Rate": "0.25",
                        "Link": "https://leetcode.com/problems/example-problem",
                        "Topics": "Array, Hash Table",
                    }
                )
        design = self.sources / app.SOURCES[1].name / "01. URL Shortener"
        design.mkdir(parents=True)
        (design / "Readme.md").write_text(
            "# Design a URL Shortener\n\nNotes for the design question.\n",
            encoding="utf-8",
        )
        self.marker = self.sources / ".last-refresh.json"
        self.marker.write_text(
            '{"refreshed_at":"2026-10-24T12:00:00+00:00"}',
            encoding="utf-8",
        )
        app._load_question_data.cache_clear()
        self.addCleanup(app._load_question_data.cache_clear)

    def test_company_problem_csv_files_are_aggregated_without_duplicates(self) -> None:
        with patch.object(app, "SOURCES_DIRECTORY", self.sources):
            questions, companies = app._read_leetcode_questions()

        self.assertEqual(companies, ["Example Co"])
        self.assertEqual(len(questions), 1)
        self.assertEqual(questions[0]["time_windows"], ["Last 30 days", "All time"])
        self.assertEqual(questions[0]["topics"], ["Array", "Hash Table"])

    def test_question_search_combines_sources_and_keeps_shared_questions(self) -> None:
        with (
            patch.object(app, "SOURCES_DIRECTORY", self.sources),
            patch.object(app, "REFRESH_MARKER", self.marker),
        ):
            data = app.get_questions({"company": "example co", "position": "Backend Engineer"})

        self.assertEqual(data["selected_company"], "Example Co")
        self.assertEqual(data["selected_position"], "Backend Engineer")
        self.assertEqual(data["counts"]["leetcode"], 1)
        self.assertEqual(data["counts"]["system-design"], 1)
        self.assertEqual(data["counts"]["behavioral"], len(app.BEHAVIORAL_QUESTIONS))
        self.assertTrue(data["position_notice"])

    def test_time_and_difficulty_filters_apply_to_leetcode_questions(self) -> None:
        with (
            patch.object(app, "SOURCES_DIRECTORY", self.sources),
            patch.object(app, "REFRESH_MARKER", self.marker),
        ):
            recent = app.get_questions(
                {
                    "company": "Example Co",
                    "type": "leetcode",
                    "difficulty": "medium",
                    "period": "last 30 days",
                }
            )
            old = app.get_questions(
                {
                    "company": "Example Co",
                    "type": "leetcode",
                    "difficulty": "hard",
                }
            )

        self.assertEqual(recent["counts"]["leetcode"], 1)
        self.assertEqual(recent["counts"]["system-design"], 0)
        self.assertEqual(old["results"], [])

    def test_generic_question_search_and_type_filter(self) -> None:
        with (
            patch.object(app, "SOURCES_DIRECTORY", self.sources),
            patch.object(app, "REFRESH_MARKER", self.marker),
        ):
            data = app.get_questions({"type": "system-design", "search": "url"})

        self.assertEqual(data["counts"]["system-design"], 1)
        self.assertEqual(data["counts"]["behavioral"], 0)
        self.assertEqual(data["results"][0]["title"], "Design a URL Shortener")

    def test_results_are_paginated_without_losing_total_counts(self) -> None:
        with (
            patch.object(app, "SOURCES_DIRECTORY", self.sources),
            patch.object(app, "REFRESH_MARKER", self.marker),
        ):
            first_page = app.get_questions(
                {"company": "Example Co", "offset": "0", "limit": "5"}
            )
            second_page = app.get_questions(
                {"company": "Example Co", "offset": "5", "limit": "5"}
            )

        self.assertEqual(first_page["total"], 14)
        self.assertEqual(first_page["counts"]["leetcode"], 1)
        self.assertEqual(len(first_page["results"]), 5)
        self.assertTrue(first_page["has_more"])
        self.assertNotEqual(first_page["results"], second_page["results"])

    def test_invalid_pagination_is_reported(self) -> None:
        with patch.object(app, "SOURCES_DIRECTORY", self.sources):
            with self.assertRaisesRegex(ValueError, "integers"):
                app.get_questions({"offset": "first"})


if __name__ == "__main__":
    unittest.main()
