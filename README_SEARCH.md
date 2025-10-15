## QATIS Search Automation (Google + Google Scholar via SerpAPI)

This script runs your predefined PMESII Infrastructure queries against Google Web and Google Scholar, filters by year, and writes per-query Markdown and JSON files you can paste into your notes.

### Setup

1. Create a Python virtualenv and install dependencies:
   - `python3 -m venv .venv && source .venv/bin/activate`
   - `pip install -r requirements.txt`
2. Configure your API key:
   - `cp .env.example .env`
   - Edit `.env` and set `SERPAPI_API_KEY` (requires a SerpAPI account).

### Queries

Edit `queries.yaml` to change or add queries. They are grouped by category (areas, structures, capabilities, organisations, people, events).

### Run

```bash
python run_searches.py \
  --queries queries.yaml \
  --output-dir search_results \
  --year-min 2024 \
  --year-max 2025 \
  --top-k 3 \
  --engines web scholar \
  --include-ru \
  --include-ro
```

Outputs are written to `search_results/<timestamp>/` as one Markdown and one JSON file per query (and per language variant if enabled), plus an `index.json`.

### Notes

- Google Web date range is enforced via `tbs` custom date range (2024–2025 by default).
- Scholar results use `as_ylo/as_yhi` year bounds.
- `--include-ru` and `--include-ro` add language bias (lr=lang_ru/lang_ro) queries in addition to English.
- Use `--top-k` to adjust how many results per engine you save for each query (default 3).

## Analysis (LLM-assisted)
## Alternative collectors (no Google API)

### DuckDuckGo Web (HTML)

```bash
python run_web_duckduckgo.py \
  --queries /Users/emilwl/Documents/QATIS/queries.yaml \
  --output-dir /Users/emilwl/Documents/QATIS/search_results_ddg \
  --top-k 5 \
  --pages 2 \
  --include-ru --include-ro
```

Writes per-query .md/.json like the SerpAPI script. Use the same `export_results_to_csv.py` to produce CSV.

### OpenAlex (Academic)

```bash
python run_academic_openalex.py \
  --queries /Users/emilwl/Documents/QATIS/queries.yaml \
  --output-dir /Users/emilwl/Documents/QATIS/search_results_openalex \
  --year-min 2024 --year-max 2025 \
  --top-k 10
```

Outputs are per-query .md/.json with title, venue, year, and link where available.

Requires `OPENAI_API_KEY` in `.env`.

1) Optional: de-duplicate and export CSV:

```bash
python export_results_to_csv.py --results-dir search_results/<timestamp> --output results_deduped.csv --dedupe
```

2) Analyze and export scored CSVs, PMESII markdown, and BibTeX:

```bash
python analyze_results.py \
  --results-dir search_results/<timestamp> \
  --input results_deduped.csv \
  --model gpt-4o-mini \
  --batch-size 20
```

Flags:
- `--no-fetch`: skip downloading article text; rely on title/snippet only.
- `--limit N`: only analyze first N rows.
- `--no-cache`: ignore `analysis_cache.jsonl` when re-running.

## Social Media Searches (X, YouTube, optional Telegram)

Use open-source scrapers (no paid APIs) via `run_social_searches.py` and `queries_social.yaml`.

### Setup
- Ensure requirements are installed: `pip install -r requirements.txt` (includes snscrape, yt-dlp)

### Run
```bash
python run_social_searches.py \
  --queries queries_social.yaml \
  --output-dir search_results_social \
  --year-min 2024 \
  --year-max 2025 \
  --top-k 20 \
  --platforms x youtube
```

Outputs are written to `search_results_social/<timestamp>/` (per-query `.md` and `.json` + `index.json`).

### Export CSV and merge
```bash
python export_results_to_csv.py \
  --results-dir search_results_social/<timestamp> \
  --output social_results.csv \
  --dedupe

python merge_csv.py \
  --input-a search_results/<timestamp>/results_deduped.csv \
  --input-b search_results_social/<timestamp>/social_results.csv \
  --output search_results/merged_results.csv \
  --dedupe-on link \
  --prefer first
```

### Optional: Telegram
- Requires `telethon` and credentials; run with `--platforms telegram --telegram --tele-api-id <id> --tele-api-hash <hash>`
- Configure channels/keywords in `queries_social.yaml`

### Broad and specific terms

`queries_social.yaml` supports both broad and specific sections per platform:

```yaml
x:
  broad:
    - 'Moldova infrastructure since:2024-01-01 until:2025-12-31 lang:en'
  specific:
    - 'Moldelectrica since:2024-01-01 until:2025-12-31'

youtube:
  broad:
    - 'Moldova infrastructure 2024'
  specific:
    - 'Moldelectrica 2024'

telegram:
  channels:
    - 't.me/moldovagov'
  keywords_broad:
    - 'infrastructure'
  keywords_specific:
    - 'Moldelectrica'
```

The runner will emit categories `x_broad`, `x_specific`, `youtube_broad`, `youtube_specific` (and placeholders for `telegram_broad`/`telegram_specific` if enabled).

