# QATIS Usage Guide

## Complete Workflow: From Search Terms to Scored CSV

### Prerequisites
- Python 3.11+ installed
- Internet connection
- API keys (see GETTING_STARTED.md)

### End-to-End Example

#### Using the Web UI (Recommended)

1. **Start the UI**
```bash
qatis ui
```

2. **Configure** (one-time, in sidebar):
   - Enter `OPENAI_API_KEY`
   - Enter `SCRAPERAPI_API_KEY` (get 5,000 free at scraperapi.com)
   - Click "Save Keys"

3. **Collect** (Step 1):
   - Edit queries in the left panel (or use defaults)
   - Optional: select social platforms (X, YouTube)
   - Adjust settings in right panel
   - Click "Run Collection"
   - Progress bar shows status with time remaining

4. **Export** (Step 2):
   - Click "Export CSV"
   - Preview deduped results table

5. **Analyze** (Step 3):
   - Keep defaults (gpt-4o-mini, batch=20)
   - Click "Run Analysis"
   - View scored results with intel labels

6. **Download** (Step 4):
   - Click "Download bundle (zip)"
   - Extract to get all CSVs, markdown, and bibliography

#### Using the CLI

```bash
# 1. Configure (one-time)
qatis configure
# Paste your OPENAI_API_KEY
# Paste your SCRAPERAPI_API_KEY

# 2. Create queries.yaml
cat > my_queries.yaml << 'EOF'
areas:
  - 'Moldova infrastructure 2024'
  - 'Moldelectrica energy grid'
  - 'Transnistria power supply'

structures:
  - 'Moldelectrica ownership'
  - 'Energy Community Moldova'

capabilities:
  - 'Moldova energy dependence Russia'
  - 'grid resilience Moldova'
EOF

# 3. Run complete pipeline
qatis run-all \
  --queries my_queries.yaml \
  --year-min 2024 \
  --year-max 2025 \
  --top-k 20 \
  --engines web scholar \
  --model gpt-4o-mini \
  --batch-size 20 \
  --no-fetch

# Output directory path is printed at the end
# Results are in: search_results/<timestamp>/results_scored.csv
```

### Step-by-Step CLI

```bash
# Step 1: Collect from Google + OpenAlex
qatis collect \
  --queries queries.yaml \
  --year-min 2024 \
  --year-max 2025 \
  --top-k 20 \
  --engines web scholar

# Step 2: Export and deduplicate
qatis export \
  --results-dir search_results/20251015_103707 \
  --output results_deduped.csv \
  --dedupe

# Step 3: Analyze with AI
qatis analyze \
  --results-dir search_results/20251015_103707 \
  --input results_deduped.csv \
  --model gpt-4o-mini \
  --batch-size 20 \
  --no-fetch

# Outputs:
# - results_scored.csv (all sources with labels)
# - results_scored_intel.csv (intel only)
# - results_scored_non_intel.csv (non-intel only)
# - pmesii_infrastructure.md (organized summary)
# - intel_sources.bib (bibliography)
```

## Understanding the Outputs

### results_scored.csv

Columns:
- `category`, `query`, `language`, `engine` - Search metadata
- `title`, `link`, `snippet` - Source content
- `label` - **"intel" or "non_intel"** (AI classification)
- `confidence` - 0.0 to 1.0 (AI confidence)
- `pmesii` - Tags: Areas, Structures, Capabilities, Organisations, People, Events
- `source_type` - news, report, journal, gov, NGO, company, think_tank, other
- `admiralty_source_reliability` - A to F (A=completely reliable, F=unreliable)
- `admiralty_info_credibility` - 1 to 6 (1=confirmed, 6=cannot be judged)
- `rationale` - Why it was classified as intel/non-intel

### Filtering Results

```bash
# Get only intel sources
grep ",intel," search_results/<timestamp>/results_scored.csv

# Or use results_scored_intel.csv directly
open search_results/<timestamp>/results_scored_intel.csv
```

### PMESII Summary

`pmesii_infrastructure.md` organizes intel sources by category:
- **Areas**: Physical/digital infrastructure locations
- **Structures**: Ownership, control, organization
- **Capabilities**: Performance, resilience, vulnerabilities
- **Organisations**: Actors, donors, influence
- **People**: Workforce, public impact
- **Events**: Incidents, crises, turning points

## Customizing the Analysis

### Edit the Prompt

The analysis prompt defines:
- What counts as "intel" vs "non-intel"
- How to assign PMESII categories
- Source type classifications
- Admiralty code criteria

**To customize:**

1. Via CLI:
```bash
# Copy default prompt
cp qatis/prompts/analyze_instruction.md my_prompt.md

# Edit it
nano my_prompt.md

# Use it
qatis analyze --results-dir search_results/<timestamp> --prompt my_prompt.md
```

2. Via system default:
```bash
# Edit global custom prompt
nano ~/.qatis/prompts/custom.md

# All future analyses will use this
```

### Example: Different Research Question

If your RQ is about cybersecurity instead of infrastructure:

1. Edit `~/.qatis/prompts/custom.md`
2. Change the context section to your RQ
3. Update PMESII definitions for cyber domain
4. Adjust intel criteria

## Cost Management

### Minimize Costs

1. **Use `--no-fetch`**: Skip article text scraping
   - Faster (2-3x)
   - Cheaper OpenAI costs (smaller prompts)
   - Still accurate for most sources

2. **Use `--limit`**: Test with subset
```bash
qatis analyze --results-dir search_results/<timestamp> --limit 50
```

3. **Smaller batches**: More reliable, slightly slower
```bash
qatis analyze --results-dir search_results/<timestamp> --batch-size 5
```

4. **Use cache**: Re-running analysis reuses cached results
   - Cache is at `search_results/<timestamp>/analysis_cache.jsonl`
   - Delete cache file to force re-evaluation

### Estimate Costs

**Collection (5,000 free with ScraperAPI trial):**
- 2 queries × 2 engines × 3 languages = 12 API calls
- 20 queries × 2 engines × 1 language = 40 API calls
- After free tier: ~$0.02 per 40 queries

**Academic (always free):**
- OpenAlex: unlimited

**Social (always free):**
- X, YouTube: unlimited

**Analysis:**
- gpt-4o-mini: ~$0.05 per 100 sources (with --no-fetch)
- gpt-4o: ~$0.50 per 100 sources (more accurate)

**Example: 500 sources**
- Collection: Free (under 5,000 limit)
- Analysis: ~$0.25 (gpt-4o-mini, no-fetch)
- **Total: $0.25**

## Advanced Usage

### Multi-language Collection

```bash
# English + Russian + Romanian
qatis collect --queries queries.yaml --include-ru --include-ro --top-k 10

# Triples the API calls but captures more sources
```

### Social Media Only

```bash
# Skip web/scholar, do social only
python run_social_searches.py \
  --queries queries_social.yaml \
  --platforms x youtube \
  --top-k 50
```

### Merge Multiple Runs

```bash
# Collect from different time periods
qatis collect --queries queries.yaml --year-min 2023 --year-max 2023 --top-k 10
qatis collect --queries queries.yaml --year-min 2024 --year-max 2025 --top-k 10

# Export both
qatis export --results-dir search_results/20251015_120000 --output r1.csv --dedupe
qatis export --results-dir search_results/20251015_120500 --output r2.csv --dedupe

# Merge
python merge_csv.py \
  --input-a search_results/20251015_120000/r1.csv \
  --input-b search_results/20251015_120500/r2.csv \
  --output merged.csv \
  --dedupe-on link \
  --prefer first
```

### Check for Duplicates

```bash
python check_dupes.py \
  --input search_results/<timestamp>/results_deduped.csv \
  --on link \
  --normalize-url
```

## Tips & Tricks

1. **Start with defaults**: Run a test with 2-3 queries first
2. **Check quality**: Review `results_scored_intel.csv` for relevance
3. **Tune the prompt**: If too many false positives/negatives, edit the analysis prompt
4. **Use PMESII summary**: `pmesii_infrastructure.md` gives you a structured overview
5. **Export to Excel**: Open CSV in Excel/Google Sheets for filtering and analysis
6. **Cite sources**: Use `intel_sources.bib` for academic citations

## Common Workflows

### Quick Triage (30 sources, 5 minutes)
```bash
qatis run-all \
  --queries queries.yaml \
  --top-k 5 \
  --limit 30 \
  --no-fetch \
  --batch-size 10
```

### Comprehensive Collection (500 sources, 1 hour)
```bash
qatis run-all \
  --queries queries.yaml \
  --top-k 20 \
  --engines web scholar \
  --batch-size 20 \
  --no-fetch
```

### Deep Dive (with full-text analysis, slower)
```bash
qatis run-all \
  --queries queries.yaml \
  --top-k 10 \
  --model gpt-4o \
  --batch-size 10
# Fetches article text and uses best model
```

## Troubleshooting

### No results returned
- Check ScraperAPI balance: https://dashboard.scraperapi.com/
- Try simpler queries without special operators
- Reduce `--top-k` if hitting rate limits

### All sources marked "non_intel"
- Check your analysis prompt
- Try `--model gpt-4o` for better accuracy
- Use `--no-fetch` (sometimes full text confuses the model)

### YAML errors
- Use single quotes around entire query string
- Escape internal quotes: `'"phrase search" OR keyword'`
- Test YAML at https://www.yamllint.com/

### Import errors
- Reinstall: `pip install -e . --force-reinstall`
- Check Python version: `python --version` (need 3.10+)

## Next Steps

- Read `README.md` for technical details
- See `GETTING_STARTED.md` for initial setup
- Check example `queries.yaml` for query patterns
- Review `prompts/analyze_instruction.md` for prompt structure

Happy intelligence gathering! 🎯


