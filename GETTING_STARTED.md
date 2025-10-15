# Getting Started with QATIS

## What You Get

**Search sources:**
- 🌐 Google web search via ScraperAPI (5,000 free, then $49/100K)
- 🎓 Academic papers via OpenAlex (unlimited free)
- 🐦 Twitter/X via snscrape (free)
- 📹 YouTube via yt-dlp (free)

**AI evaluation:**
- Intel vs non-intel classification
- PMESII tagging (Areas, Structures, Capabilities, Organisations, People, Events)
- Source type + Admiralty codes
- Rationale for each classification

**Outputs:**
- `results_scored.csv` - All sources with AI evaluation
- `results_scored_intel.csv` - Intelligence sources only
- `pmesii_infrastructure.md` - Organized by PMESII categories
- `intel_sources.bib` - Bibliography for citations

## Step-by-Step Setup

### 1. Get Your API Keys (5 minutes)

#### ScraperAPI (required for Google search)
1. Go to https://www.scraperapi.com/signup
2. Sign up with email
3. Copy your API key from the dashboard
4. **You get 5,000 free searches** (7-day trial)

#### OpenAI (required for AI evaluation)
1. Go to https://platform.openai.com/signup
2. Create account
3. Go to https://platform.openai.com/api-keys
4. Create new API key
5. Add $5-10 credit (analyze 100 sources ≈ $0.05 with gpt-4o-mini)

### 2. Install QATIS

#### If you have Python 3.11:
```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -e .
pip install -e '.[ui]'  # For web UI
```

#### If you have Python 3.14:
```bash
# CLI only (UI needs 3.11 due to Streamlit/pyarrow compatibility)
pip install -e . --break-system-packages
```

### 3. Configure

```bash
qatis configure
```

When prompted:
- **OPENAI_API_KEY**: paste your OpenAI key
- **SCRAPERAPI_API_KEY**: paste your ScraperAPI key

Keys are saved to `~/.qatis/.env`

### 4. Run Your First Search

#### Using the Web UI (easiest):
```bash
qatis ui
```

Your browser opens to http://localhost:8501

**In the UI:**
1. Check that your keys are showing (masked) in the sidebar
2. Edit the queries if you want (default is 2 test queries)
3. Click "Run Collection"
4. Wait for progress bar (should take ~30 seconds for 2 queries)
5. Click "Export CSV"
6. Click "Run Analysis"
7. Click "Download bundle (zip)"

#### Using the CLI (automation):
```bash
# Create a queries.yaml file first
cat > my_queries.yaml << 'EOF'
areas:
  - 'Moldova infrastructure 2024'
  - 'Moldelectrica energy grid'
EOF

# Run everything
qatis run-all --queries my_queries.yaml --top-k 10

# Results in search_results/<timestamp>/results_scored.csv
```

## Next Steps

### Customize Your Queries

Edit queries in the UI or create a `queries.yaml` file:

```yaml
areas:
  - 'Moldova power grid infrastructure'
  - 'Transnistria electricity supply'

structures:
  - 'Moldelectrica ownership structure'
  - 'Energy Community Moldova governance'

capabilities:
  - 'Moldova energy independence Russia'
  - 'Moldova grid resilience capacity'

organisations:
  - 'EU4Energy Moldova projects'
  - 'Gazprom Moldova contracts'

people:
  - 'Moldova energy sector workforce'
  - 'brain drain infrastructure Moldova'

events:
  - 'Moldova power outage 2024'
  - 'cyberattack energy infrastructure Moldova'
```

### Customize the Analysis Prompt

The default prompt evaluates sources for Moldova infrastructure intelligence. To customize:

```bash
# Edit the custom prompt
nano ~/.qatis/prompts/custom.md
```

Change:
- Research question and context
- PMESII category definitions
- Intel vs non-intel criteria
- Source type classifications

### Scale Up

Once you've tested with the defaults:

1. **Add more queries** - the UI handles any number
2. **Increase results** - change "Results per query" from 20 to 50+
3. **Add language variants** - select "All (en+ru+ro)" for multilingual results
4. **Enable social** - check X and/or YouTube platforms
5. **Batch analyze** - the analysis step handles hundreds of sources efficiently

### Monitor Costs

- **ScraperAPI**: Check balance at https://dashboard.scraperapi.com/
- **OpenAI**: Check usage at https://platform.openai.com/usage
- **OpenAlex**: Always free
- **Social scrapers**: Always free

## Example Workflow

```bash
# 1. Configure (one-time)
qatis configure

# 2. Collect (5-10 minutes for 50 queries)
qatis collect --queries queries.yaml --top-k 20 --engines web scholar

# 3. Export and dedupe
qatis export --results-dir search_results/20251015_103707

# 4. Analyze with AI (5-15 minutes for 100 sources)
qatis analyze \
  --results-dir search_results/20251015_103707 \
  --model gpt-4o-mini \
  --batch-size 20 \
  --no-fetch  # Skip full-text scraping to save time/cost

# 5. Review outputs
open search_results/20251015_103707/results_scored.csv
open search_results/20251015_103707/pmesii_infrastructure.md
```

## Tips

1. **Start small**: Test with 2-3 queries first
2. **Use `--no-fetch`**: Skips scraping full article text; saves time and OpenAI costs
3. **Cache is your friend**: Re-running analysis uses cache; only new sources are evaluated
4. **Check YAML**: Use https://www.yamllint.com/ if you get parse errors
5. **Monitor credits**: Keep an eye on ScraperAPI dashboard

## Ready to Go!

You're all set. Run `qatis ui` and start collecting intelligence! 🚀


