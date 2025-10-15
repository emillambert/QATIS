## QATIS OSINT Workflow and Automation Guide

This guide covers end-to-end collection and triage for Moldova Infrastructure OSINT using Google, Google Scholar, social platforms, CSV aggregation, LLM-assisted analysis, PMESII outputs, and BibTeX export.

### 1) Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Create `.env` in the project root:

```bash
# SerpAPI (Google + Scholar)
SERPAPI_API_KEY=your_serpapi_key_here

# OpenAI (LLM analysis)
OPENAI_API_KEY=sk-...
```

Notes:
- Python 3.10+ recommended. On 3.14 you may see a pydantic warning; it’s benign.
- If you hit an OpenAI client error about `proxies`, pinning httpx is already handled in `requirements.txt`.

### 2) Define search queries

- Web/Scholar queries: `queries.yaml` (quoted scalars per line). Example:

```yaml
areas:
  - '"Moldova infrastructure overview" OR "critical infrastructure Moldova"'
structures:
  - 'Moldelectrica ownership OR restructuring'
```

- Optional general pack: `queries_general.yaml`
- Optional social pack: `queries_social.yaml`

### 3) Run Google + Scholar collection

```bash
python run_searches.py \
  --queries /Users/emilwl/Documents/QATIS/queries.yaml \
  --output-dir /Users/emilwl/Documents/QATIS/search_results \
  --year-min 2024 \
  --year-max 2025 \
  --top-k 3 \
  --engines web scholar \
  --include-ru \
  --include-ro
```

Outputs:
- Per-query `.md` and `.json` files under `search_results/<timestamp>/`
- `index.json` with pointers

### 4) Export all results to CSV

```bash
python export_results_to_csv.py \
  --results-dir /Users/emilwl/Documents/QATIS/search_results/<timestamp> \
  --output results.csv

# Deduplicate by link and union categories/queries/languages/engines
python export_results_to_csv.py \
  --results-dir /Users/emilwl/Documents/QATIS/search_results/<timestamp> \
  --output results_deduped.csv \
  --dedupe
```

Deduping rules:
- Same-link rows are merged.
- First non-empty title/source/date kept, longest snippet kept, smallest position kept.
- Adds `occurrences` column.

### 5) Run social collections (optional)

```bash
python run_social_searches.py \
  --queries /Users/emilwl/Documents/QATIS/queries_social.yaml \
  --output-dir /Users/emilwl/Documents/QATIS/search_results_social \
  --year-min 2024 --year-max 2025 \
  --top-k 20 \
  --platforms x youtube
```

Export to CSV and dedupe:

```bash
python export_results_to_csv.py \
  --results-dir /Users/emilwl/Documents/QATIS/search_results_social/<timestamp> \
  --output social_results.csv \
  --dedupe
```

### 6) Merge CSVs

```bash
python merge_csv.py \
  --input-a /Users/emilwl/Documents/QATIS/search_results/20251015_001826/results_deduped.csv \
  --input-b /Users/emilwl/Documents/QATIS/search_results/20251015_005430/general_results_deduped.csv \
  --output /Users/emilwl/Documents/QATIS/search_results/merged_results.csv \
  --dedupe-on link --prefer first

# Optionally include social
python merge_csv.py \
  --input-a /Users/emilwl/Documents/QATIS/search_results/merged_results.csv \
  --input-b /Users/emilwl/Documents/QATIS/search_results_social/<timestamp>/social_results.csv \
  --output /Users/emilwl/Documents/QATIS/search_results/merged_results_with_social.csv \
  --dedupe-on link --prefer first
```

Check duplicates:

```bash
python check_dupes.py \
  --input /Users/emilwl/Documents/QATIS/search_results/merged_results_with_social.csv \
  --on link --normalize-url
```

### 7) LLM-assisted analysis (intel vs non_intel) + PMESII + BibTeX
- Unified multi-source collection (DDG + OpenAlex + Social):

```bash
python run_multi_collect.py \
  --ddg-queries /Users/emilwl/Documents/QATIS/queries.yaml \
  --openalex-queries /Users/emilwl/Documents/QATIS/queries.yaml \
  --social-queries /Users/emilwl/Documents/QATIS/queries_social.yaml \
  --out-root /Users/emilwl/Documents/QATIS/search_results_multi \
  --ddg-top-k 5 --ddg-pages 2 --include-ru --include-ro \
  --oa-year-min 2024 --oa-year-max 2025 --oa-top-k 10 \
  --social-platforms x youtube --social-year-min 2024 --social-year-max 2025 --social-top-k 20
```

Output: `search_results_multi/<timestamp>/aggregated_results.csv` plus per-source folders.

Minimal spend (no content fetch, small batches):

```bash
python analyze_results.py \
  --results-dir /Users/emilwl/Documents/QATIS/search_results \
  --input merged_results_with_social.csv \
  --model gpt-4o-mini \
  --batch-size 5 \
  --no-fetch
```

Flags:
- `--limit N` analyze first N rows only.
- `--no-cache` ignore prior `analysis_cache.jsonl`.
- Try `--model gpt-4o` if you see defaulted rows.

Outputs (written next to the input CSV):
- `results_scored.csv` (all rows with label/confidence/PMESII/Admiralty)
- `results_scored_intel.csv`, `results_scored_non_intel.csv`
- `pmesii_infrastructure.md` (ASCOPE-aligned sections)
- `intel_sources.bib` (best-effort `@misc` entries)
- `analysis_cache.jsonl` (avoids re-charging for repeats)

### 8) Budgeting guide

- Web/Scholar calls ≈ (#queries) × (#engines) × (#languages). Defaults: 24 × 2 × 3 = 144 calls.
- `--include-ru`/`--include-ro` are multipliers; remove to cut usage.
- LLM cost: Use `--limit`, `--batch-size 5`, and `--no-fetch` to minimize tokens.

### 9) Troubleshooting

- YAML parse error (line 2 scalar): ensure each query is quoted as a single scalar string.
- “timestamp” file not found: replace `<timestamp>` placeholders with the actual folder name printed by the scripts.
- OpenAI `proxies` error: resolved by pinning `httpx==0.27.2` (already in requirements).
- Missing `OPENAI_API_KEY`: add to `.env` and re-run in the same shell.
- All rows `non_intel`: use `--batch-size 5 --no-fetch`, or switch to `--model gpt-4o`.
- CSV export crash on extra fields: handled—only known columns are written.
- Duplicate YouTube links (`watch`): expected; dedupe merges them by normalized link.

### 10) File reference

- `run_searches.py`: Google + Scholar collection (SerpAPI)
- `export_results_to_csv.py`: flatten JSON to CSV; `--dedupe`
- `analyze_results.py`: LLM scoring, PMESII summary, BibTeX
- `run_social_searches.py`: social platform searches (X, YouTube)
- `merge_csv.py`: merge two CSVs with `--dedupe-on link`
- `check_dupes.py`: report duplicate keys (e.g., link)
- `queries.yaml`, `queries_general.yaml`, `queries_social.yaml`: query packages
- `prompts/analyze_instruction.md`: LLM instruction with strict JSON schema
- `README_SEARCH.md`: quickstart for search and analysis

### 11) Example “quick path”

```bash
# 1) Collect
python run_searches.py --queries queries.yaml --output-dir search_results --year-min 2024 --year-max 2025 --top-k 3 --engines web scholar

# 2) CSV + dedupe
python export_results_to_csv.py --results-dir search_results/<timestamp> --output results_deduped.csv --dedupe

# 3) Analyze
python analyze_results.py --results-dir search_results/<timestamp> --input results_deduped.csv --model gpt-4o-mini --batch-size 5 --no-fetch
```


