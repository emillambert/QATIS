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

#### Enhanced Social Collection (Optional)
For enhanced social media collection with transcripts and comments:

```bash
pip install -e '.[enhanced-social]'
```

This adds:
- **YouTube transcripts** (youtube-transcript-api)
- **Reddit posts + comments** (praw)
- **VK/VKontakte** (vk-api)
- **Instagram** (instaloader - optional)

### 2. Get API Keys

1. **ScraperAPI** (5,000 free searches):
   - Sign up at https://www.scraperapi.com/
   - Get your API key from dashboard
   - 7-day free trial with 5,000 credits

2. **OpenAI** (for AI evaluation):
   - Get key from https://platform.openai.com/api-keys
   - ~$0.01-0.05 per 100 sources analyzed with gpt-4o-mini

3. **Enhanced Social (optional)**:
   - **Reddit**: Get from https://www.reddit.com/prefs/apps (free, 60 req/min)
   - **VK**: Optional token from https://vk.com/dev/access_token (improves results)

### 3. Configure

```bash
qatis configure
# Enter your OPENAI_API_KEY
# Enter your SCRAPERAPI_API_KEY
# (Optional) REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET for Reddit
# (Optional) VK_TOKEN for VK/VKontakte
```

Or manually edit `~/.qatis/.env`:
```bash
OPENAI_API_KEY=sk-...
SCRAPERAPI_API_KEY=...
# Optional enhanced social scrapers:
REDDIT_CLIENT_ID=...
REDDIT_CLIENT_SECRET=...
VK_TOKEN=...
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
   - Set search settings (right panel): year range, results per query, **combined engines & platforms**, language
   - Select from unified list: web, scholar, X, YouTube, Reddit, VK
   - Enable enhanced features: YouTube transcripts, Reddit comments (in left panel)
   - Click "Run Collection"

3. **Export & Dedupe**:
   - Click "Export CSV"
   - Preview deduped results

4. **Analyze**:
   - Set model, batch size, options
   - Configure content analysis: max chars, content mode (auto/full/min)
   - Click "Run Analysis"
   - Preview scored results with intel/non-intel labels

5. **Download**:
   - Download ZIP bundle with all outputs

### Query Format (YAML)

#### Web/Academic Queries (`queries.yaml`)
```yaml
areas:
  - "Moldova infrastructure overview" OR "critical infrastructure Moldova"
  - "Moldova energy grid" OR "power transmission Moldova site:europa.eu"

structures:
  - Moldelectrica ownership OR restructuring
  - "Energy Community Moldova report" filetype:pdf

# ... add more categories: capabilities, organisations, people, events
```

#### Social Media Queries (`queries_social.yaml`)
```yaml
x:  # Twitter/X
  broad:
    - 'Moldova infrastructure since:2024-01-01 until:2025-12-31 lang:en'
  specific:
    - 'Moldelectrica since:2024-01-01 until:2025-12-31'

reddit:
  queries:
    - 'Moldova infrastructure'
  subreddits:
    - 'geopolitics'
    - 'europe'

vk:
  queries:
    - 'Молдова инфраструктура'  # Russian for VK
```

**Query Architecture:**
- **Web queries** use advanced search operators (OR, site:, filetype:, date ranges)
- **Social queries** are platform-optimized (date syntax for Twitter, subreddits for Reddit, Russian for VK)
- **Future**: Could unify with a query generator that applies platform-specific transformations

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
- Analysis: ~$0.50-2.00 (OpenAI, depends on content length)
- **Total: ~$5.50-7.00** vs ~$30+ with SerpAPI

**Enhanced social content increases analysis costs by 3-5x** due to longer content (transcripts, comments). Use `--max-content-chars` to control this.

## CLI Commands

```bash
# Configure keys
qatis configure

# Collect from all sources (enhanced social optional)
qatis collect --queries queries.yaml --year-min 2024 --year-max 2025 --top-k 20 --platforms web scholar x youtube reddit vk

# Export to CSV with deduplication
qatis export --results-dir search_results/<timestamp> --dedupe

# Analyze with AI (with content controls)
qatis analyze --results-dir search_results/<timestamp> --model gpt-4o-mini --batch-size 20 --max-content-chars 8000

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

### Enhanced Social Collection
```bash
# Separate social run with enhanced features
python run_social_searches.py --queries queries_social.yaml --platforms x youtube reddit vk --top-k 20 --use-transcripts --include-comments

# Environment variables for API keys:
# REDDIT_CLIENT_ID=your_id REDDIT_CLIENT_SECRET=your_secret python run_social_searches.py --platforms reddit
# VK_TOKEN=your_token python run_social_searches.py --platforms vk
```

**Enhanced Features:**
- **YouTube transcripts**: Extracts full video captions (60-70% success rate)
- **Reddit posts + comments**: Includes top 10 comments for context
- **VK/VKontakte**: Russian social network popular in Moldova/Eastern Europe
- **Instagram**: Visual content (optional, requires `instaloader`)

### Custom Prompt
```bash
# CLI
qatis analyze --results-dir search_results/<timestamp> --prompt my_custom_prompt.md

# Or edit default
nano ~/.qatis/prompts/custom.md
```

### Analysis Options
```bash
# Minimize cost: skip fetching article text, use small batches, limit content length
qatis analyze --results-dir search_results/<timestamp> --no-fetch --batch-size 5 --limit 100 --max-content-chars 4000

# Use better model
qatis analyze --results-dir search_results/<timestamp> --model gpt-4o

# Content analysis modes:
# --max-content-chars 8000 (default) - truncate beyond this for cost control
# Content mode: auto (prefer full_content), full (always full), min (prefer snippet)
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
- YouTube: yt-dlp usually stable, transcripts work for 60-70% of videos
- Reddit: praw reliable (60 req/min limit), requires API keys from reddit.com/prefs/apps
- VK: vk-api works well for public content, optional token improves results
- All are free but may require occasional dependency updates: `pip install -e '.[enhanced-social]'`

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


