# QATIS Quick Start Guide

## ✅ All Fixed! Here's What Changed

### Problems Solved
1. ✅ **UI no longer gets stuck** during collection (timeout + better error handling)
2. ✅ **Reddit/VK keys now save properly** (button moved after inputs)
3. ✅ **Progress bar accurately reflects web + social phases**
4. ✅ **Social results are now merged into CSV** for analysis
5. ✅ **Missing dependencies are detected** and shown with helpful hints

---

## 🚀 Launch the UI (Easy Way)

```bash
cd /Users/emilwl/Documents/QATIS
./start_ui.sh
```

That's it! The script handles activation and package installation automatically.

**OR manually:**

```bash
cd /Users/emilwl/Documents/QATIS
source .qatis-ui/bin/activate
streamlit run qatis/ui_app.py
```

---

## 📦 What's Installed

All social media dependencies are now installed in your `.qatis-ui` virtual environment:

- ✅ `youtube-transcript-api` - YouTube transcripts
- ✅ `praw` - Reddit scraping
- ✅ `vk-api` - VK (VKontakte) scraping
- ✅ `snscrape` - X/Twitter scraping (often blocked)
- ✅ `yt-dlp` - YouTube metadata

---

## 🎯 How to Use (Complete Workflow)

### 1. Launch UI
```bash
./start_ui.sh
```

### 2. Configure (Sidebar)
- Enter your **OpenAI API key** (required for analysis)
- Enter your **ScraperAPI key** (required for web/scholar)
- Enter **Reddit credentials** (optional, for Reddit scraping)
  - Get from: https://www.reddit.com/prefs/apps
- Enter **VK token** (optional, improves VK results)
- Click **Save Keys**

### 3. Collect Data
**In the main panel:**

1. **Write queries** in YAML format:
   - Web/Scholar queries: `category: - 'query'`
   - Social queries: platform-specific format (see UI hints)

2. **Select engines**: web, scholar, youtube, reddit, vk

3. **Click "Run Collection"**
   - Progress bar shows both web/scholar and social phases
   - Check output for any scraper errors

### 4. Export & Merge
After collection completes:

1. **Click "Export CSV"** → exports web/scholar results
2. **Click "Export Social CSV"** → exports social results
3. **Click "Merge Web + Social CSV"** → creates combined dataset

### 5. Analyze
1. Select **Input CSV**: `merged_results_with_social.csv`
2. Choose **model**: gpt-4o-mini (cheapest) or gpt-4o
3. Set **batch size**: 20 (recommended)
4. **Click "Run Analysis"**
   - Watch progress bar
   - Results saved to `results_scored.csv`

### 6. Download
Click **"Download bundle (zip)"** to get all outputs:
- `results_scored.csv` (all results with AI labels)
- `results_scored_intel.csv` (intel-only)
- `pmesii_infrastructure.md` (PMESII breakdown)
- `intel_sources.bib` (BibTeX citations)

---

## 🔧 Troubleshooting

### "No module named 'qatis'"
**Fix:**
```bash
cd /Users/emilwl/Documents/QATIS
source .qatis-ui/bin/activate
pip install -e .
```

### Social scrapers failing
**Check stderr output** in the UI after collection. Common issues:

- **X/Twitter**: Often blocked (snscrape) → use other platforms
- **YouTube**: Needs `youtube-transcript-api` (✅ installed)
- **Reddit**: Needs credentials in sidebar
- **VK**: Works without token but better with one

### Progress bar stuck at 99%
This is now fixed! But if it happens:
- Check stderr output for errors
- Timeout kicks in after 5 minutes
- UI now shows warning if no results saved

### Keys not saving
Make sure you click **Save Keys** *after* entering all credentials.

---

## 📊 Example: Quick Moldova Test

1. **Web/Scholar queries:**
```yaml
test:
  - 'Moldova infrastructure 2024'
```

2. **Social queries:**
```yaml
youtube:
  queries:
    - 'Moldova energy 2024'
reddit:
  subreddits:
    - 'europe'
  queries:
    - 'Moldova'
```

3. **Select engines:** web, scholar, youtube, reddit
4. **Run → Export → Merge → Analyze → Download**

Done! You now have AI-scored OSINT results combining web, academic, and social sources.

---

## 🎓 Pro Tips

1. **Start small**: Test with 1-2 queries per platform first
2. **YouTube transcripts**: Enable for best analysis quality
3. **Reddit comments**: Enable for context (requires `praw`)
4. **Batch size**: 20 is optimal (balance cost vs speed)
5. **Content mode**: "auto" preferred (uses full_content when available)
6. **Merge before analysis**: Always analyze the merged CSV for complete data

---

## 🆘 Need Help?

- **Setup issues**: Check this guide
- **API errors**: Verify keys in sidebar
- **Scraper failures**: Check stderr output
- **Analysis errors**: Check OpenAI API quota

---

## 📝 What Changed in This Update

**UI Improvements:**
- Progress bar now accurately reflects web + social phases
- Social results can be exported and merged into analysis
- Better error handling and timeout (no more stuck UI)
- Dependency hints shown when selecting social platforms
- Save Keys button moved to proper location

**New Files:**
- `start_ui.sh` - Easy launcher script
- `QUICKSTART.md` - This guide

**Package Updates:**
- All social scraping dependencies installed in `.qatis-ui` venv
- `qatis` package installed in editable mode (`pip install -e .`)

---

**You're all set! Run `./start_ui.sh` to get started.**




