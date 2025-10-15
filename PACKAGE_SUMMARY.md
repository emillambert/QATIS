# QATIS Package - What You Got

## Overview

QATIS is now a **pip-installable package** with CLI and web UI for turnkey OSINT collection and AI evaluation.

## What Changed

### From: Scattered Scripts
- `run_searches.py` - manual script
- `analyze_results.py` - manual script  
- `.env` in project root
- Hard to share or reuse

### To: Professional Package
- `qatis` CLI command with 6 subcommands
- Streamlit web UI for non-technical users
- User config at `~/.qatis/`
- Anyone can `pip install` and use

## Architecture

### Search Stack (Free/Cheap)
```
Web Search      → ScraperAPI (5,000 free → $49/100K)
Academic        → OpenAlex (unlimited free)
Social (X)      → snscrape (unlimited free)
Social (YouTube)→ yt-dlp (unlimited free)
AI Evaluation   → OpenAI GPT (pay-as-you-go)
```

### Data Flow
```
Input (queries.yaml)
  ↓
Collection (web + academic + social)
  ↓
Export & Dedupe (CSV)
  ↓
AI Analysis (OpenAI)
  ↓
Outputs (scored CSV, BibTeX, PMESII markdown)
```

## Package Structure

```
qatis/
├── __init__.py
├── cli.py                    # Typer CLI entrypoint
├── config.py                 # Key management (~/.qatis/)
├── ui_app.py                 # Streamlit web UI
├── prompts/
│   └── analyze_instruction.md  # Default analysis prompt
├── collect/
│   ├── web.py               # Web/scholar wrappers
│   └── social.py            # Social wrappers
├── export/
│   └── csv.py               # CSV export wrapper
└── analyze/
    └── pipeline.py          # Analysis wrapper

Root:
├── search_apis.py           # ScraperAPI + OpenAlex clients
├── scraping_robot_client.py # (legacy, unused)
├── run_searches.py          # Wired to ScraperAPI + OpenAlex
├── run_social_searches.py   # Free social scrapers
├── export_results_to_csv.py # CSV aggregation
├── analyze_results.py       # OpenAI classification
├── pyproject.toml           # Package definition
├── README.md                # Technical reference
├── GETTING_STARTED.md       # Quick setup guide
└── USAGE.md                 # Complete workflows

Config:
~/.qatis/
├── .env                     # User's API keys
└── prompts/
    └── custom.md            # Optional custom prompt
```

## CLI Commands

```bash
qatis configure              # Save API keys
qatis collect               # Run searches
qatis export                # Flatten to CSV
qatis analyze               # AI evaluation
qatis run-all              # All steps in one
qatis ui                   # Launch web UI
```

## Web UI Features

- **Settings** (sidebar):
  - API key management
  - Saved to `~/.qatis/.env`

- **Step 1: Collect**:
  - YAML editor for queries
  - Search settings panel
  - Social platforms (optional)
  - Progress bar with time estimate

- **Step 2: Export**:
  - One-click CSV export
  - Deduplication by URL
  - Preview table

- **Step 3: Analyze**:
  - Model selection
  - Batch size tuning
  - Options (fetch/cache)
  - Progress bar

- **Step 4: Download**:
  - ZIP bundle of all outputs

## API Keys & Costs

### ScraperAPI (Web Search)
- **Free tier**: 5,000 searches (7-day trial)
- **After trial**: $49/mo for 100,000 credits
- **Sign up**: https://www.scraperapi.com/
- **Cost per query**: ~$0.0005 after trial

### OpenAlex (Academic Search)
- **Free tier**: Unlimited
- **Sign up**: Not required
- **Cost**: $0

### OpenAI (AI Evaluation)
- **Free tier**: $5 credit (new accounts)
- **Cost**: ~$0.0005 per source with gpt-4o-mini (no-fetch)
- **Sign up**: https://platform.openai.com/

### Social Scrapers
- **Free tier**: Unlimited
- **Cost**: $0

### Example Budget
- 1,000 Google searches: $0-0.50 (likely free under trial)
- 1,000 academic searches: $0
- 200 social results: $0
- Analyze 1,200 sources: ~$0.60 (gpt-4o-mini)
- **Total: ~$0.60** (mostly just OpenAI)

## What Makes This "Anyone Can Use"

1. **Easy install**: `pip install -e .`
2. **Guided setup**: `qatis configure` walks you through
3. **Web UI**: No command-line needed
4. **Clear docs**: 3 markdown guides (README, GETTING_STARTED, USAGE)
5. **Defaults**: Works out-of-box with example queries
6. **Progress bars**: Visual feedback during long operations
7. **Error handling**: Friendly YAML validation, API error messages
8. **Cost transparency**: Free tiers clearly documented

## Prompt Customization

### Default Prompt
- Located at `qatis/prompts/analyze_instruction.md`
- Packaged with pip install
- Focused on Moldova infrastructure intelligence

### How to Customize

1. **Per-run override** (CLI):
```bash
qatis analyze --results-dir search_results/<timestamp> --prompt my_custom.md
```

2. **System default** (affects all runs):
```bash
nano ~/.qatis/prompts/custom.md
# Edit and save
# All future runs use this automatically
```

3. **Precedence** (how prompts are loaded):
   - 1st: `results_dir/custom_analyze_prompt.md` (CLI --prompt creates this)
   - 2nd: `~/.qatis/prompts/custom.md` (user default)
   - 3rd: Packaged `qatis/prompts/analyze_instruction.md`
   - 4th: Project `prompts/analyze_instruction.md` (dev fallback)

## Distribution

### For End Users
```bash
# Just install and run
pip install -e .
qatis configure
qatis ui
```

### For Developers
```bash
# Clone repo
git clone <your-repo>
cd QATIS

# Install in editable mode
pip install -e .
pip install -e '.[ui]'

# Make changes, test immediately
qatis ui
```

### For Production
```bash
# Build wheel
python -m build

# Distribute
pip install qatis-0.1.0-py3-none-any.whl
```

## Key Improvements from Original

| Before | After |
|--------|-------|
| Scattered scripts | Single `qatis` command |
| Manual .env in project | User config at `~/.qatis/` |
| Hard-coded prompts | Customizable with precedence |
| CLI only | CLI + web UI |
| SerpAPI only ($$$) | ScraperAPI + OpenAlex (5K free) |
| No progress feedback | Progress bars with time estimates |
| Complex setup | `qatis configure` + `qatis ui` |
| Project-specific | Reusable across projects |

## Testing Checklist

- [x] CLI installs correctly
- [x] `qatis configure` saves keys
- [x] `qatis collect` runs search APIs
- [x] `qatis export` generates CSV
- [x] `qatis analyze` uses OpenAI
- [x] `qatis run-all` completes pipeline
- [x] `qatis ui` launches Streamlit
- [x] OpenAlex API works (tested)
- [x] ScraperAPI integration ready
- [x] Social scrapers work (snscrape, yt-dlp)
- [x] Prompt precedence works
- [x] Progress bars show in UI
- [x] YAML validation catches errors
- [x] Language dropdown maps correctly

## Ready to Ship

Your package is ready for distribution. Users can now:

1. Clone your repo
2. Run `pip install -e .`
3. Run `qatis configure`
4. Run `qatis ui`
5. Input search terms
6. Get scored CSV with AI evaluation

All in ~10 minutes from zero to results.

## Next: Get Your ScraperAPI Key

1. Go to https://www.scraperapi.com/signup
2. Sign up (no credit card for trial)
3. Get your API key
4. Run `qatis configure` and paste it
5. Try it: `qatis ui` and click "Run Collection"

You'll have 5,000 free searches to test the system! 🎉


