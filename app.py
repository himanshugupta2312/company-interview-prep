"""Local web app for browsing company interview-preparation questions."""

from __future__ import annotations

import csv
import json
import re
import shutil
import subprocess
import sys
import threading
from datetime import datetime, timezone
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, urlparse

from flask import Flask, jsonify, request, send_from_directory

from scripts.fetch_sources import REPOSITORY_ROOT, SOURCES, SourceUpdateError, fetch_source


app = Flask(__name__)
WEB_DIRECTORY = REPOSITORY_ROOT / "web"
SOURCES_DIRECTORY = REPOSITORY_ROOT / "sources"
REFRESH_MARKER = SOURCES_DIRECTORY / ".last-refresh.json"
AUTO_REFRESH_INTERVAL_SECONDS = 24 * 60 * 60
SOURCE_LOCK = threading.RLock()
LEETCODE_REPOSITORY_URL = "https://github.com/liquidslr/leetcode-company-wise-problems"
SYSTEM_DESIGN_REPOSITORY_URL = "https://github.com/liquidslr/system-design-notes"
LEETCODE_WINDOW_LABELS = {
    "thirty days": "Last 30 days",
    "three months": "Last 3 months",
    "six months": "Last 6 months",
    "more than six months": "More than 6 months",
    "all": "All time",
}
POSITION_KEYWORDS = {
    "frontend": (
        "frontend",
        "front-end",
        "front end",
        "javascript",
        "typescript",
        "html",
        "css",
        "browser",
        "react",
        "vue",
        "angular",
        "web",
        "user interface",
    ),
    "backend": (
        "backend",
        "back-end",
        "back end",
        "server",
        "api",
        "database",
        "sql",
        "cache",
        "queue",
        "distributed",
        "network",
        "storage",
        "key-value",
        "url",
        "crawler",
        "notification",
        "chat",
        "feed",
        "search",
        "rate limiter",
        "consistent hashing",
        "scaling",
    ),
    "mobile": (
        "mobile",
        "ios",
        "android",
        "array",
        "string",
        "hash table",
        "graph",
        "tree",
    ),
    "data": (
        "data",
        "machine learning",
        "statistics",
        "sql",
        "database",
        "pipeline",
        "stream",
        "graph",
        "array",
        "search",
    ),
    "platform": (
        "platform",
        "infrastructure",
        "devops",
        "reliability",
        "monitoring",
        "metrics",
        "alerting",
        "scaling",
        "distributed",
        "storage",
        "queue",
        "network",
        "rate limiter",
    ),
    "security": (
        "security",
        "authentication",
        "authorization",
        "encryption",
        "access control",
        "cryptography",
    ),
}
GENERAL_POSITION_WORDS = {
    "engineer",
    "engineering",
    "developer",
    "software",
    "senior",
    "junior",
    "staff",
    "principal",
    "lead",
    "sde",
    "swe",
}

BEHAVIORAL_QUESTIONS = (
    {
        "title": "Tell me about a challenging problem you solved.",
        "topic": "Problem solving",
    },
    {
        "title": "Describe a time you disagreed with a teammate. How did you handle it?",
        "topic": "Collaboration",
    },
    {
        "title": "Tell me about a mistake you made and what you learned from it.",
        "topic": "Learning",
    },
    {
        "title": "Give an example of a time you had to learn something quickly.",
        "topic": "Adaptability",
    },
    {
        "title": "Describe a time you received difficult feedback. What did you do?",
        "topic": "Growth",
    },
    {
        "title": "Tell me about a time you took ownership beyond your assigned work.",
        "topic": "Ownership",
    },
    {
        "title": "Describe a project that did not go as planned. What would you change?",
        "topic": "Reflection",
    },
    {
        "title": "Tell me about a time you had to prioritize competing deadlines.",
        "topic": "Prioritization",
    },
    {
        "title": "Give an example of how you helped a teammate succeed.",
        "topic": "Teamwork",
    },
    {
        "title": "Describe a decision you made with incomplete information.",
        "topic": "Decision making",
    },
    {
        "title": "Tell me about a time you improved a process or made work more effective.",
        "topic": "Initiative",
    },
    {
        "title": "Describe a time you influenced a decision without formal authority.",
        "topic": "Influence",
    },
)


def _github_file_url(repository_url: str, relative_path: Path) -> str:
    return f"{repository_url}/blob/main/{quote(relative_path.as_posix(), safe='/')}"


def _read_leetcode_questions() -> tuple[list[dict[str, object]], list[str]]:
    root = SOURCES_DIRECTORY / SOURCES[0].name
    if not root.is_dir():
        raise SourceUpdateError(f"LeetCode source is missing: {root}")

    by_question: dict[tuple[str, str], dict[str, object]] = {}
    companies: list[str] = []
    for company_directory in sorted(
        path for path in root.iterdir() if path.is_dir() and not path.name.startswith(".")
    ):
        company = company_directory.name
        companies.append(company)
        for csv_path in sorted(company_directory.rglob("*.csv")):
            filename = re.sub(r"^\d+\.\s*", "", csv_path.stem).strip().casefold()
            window = LEETCODE_WINDOW_LABELS.get(filename, "Other")
            relative_path = csv_path.relative_to(root)
            try:
                with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
                    for row in csv.DictReader(file):
                        title = (row.get("Title") or "").strip()
                        link = (row.get("Link") or "").strip()
                        if not title:
                            continue
                        key = (company.casefold(), link.casefold() or title.casefold())
                        question = by_question.get(key)
                        if question is None:
                            question = {
                                "id": f"leetcode:{company.casefold()}:{len(by_question)}",
                                "type": "leetcode",
                                "title": title,
                                "company": company,
                                "position": None,
                                "difficulty": (row.get("Difficulty") or "").strip().title(),
                                "topics": [
                                    topic.strip()
                                    for topic in (row.get("Topics") or "").split(",")
                                    if topic.strip()
                                ],
                                "frequency": (row.get("Frequency") or "").strip(),
                                "acceptance_rate": (row.get("Acceptance Rate") or "").strip(),
                                "link": link,
                                "source_url": _github_file_url(
                                    LEETCODE_REPOSITORY_URL,
                                    relative_path,
                                ),
                                "time_windows": [],
                                "search_text": "",
                            }
                            by_question[key] = question
                        if window not in question["time_windows"]:
                            question["time_windows"].append(window)
                        if window == "All time":
                            question["frequency"] = (row.get("Frequency") or "").strip()
                            question["acceptance_rate"] = (
                                row.get("Acceptance Rate") or ""
                            ).strip()
                            question["source_url"] = _github_file_url(
                                LEETCODE_REPOSITORY_URL,
                                relative_path,
                            )
            except (OSError, UnicodeError, csv.Error) as error:
                raise SourceUpdateError(f"Could not read LeetCode data file {csv_path}: {error}") from error

    questions = list(by_question.values())
    for question in questions:
        question["search_text"] = " ".join(
            [
                str(question["title"]),
                str(question["company"]),
                *question["topics"],
            ]
        ).casefold()
    return questions, companies


def _read_system_design_questions() -> list[dict[str, object]]:
    root = SOURCES_DIRECTORY / SOURCES[1].name
    if not root.is_dir():
        raise SourceUpdateError(f"System-design source is missing: {root}")

    questions: list[dict[str, object]] = []
    for markdown_path in sorted(root.glob("*/Readme.md")):
        relative_path = markdown_path.relative_to(root)
        try:
            content = markdown_path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            raise SourceUpdateError(f"Could not read system-design note {markdown_path}: {error}") from error
        heading = re.search(r"^#\s+(.+?)\s*#*\s*$", content, re.MULTILINE)
        title = heading.group(1).strip() if heading else relative_path.parent.name
        questions.append(
            {
                "id": f"system-design:{relative_path.parent.name.casefold()}",
                "type": "system-design",
                "title": title,
                "company": None,
                "position": None,
                "difficulty": "",
                "topics": [relative_path.parent.name],
                "frequency": "",
                "acceptance_rate": "",
                "link": _github_file_url(SYSTEM_DESIGN_REPOSITORY_URL, relative_path),
                "source_url": _github_file_url(SYSTEM_DESIGN_REPOSITORY_URL, relative_path),
                "time_windows": [],
                "search_text": f"{title} {relative_path.parent.name}".casefold(),
            }
        )
    return questions


def _position_keywords(position: str) -> tuple[str, ...]:
    normalized = re.sub(r"[^a-z0-9]+", " ", position.casefold()).strip()
    if not normalized:
        return ()
    role_patterns = (
        (r"\b(front[ -]?end|ui|web)\b", "frontend"),
        (r"\b(back[ -]?end|server)\b", "backend"),
        (r"\b(mobile|ios|android)\b", "mobile"),
        (r"\b(data|machine learning|ml|ai)\b", "data"),
        (r"\b(platform|devops|sre|infrastructure|reliability)\b", "platform"),
        (r"\b(security|cybersecurity|appsec)\b", "security"),
    )
    for pattern, category in role_patterns:
        if re.search(pattern, normalized):
            return POSITION_KEYWORDS[category]

    words = tuple(
        word
        for word in normalized.split()
        if word not in GENERAL_POSITION_WORDS and len(word) > 1
    )
    return words


@lru_cache(maxsize=1)
def _load_question_data() -> tuple[list[dict[str, object]], list[str], list[dict[str, object]]]:
    leetcode, companies = _read_leetcode_questions()
    system_design = _read_system_design_questions()
    behavioral = [
        {
            "id": f"behavioral:{index}",
            "type": "behavioral",
            "title": question["title"],
            "company": None,
            "position": None,
            "difficulty": "",
            "topics": [question["topic"]],
            "frequency": "",
            "acceptance_rate": "",
            "link": "",
            "source_url": "",
            "time_windows": [],
            "search_text": f"{question['title']} {question['topic']}".casefold(),
        }
        for index, question in enumerate(BEHAVIORAL_QUESTIONS, start=1)
    ]
    return leetcode, companies, system_design + behavioral


def get_questions(filters: dict[str, str]) -> dict[str, object]:
    with SOURCE_LOCK:
        return _get_questions(filters)


def _get_questions(filters: dict[str, str]) -> dict[str, object]:
    leetcode, companies, general_questions = _load_question_data()
    requested_company = filters.get("company", "").strip()
    selected_company = next(
        (company for company in companies if company.casefold() == requested_company.casefold()),
        None,
    )
    selected_type = filters.get("type", "all").casefold()
    selected_difficulty = filters.get("difficulty", "").casefold()
    selected_window = filters.get("period", "").casefold()
    search = filters.get("search", "").strip().casefold()
    position_keywords = _position_keywords(filters.get("position", ""))
    try:
        offset = max(0, int(filters.get("offset", "0")))
        limit = min(100, max(1, int(filters.get("limit", "50"))))
    except ValueError as error:
        raise ValueError("Question offset and limit must be integers.") from error

    results: list[dict[str, object]] = []
    if selected_type in ("all", "leetcode") and selected_company:
        for question in leetcode:
            if question["company"] != selected_company:
                continue
            if selected_difficulty and str(question["difficulty"]).casefold() != selected_difficulty:
                continue
            if selected_window:
                windows = question["time_windows"]
                if selected_window == "all time":
                    if "All time" not in windows:
                        continue
                elif selected_window not in [window.casefold() for window in windows]:
                    continue
            if search and search not in str(question["search_text"]):
                continue
            if position_keywords and not any(
                keyword in str(question["search_text"])
                for keyword in position_keywords
            ):
                continue
            results.append(question)

    if selected_type in ("all", "system-design", "behavioral"):
        for question in general_questions:
            if selected_type != "all" and question["type"] != selected_type:
                continue
            if search and search not in str(question["search_text"]):
                continue
            if (
                question["type"] == "system-design"
                and position_keywords
                and not any(
                    keyword in str(question["search_text"])
                    for keyword in position_keywords
                )
            ):
                continue
            results.append(question)

    results.sort(key=lambda item: (str(item["type"]), str(item["title"]).casefold()))
    try:
        refreshed_at = json.loads(REFRESH_MARKER.read_text(encoding="utf-8")).get("refreshed_at")
    except FileNotFoundError:
        refreshed_at = None
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise SourceUpdateError(f"Could not read source refresh status: {error}") from error
    counts = {
        kind: sum(question["type"] == kind for question in results)
        for kind in ("leetcode", "system-design", "behavioral")
    }
    total = len(results)
    return {
        "companies": companies,
        "selected_company": selected_company,
        "selected_position": filters.get("position", "").strip(),
        "results": results[offset : offset + limit],
        "counts": counts,
        "total": total,
        "has_more": offset + limit < total,
        "refreshed_at": refreshed_at,
        "position_notice": (
            "Position matches are inferred from role keywords in question titles and topics, "
            "not verified job-title history. General behavioral prompts remain included."
            if position_keywords
            else "The upstream lists do not tag questions by job title. Broad software-engineering "
            "roles use the full company list; specialized positions match titles and topics when "
            "keywords are available. Behavioral prompts remain general."
        ),
    }


@app.get("/")
def index():
    return send_from_directory(WEB_DIRECTORY, "index.html")


@app.get("/app.js")
@app.get("/styles.css")
def static_asset():
    return send_from_directory(WEB_DIRECTORY, request.path.lstrip("/"))


@app.get("/api/questions")
def questions_api():
    filters = request.args.to_dict()
    try:
        return jsonify(get_questions(filters))
    except ValueError as error:
        return jsonify({"error": str(error)}), 400
    except (SourceUpdateError, OSError) as error:
        return jsonify({"error": str(error)}), 500


def refresh_sources() -> str:
    if shutil.which("git") is None:
        raise SourceUpdateError("Git is required but was not found on PATH.")

    with SOURCE_LOCK:
        for source in SOURCES:
            fetch_source(source)
        refreshed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            REFRESH_MARKER.write_text(
                json.dumps({"refreshed_at": refreshed_at}, indent=2) + "\n",
                encoding="utf-8",
            )
        except OSError as error:
            raise SourceUpdateError(f"Could not save source refresh status: {error}") from error
        _load_question_data.cache_clear()
        return refreshed_at


@app.post("/api/refresh")
def refresh_api():
    try:
        return jsonify({"refreshed_at": refresh_sources()})
    except (SourceUpdateError, OSError, subprocess.CalledProcessError) as error:
        detail = str(error)
        if isinstance(error, subprocess.CalledProcessError):
            detail = f"Git update failed (exit code {error.returncode}): {error.cmd}"
        return jsonify({"error": detail}), 500


def auto_refresh_sources(
    stop_event: threading.Event,
    interval_seconds: int = AUTO_REFRESH_INTERVAL_SECONDS,
) -> None:
    while not stop_event.wait(interval_seconds):
        try:
            refreshed_at = refresh_sources()
        except (SourceUpdateError, OSError, subprocess.CalledProcessError) as error:
            print(f"Automatic source refresh failed: {error}", file=sys.stderr)
        else:
            print(f"Automatic source refresh completed at {refreshed_at}")


class InterviewPrepHandler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, payload: dict[str, object]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, relative_path: str) -> None:
        path = (WEB_DIRECTORY / relative_path).resolve()
        if WEB_DIRECTORY.resolve() not in path.parents or not path.is_file():
            self.send_error(404)
            return
        content_type = {
            ".css": "text/css; charset=utf-8",
            ".html": "text/html; charset=utf-8",
            ".js": "text/javascript; charset=utf-8",
        }.get(path.suffix, "application/octet-stream")
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed_url = urlparse(self.path)
        if parsed_url.path == "/api/questions":
            query = parse_qs(parsed_url.query)
            filters = {key: values[0] for key, values in query.items() if values}
            try:
                self._send_json(200, get_questions(filters))
            except ValueError as error:
                self._send_json(400, {"error": str(error)})
            except (SourceUpdateError, OSError) as error:
                self._send_json(500, {"error": str(error)})
            return
        if parsed_url.path == "/":
            self._send_file("index.html")
            return
        if parsed_url.path in ("/app.js", "/styles.css"):
            self._send_file(parsed_url.path.lstrip("/"))
            return
        self.send_error(404)

    def do_POST(self) -> None:
        if urlparse(self.path).path != "/api/refresh":
            self.send_error(404)
            return
        try:
            refreshed_at = refresh_sources()
            self._send_json(200, {"refreshed_at": refreshed_at})
        except (SourceUpdateError, OSError, subprocess.CalledProcessError) as error:
            detail = str(error)
            if isinstance(error, subprocess.CalledProcessError):
                detail = f"Git update failed (exit code {error.returncode}): {error.cmd}"
            self._send_json(500, {"error": detail})

    def log_message(self, format: str, *args: object) -> None:
        print(f"[{self.log_date_time_string()}] {format % args}")


def main() -> None:
    try:
        refreshed_at = refresh_sources()
    except (SourceUpdateError, OSError, subprocess.CalledProcessError) as error:
        print(f"Could not fetch interview-prep sources: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    server = ThreadingHTTPServer(("127.0.0.1", 8000), InterviewPrepHandler)
    stop_refresh = threading.Event()
    refresh_thread = threading.Thread(
        target=auto_refresh_sources,
        args=(stop_refresh,),
        name="interview-prep-source-refresh",
        daemon=True,
    )
    refresh_thread.start()
    print(f"Sources checked at {refreshed_at}")
    print("Sources will be checked automatically every 24 hours.")
    print("Open http://127.0.0.1:8000 in your browser. Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping interview prep.")
    finally:
        stop_refresh.set()
        refresh_thread.join(timeout=1)
        server.server_close()


if __name__ == "__main__":
    main()
