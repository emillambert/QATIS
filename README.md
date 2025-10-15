# QATIS - OSINT Collection and AI Evaluation

Turnkey CLI and web UI for OSINT collection (web, academic, social) with AI-powered relevance evaluation and structured outputs.

## Features

- 🔍 **Multi-source collection**: Google (ScraperAPI), Academic papers (OpenAlex), Twitter/X, YouTube
- 🤖 **AI evaluation**: OpenAI GPT classification with PMESII tagging and Admiralty codes
- 📊 **Structured outputs**: CSV, BibTeX, PMESII markdown summaries
- 💻 **Dual interface**: CLI for automation + Streamlit web UI for interactive use
- 💰 **Cost-effective**: 5,000 free ScraperAPI searches + unlimited OpenAlex academic + free social scrapers

## Quick Start

### 1. Install

#### Option A: Python 3.11 (recommended for UI)
```bash
# Using Homebrew on macOS
brew install python@3.11
/opt/homebrew/bin/python3.11 -m venv .venv
source .venv/bin/activate

# Install
pip install -e .
pip install -e '.[ui]'  # Optional: for web UI
```

#### Option B: Python 3.14+ (CLI only)
```bash
pip install -e . --break-system-packages
```

### 2. Get API Keys

1. **ScraperAPI** (5,000 free searches):
   - Sign up at https://www.scraperapi.com/
   - Get your API key from dashboard
   - 7-day free trial with 5,000 credits

2. **OpenAI** (for AI evaluation):
   - Get key from https://platform.openai.com/api-keys
   - ~$0.01-0.05 per 100 sources analyzed with gpt-4o-mini

### 3. Configure

```bash
qatis configure
# Enter your OPENAI_API_KEY
# Enter your SCRAPERAPI_API_KEY
```

Or manually edit `~/.qatis/.env`:
```bash
OPENAI_API_KEY=sk-...
SCRAPERAPI_API_KEY=...
```

### 4. Run

#### Web UI (easiest)
```bash
qatis ui
# Opens in browser at http://localhost:8501
```

#### CLI (automation)
```bash
# One-shot: collect → export → analyze
qatis run-all --queries queries.yaml

# Or step-by-step:
qatis collect --queries queries.yaml --top-k 20
qatis export --results-dir search_results/<timestamp>
qatis analyze --results-dir search_results/<timestamp>
```

## Usage

### Web UI Workflow

1. **Configure** (sidebar):
   - Enter API keys
   - Save

2. **Collect**:
   - Edit queries in YAML editor (left panel)
   - Set search settings (right panel): year range, results per query, engines, language
   - Optional: enable social platforms (X, YouTube)
   - Click "Run Collection"

3. **Export & Dedupe**:
   - Click "Export CSV"
   - Preview deduped results

4. **Analyze**:
   - Set model, batch size, options
   - Click "Run Analysis"
   - Preview scored results with intel/non-intel labels

5. **Download**:
   - Download ZIP bundle with all outputs

### Query Format (YAML)

```yaml
areas:
  - 'Moldova infrastructure 2024'
  - 'Moldelectrica energy grid'

structures:
  - 'Moldelectrica ownership OR restructuring'
  - '"Energy Community Moldova" filetype:pdf'

# ... add more categories: capabilities, organisations, people, events
```

**Rules:**
- Wrap each query in single quotes
- For complex queries with quotes/colons, use: `'"phrase search" OR site:example.com'`

### Custom Analysis Prompt

Edit the analysis prompt at `~/.qatis/prompts/custom.md` to customize:
- Classification criteria
- PMESII categories
- Source types
- Admiralty code assignment

The default prompt focuses on Moldova infrastructure intelligence.

## Outputs

All outputs are written to `search_results/<timestamp>/`:

- `results_scored.csv` - All sources with AI labels, confidence, PMESII tags, Admiralty codes
- `results_scored_intel.csv` - Intelligence sources only
- `results_scored_non_intel.csv` - Non-intelligence sources
- `pmesii_infrastructure.md` - PMESII-organized summary
- `intel_sources.bib` - BibTeX bibliography of intel sources
- `analysis_cache.jsonl` - Cache to avoid re-analyzing

## Cost Breakdown

### Free Tier (5,000+ searches)
- **ScraperAPI**: 5,000 Google searches (7-day trial)
- **OpenAlex**: Unlimited academic paper searches
- **Social**: Unlimited (snscrape + yt-dlp)

### After Free Tier
- **ScraperAPI**: $49/mo for 100,000 API credits (~$0.00049/search)
- **OpenAI**: ~$0.01-0.05 per 100 sources (gpt-4o-mini)
- **Social**: Still free

**Example cost for 1,000 sources:**
- Collection: ~$5 (if over free tier)
- Analysis: ~$0.50 (OpenAI)
- **Total: ~$5.50** vs ~$30+ with SerpAPI

## CLI Commands

```bash
# Configure keys
qatis configure

# Collect from all sources
qatis collect --queries queries.yaml --year-min 2024 --year-max 2025 --top-k 20

# Export to CSV with deduplication
qatis export --results-dir search_results/<timestamp> --dedupe

# Analyze with AI
qatis analyze --results-dir search_results/<timestamp> --model gpt-4o-mini --batch-size 20

# All-in-one
qatis run-all --queries queries.yaml --year-min 2024 --year-max 2025 --top-k 20

# Launch web UI
qatis ui
```

## Advanced

### Language Variants
```bash
qatis collect --queries queries.yaml --include-ru --include-ro
# Runs queries in English + Russian + Romanian
```

### Social Collection
```bash
# Separate social run
python run_social_searches.py --queries queries_social.yaml --platforms x youtube --top-k 20
```

### Custom Prompt
```bash
# CLI
qatis analyze --results-dir search_results/<timestamp> --prompt my_custom_prompt.md

# Or edit default
nano ~/.qatis/prompts/custom.md
```

### Analysis Options
```bash
# Minimize cost: skip fetching article text, use small batches
qatis analyze --results-dir search_results/<timestamp> --no-fetch --batch-size 5 --limit 100

# Use better model
qatis analyze --results-dir search_results/<timestamp> --model gpt-4o
```

## Troubleshooting

### "Missing SCRAPERAPI_API_KEY"
- Run `qatis configure` and enter your ScraperAPI key
- Or manually add to `~/.qatis/.env`

### Empty results / 400 errors
- ScraperAPI trial expired: sign up for paid plan or use a different email for another trial
- Check your balance at https://dashboard.scraperapi.com/

### YAML parse errors
- Ensure each query is wrapped in single quotes
- Complex queries: `'"exact phrase" OR keyword filetype:pdf'`

### UI won't start (Python 3.14)
- Use Python 3.11: `brew install python@3.11` and create venv with 3.11
- Or skip UI and use CLI only

### Social scrapers failing
- X/Twitter: snscrape may break if Twitter changes their HTML
- YouTube: yt-dlp usually stable
- Both are free but may require occasional updates

## File Structure

```
~/.qatis/
  .env              # Your API keys
  prompts/
    custom.md       # Your custom analysis prompt

search_results/
  <timestamp>/
    *.json          # Raw results per query
    *.md            # Human-readable results
    results_scored.csv          # Main output
    results_scored_intel.csv    # Intel only
    pmesii_infrastructure.md    # PMESII summary
    intel_sources.bib          # Bibliography
```

## Support

- ScraperAPI docs: https://docs.scraperapi.com/
- OpenAlex docs: https://docs.openalex.org/
- OpenAI models: https://platform.openai.com/docs/models

## License

MIT


