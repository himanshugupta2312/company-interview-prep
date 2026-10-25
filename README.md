# Company Interview Prep

A small local web app for browsing company-wise coding problems, system-design
practice, and general behavioral prompts.

## Run the app

Install Python 3.10+ and Git, then run from this repository:

```powershell
python app.py
```

On startup, the app checks out or fast-forwards both upstream repositories, then
serves the UI at <http://127.0.0.1:8000>. Keep the terminal open while using it;
press `Ctrl+C` to stop. Use **Refresh sources** in the UI to check for new
upstream questions without restarting the app. The app also checks for changes
automatically every 24 hours while it is running. If an update fails, the app
shows or logs the error instead of presenting it as a successful refresh.

The repositories are checked out into `sources\` and remain ignored by Git.
The UI reads the current checked-out data, so refreshed questions appear on the
next search or page reload. The LeetCode source includes company coding lists; the
system-design source supplies general design prompts, not verified
company-specific questions.

## Filters and data limitations

- Search by company, question text, topic, LeetCode difficulty, and the
  upstream time-window lists. Leave the company blank to browse general
  system-design and behavioral practice.
- The upstream company problem lists do not identify the job position for
  each question. The position field uses keyword-based relevance matching
  against question titles and topics for specialized roles; broad software
  engineering titles keep the full company list. This is an estimate, not
  verified role-specific interview history. General behavioral prompts remain
  included for every position.
- The upstream sources do not provide a behavioral interview dataset. The app
  includes a small set of general, original practice prompts, not
  company-specific questions. A public behavioral-question repository is
  linked in the UI as a reference, but its content is not copied into this
  project because a reuse license was not found.
- Upstream coding questions may be dated or incomplete. “Refresh sources”
  checks for changes in those repositories; it cannot guarantee that any
  interview report is exhaustive or current.

## Refresh sources from the command line

```powershell
python scripts\fetch_sources.py
```

## Run tests

```powershell
python -m unittest discover -s tests -v
```

## Layout

- `app.py` - local web server, data parsing, filtering, and refresh endpoint.
- `web\` - responsive browser UI.
- `scripts\fetch_sources.py` - shallow-clones or fast-forwards upstream data.
- `tests\` - source-fetcher and question filtering tests.
- `sources\` - ignored local upstream checkouts, created on first run.

Fetched files remain subject to their respective upstream authors' copyright,
license, and usage terms. Review each source repository's current terms before
redistributing fetched material.

## Upstream sources

- [liquidslr/leetcode-company-wise-problems](https://github.com/liquidslr/leetcode-company-wise-problems)
- [liquidslr/system-design-notes](https://github.com/liquidslr/system-design-notes)
- [gregorojstersek/behavioral-interview-list-of-questions](https://github.com/gregorojstersek/behavioral-interview-list-of-questions) - reference only; not imported.
