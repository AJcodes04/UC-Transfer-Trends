# assist.org Articulation Scraper

Scrapes course-level articulation agreements from assist.org using Playwright browser automation + XHR interception.

## Setup

```bash
# From project root, create/activate a venv (or use the existing backend venv)
cd scraper
python3 -m venv venv
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Install Playwright's Chromium browser (one-time, ~150MB download)
playwright install chromium
```

## Quick Start

```bash
# From project root (not scraper/), with venv activated:

# 1. First, run discovery to inspect assist.org's data format
python -m scraper.run discover --from SBCC --to UCB

# 2. Inspect the output in data/articulation/_discovery/
#    - xhr_*/body.json = intercepted API responses
#    - page.html = rendered DOM

# 3. Scrape one major for testing
python -m scraper.run scrape --from SBCC --to UCB --major "Computer Science" --debug

# 4. Scrape all majors for one UC
python -m scraper.run scrape --from SBCC --to UCB

# 5. Scrape all UCs
python -m scraper.run scrape --from SBCC --to ALL
```

## Commands

| Command | Description |
|---------|-------------|
| `discover` | Navigate to one agreement page, dump all XHR + DOM for inspection |
| `scrape` | Run the full scrape pipeline |
| `list-institutions` | Fetch all institution IDs from assist.org |
| `list-years` | Fetch available academic years |

## CLI Flags

| Flag | Default | Description |
|------|---------|-------------|
| `--from` | SBCC | Sending community college code |
| `--to` | ALL | Receiving UC code(s), space-separated, or ALL |
| `--year` | 2024-25 | Academic year |
| `--major` | (none) | Filter to majors containing this string |
| `--headful` | false | Show the browser window |
| `--debug` | false | Save screenshots and debug info |
| `-v` | false | Verbose/debug logging |

## Output

Articulation data is saved as JSON in `data/articulation/`:

```
data/articulation/
  sbcc/
    ucb/
      2024-25/
        computer_science.json
        ...
    ucla/
      2024-25/
        ...
  manifest.json   # Tracks scraping progress for resume
```

## Resume Support

The scraper saves progress after each agreement. If interrupted, re-run the same command — it skips already-completed agreements automatically.

## Adding New Colleges

1. Look up the institution ID: `python -m scraper.run list-institutions`
2. Add it to `CC_INSTITUTIONS` in `config.py`
3. Run: `python -m scraper.run scrape --from NEW_CODE --to ALL`
