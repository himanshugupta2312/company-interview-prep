# Company Interview Prep

Fetch the latest company-wise LeetCode problems and system-design notes from:

- [leetcode-company-wise-problems](https://github.com/liquidslr/leetcode-company-wise-problems)
- [system-design-notes](https://github.com/liquidslr/system-design-notes)

## Fetch or update the sources

Install Git, then run from this repository:

```powershell
python scripts\fetch_sources.py
```

The script shallow-clones each source on the first run and fast-forwards it on
later runs. The source trees are saved in `sources\` and are intentionally
ignored by Git; this repository contains the fetcher and source references,
not copies of their content.

The fetched files remain subject to their respective upstream authors'
copyright, license, and usage terms. Check each source repository for current
terms before using or redistributing its material.

## Layout

- `scripts\fetch_sources.py` - fetches or updates both source repositories.
- `sources\leetcode-company-wise-problems\` - created by the fetch command.
- `sources\system-design-notes\` - created by the fetch command.
