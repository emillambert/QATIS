import io
import os
import pathlib
import zipfile
import time
import subprocess
import sys
from typing import Optional

import streamlit as st

from qatis.config import Keys, ensure_dirs, load_keys, save_keys, PROMPTS_DIR
from importlib import resources as ilres
import yaml


st.set_page_config(page_title="QATIS", layout="wide")


def save_prompt(text: str):
    ensure_dirs()
    path = PROMPTS_DIR / "custom.md"
    path.write_text(text, encoding="utf-8")
    return path


def main():
    st.title("QATIS — OSINT Collection and AI Evaluation")

    with st.sidebar:
        st.header("Configuration")
        keys = load_keys()
        openai = st.text_input("OPENAI_API_KEY", value=keys.openai_api_key or "", type="password")
        scraperapi = st.text_input("SCRAPERAPI_API_KEY", value=keys.scraperapi_api_key or "", type="password", help="Get 5000 free at scraperapi.com")
        
        st.divider()
        st.subheader("Enhanced Social Scrapers")
        reddit_client_id = st.text_input("Reddit Client ID", value=keys.reddit_client_id or "", type="password", help="Get from https://www.reddit.com/prefs/apps")
        reddit_client_secret = st.text_input("Reddit Client Secret", value=keys.reddit_client_secret or "", type="password")
        vk_token = st.text_input("VK Access Token (optional)", value=keys.vk_token or "", type="password", help="Optional: improves VK search results")

        # X/Twitter advanced options
        st.markdown("X/Twitter (optional)")
        x_session_dir = st.text_input("X Session Dir (twscrape)", value=str(pathlib.Path.home() / ".twscrape"))
        
        if st.button("Save Keys"):
            save_keys(Keys(
                openai_api_key=openai,
                scraperapi_api_key=scraperapi,
                reddit_client_id=reddit_client_id,
                reddit_client_secret=reddit_client_secret,
                vk_token=vk_token
            ))
            st.success("Saved to ~/.qatis/.env")

        st.divider()
        st.subheader("Analysis Prompt")
        # Load current prompt (from custom or default)
        try:
            custom_path = PROMPTS_DIR / "custom.md"
            if custom_path.exists():
                current_prompt = custom_path.read_text(encoding="utf-8")
            else:
                current_prompt = ilres.files("qatis").joinpath("prompts/analyze_instruction.md").read_text(encoding="utf-8")
        except Exception:
            current_prompt = ""
        
        prompt_text = st.text_area("Prompt (editable)", value=current_prompt, height=300, help="Edit and save to customize analysis")
        if st.button("Save Prompt"):
            p = save_prompt(prompt_text)
            st.success(f"Saved to {p}")

    st.header("1) Collect")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Web/Scholar Queries")
        with st.expander("ℹ️ Query Format Guide", expanded=True):
            st.markdown("""
**Format:** Category-based YAML with quoted strings

```yaml
category_name:
  - 'simple query'
  - 'phrase with "quotes" inside'
  - '"exact phrase" OR keyword'
  - 'site:example.com keyword'
  - 'filetype:pdf keyword'
  - '"keyword" 2024..2025'
```

**Tips:**
- Wrap each query in single quotes `'...'`
- Use double quotes inside for exact phrases
- Boolean: `OR`, `AND`, `NOT`
- Date range: `2024..2025`
- Site filter: `site:europa.eu`
- File type: `filetype:pdf`

**Examples:**
```yaml
areas:
  - 'Moldova infrastructure'
  - '"power grid" Moldova'
structures:
  - 'Moldelectrica ownership'
  - '"Energy Community" Moldova filetype:pdf'
```
            """)
        # Default: short and properly formatted
        default_queries = (
            "test:\n"
            "  - 'Moldova'\n"
        )
        queries_text = st.text_area("Queries (YAML)", height=200, value=default_queries, key="queries_yaml_input")

        st.markdown("")
        st.subheader("Social Queries")
        with st.expander("ℹ️ Social Query Format Guide", expanded=True):
            st.markdown("""
**Format:** Platform-specific YAML structure

```yaml
x:
  queries:
    - 'keyword since:2024-01-01 until:2025-12-31'
    - 'from:username keyword'
    - '#hashtag lang:en'

youtube:
  queries:
    - 'keyword 2024'
    - 'channel_name topic'

reddit:
  subreddits:
    - 'worldnews'
    - 'europe'
  queries:
    - 'Moldova'
    - 'infrastructure'

vk:
  queries:
    - 'Moldova'
    - 'Молдова'  # Cyrillic works
```

**X/Twitter syntax:**
- Time: `since:2024-01-01 until:2025-12-31`
- User: `from:username` or `to:username`
- Language: `lang:en`, `lang:ru`
- Hashtag: `#keyword`

**YouTube syntax:**
- Simple keywords work best
- Year helps: `Moldova 2024`
- Channel: `"Channel Name" topic`

**Reddit:**
- Specify subreddits to search
- Queries searched across those subs
- Requires Client ID/Secret (see sidebar)

**VK:**
- Supports Cyrillic and Latin
- Optional token improves results
- Searches public posts/groups
            """)
        default_social = (
            "x:\n"
            "  queries:\n"
            "    - 'Moldova'\n"
            "youtube:\n"
            "  queries:\n"
            "    - 'Moldova'\n"
            "reddit:\n"
            "  subreddits:\n"
            "    - 'worldnews'\n"
            "  queries:\n"
            "    - 'Moldova'\n"
            "vk:\n"
            "  queries:\n"
            "    - 'Moldova'\n"
        )
        social_queries_text = st.text_area("Social Queries (YAML)", height=140, value=default_social, help="Used if social platforms are selected")

        # Social enhancement options
        col3, col4 = st.columns(2)
        with col3:
            use_transcripts = st.checkbox("Use YouTube transcripts", value=True, help="Enable YouTube transcript extraction (requires youtube-transcript-api)")
        with col4:
            include_comments = st.checkbox("Include Reddit top comments", value=True, help="Include Reddit post comments in analysis (requires praw)")
    with col2:
        st.subheader("Search Settings")
        speed_mode = st.checkbox("Speed mode (fast defaults)", value=False, help="Optimized for speed: web only, English only, small top_k, concurrency, minimal disk writes")
        year_min = st.number_input("Year min", value=2024)
        year_max = st.number_input("Year max", value=2025)
        default_top_k = 5 if speed_mode else 20
        top_k = st.number_input("Results per query (per engine)", value=default_top_k)

        # Combined engines selection (web/academic + social platforms)
        all_engines = ["web", "scholar", "x", "youtube", "reddit", "vk"]
        default_engines = ["web"] if speed_mode else ["web", "scholar"]
        engines = st.multiselect("Engines & Platforms", all_engines, default=default_engines, help="Select web/academic engines and social platforms to search")
        
        # Show dependency hints for social platforms
        selected_social = [e for e in engines if e in ["x", "youtube", "reddit", "vk"]]
        if selected_social:
            with st.expander("📦 Social Platform Dependencies", expanded=True):
                st.markdown("""
**Required packages per platform:**
- **X/Twitter**: `snscrape` (often blocked by Twitter)
- **YouTube**: `yt-dlp` + `youtube-transcript-api` (optional, for transcripts)
- **Reddit**: `praw` + credentials (see sidebar)
- **VK**: `vk-api` (token optional but helpful)

**Install missing packages:**
```bash
pip install -r requirements.txt
```

If scrapers fail, check stderr output after collection.
                """)

        # Separate web and social engines for processing
        web_engines = [e for e in engines if e in ["web", "scholar"]]
        social_platforms = [e for e in engines if e in ["x", "youtube", "reddit", "vk"]]

        default_lang_index = 0  # English only
        lang_choice = st.selectbox("Language bias", ["English only", "Russian only", "Romanian only", "All (en+ru+ro)"], index=default_lang_index)
        include_ru = lang_choice in ["Russian only", "All (en+ru+ro)"]
        include_ro = lang_choice in ["Romanian only", "All (en+ru+ro)"]

    run_collect = st.button("Run Collection")
    results_dir = st.session_state.get("results_dir")
    if run_collect:
        ensure_dirs()
        out_root = pathlib.Path("search_results")
        # Validate queries YAML
        try:
            data = yaml.safe_load(queries_text) or {}
            if not isinstance(data, dict):
                raise ValueError("Top-level must be a mapping of category -> list")
            for k, v in data.items():
                if not isinstance(v, list):
                    raise ValueError(f"Category '{k}' must map to a list of query strings")
        except Exception as e:
            st.error(f"Invalid Queries YAML: {e}")
            return
        
        # Calculate total tasks
        total_queries = sum(len(v) for v in data.values())
        lang_variants = 1
        if include_ru:
            lang_variants += 1
        if include_ro:
            lang_variants += 1
        total_web_scholar = total_queries * len(web_engines) * lang_variants
        
        # Validate social YAML if needed
        total_social = 0
        if social_platforms:
            try:
                sdata = yaml.safe_load(social_queries_text) or {}
                if not isinstance(sdata, dict):
                    raise ValueError("Top-level must be a mapping: platform -> {queries: [...]} ")
                for platform, cfg in sdata.items():
                    if not isinstance(cfg, dict) or not isinstance(cfg.get("queries"), list):
                        raise ValueError(f"Platform '{platform}' requires 'queries: [..]'")
                    if platform in social_platforms:
                        total_social += len(cfg.get("queries", []))
            except Exception as e:
                st.error(f"Invalid Social Queries YAML: {e}")
                return
        
        total_tasks = total_web_scholar + total_social
        completed_tasks = 0
        
        # Persist queries to a temp file
        q_path = pathlib.Path("queries_ui.yaml")
        q_path.write_text(queries_text or "", encoding="utf-8")

        args = [
            sys.executable, "run_searches.py",
            "--queries", str(q_path),
            "--output-dir", str(out_root),
            "--year-min", str(int(year_min)),
            "--year-max", str(int(year_max)),
            "--top-k", str(int(top_k)),
            "--engines", *web_engines,
        ]
        if speed_mode:
            args += ["--concurrency", "6", "--no-markdown"]
        if include_ru:
            args.append("--include-ru")
        if include_ro:
            args.append("--include-ro")
        
        prog = st.progress(0, text="Starting collection...")
        start_time = time.time()
        
        # Only run web/scholar if engines are selected
        if web_engines:
            p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            while p.poll() is None:
                elapsed = time.time() - start_time
                # Estimate: 2 seconds per query
                if total_tasks > 0:
                    estimated_web = total_web_scholar * 2
                    progress_fraction = min(elapsed / estimated_web, 1.0) if estimated_web > 0 else 0
                    # Scale web/scholar to its share of total tasks
                    progress_pct = int((total_web_scholar / total_tasks) * progress_fraction * 100)
                    remaining = max(0, int(estimated_web - elapsed))
                    prog.progress(min(progress_pct / 100, 0.99), text=f"Collecting web/scholar results... (~{remaining}s remaining)")
                else:
                    prog.progress(0, text="Collecting web/scholar results...")
                time.sleep(0.5)
            
            stdout, stderr = p.communicate()
            # Web/scholar phase complete
            if total_tasks > 0:
                web_share = total_web_scholar / total_tasks
                progress_pct = int(web_share * 100)
            else:
                progress_pct = 100
            prog.progress(min(progress_pct / 100, 0.99), text="Web/scholar collection finished")
            st.code((stdout or "") + "\n" + (stderr or ""))
            
            # Find most recent dir
            subs = sorted([p for p in pathlib.Path(out_root).iterdir() if p.is_dir()], reverse=True)
            if subs:
                results_dir = subs[0]
                st.session_state["results_dir"] = str(results_dir)
                st.success(f"Results dir: {results_dir}")
        else:
            # No web engines, start at 0%
            progress_pct = 0

        # Social collection if selected
        if social_platforms and social_queries_text.strip():
            s_out_root = pathlib.Path("search_results_social")
            s_q_path = pathlib.Path("queries_social_ui.yaml")
            s_q_path.write_text(social_queries_text or "", encoding="utf-8")
            s_args = [
                sys.executable, "run_social_searches.py",
                "--queries", str(s_q_path),
                "--output-dir", str(s_out_root),
                "--year-min", str(int(year_min)),
                "--year-max", str(int(year_max)),
                "--top-k", str(int(top_k)),
                "--platforms", *social_platforms,
            ]

            # Add enhanced social scraping flags
            if use_transcripts:
                s_args.append("--use-transcripts")
            else:
                s_args.append("--no-transcripts")

            if include_comments:
                s_args.append("--include-comments")
            else:
                s_args.append("--no-comments")
            social_start = time.time()
            # Pass API keys as environment variables
            social_env = os.environ.copy()
            if reddit_client_id:
                social_env["REDDIT_CLIENT_ID"] = reddit_client_id
            if reddit_client_secret:
                social_env["REDDIT_CLIENT_SECRET"] = reddit_client_secret
            if vk_token:
                social_env["VK_TOKEN"] = vk_token

            # Provide optional X session dir for twscrape fallback
            if x_session_dir:
                social_env["X_SESSION_DIR"] = x_session_dir

            sp = subprocess.Popen(s_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=social_env)
            
            # Add timeout to prevent infinite loops (5 minutes max)
            max_wait = 300
            while sp.poll() is None:
                s_elapsed = time.time() - social_start
                
                # Timeout check
                if s_elapsed > max_wait:
                    sp.terminate()
                    st.warning(f"Social collection timed out after {max_wait}s")
                    break
                
                if total_tasks > 0 and total_social > 0:
                    s_estimated = total_social * 2
                    s_progress_fraction = min(s_elapsed / s_estimated, 1.0) if s_estimated > 0 else 0
                    # Add social progress to web progress
                    social_share = total_social / total_tasks
                    current_pct = progress_pct + int(social_share * s_progress_fraction * 100)
                    s_remaining = max(0, int(s_estimated - s_elapsed))
                    prog.progress(min(current_pct / 100, 0.99), text=f"Collecting social results... (~{s_remaining}s remaining)")
                else:
                    prog.progress(0.5, text="Collecting social results...")
                time.sleep(0.5)
            
            s_stdout, s_stderr = sp.communicate(timeout=5)  # 5s timeout for cleanup
            prog.progress(1.0, text="Collection finished")
            
            # Show both stdout and stderr (stderr contains scraper errors)
            combined_output = ""
            if s_stdout:
                combined_output += s_stdout
            if s_stderr:
                combined_output += "\n" + s_stderr
            st.code(combined_output or "(no output)")

            # Analyze output for common failures and provide actionable guidance
            platform_issues = []
            if "x" in social_platforms and s_stderr:
                if "Twitter" in s_stderr or "snscrape" in s_stderr or "blocked" in s_stderr.lower():
                    platform_issues.append("**X/Twitter**: ❌ Blocked or failed. Twitter actively blocks automated scraping. This platform is unreliable - consider removing it from your selection.")
            
            if "vk" in social_platforms and s_stderr:
                if "VK" in s_stderr or "vk" in s_stderr.lower():
                    platform_issues.append("**VK**: ❌ Failed. VK API may require authentication. Add a VK Access Token in the sidebar for better results.")
            
            if platform_issues:
                with st.expander("⚠️ Platform-Specific Issues Detected", expanded=True):
                    for issue in platform_issues:
                        st.markdown(issue)
                    st.markdown("""
**Working platforms:**
- ✅ **Web/Scholar**: Google Search and Google Scholar (always reliable)
- ✅ **YouTube**: Video search with transcripts (requires `yt-dlp` and `youtube-transcript-api`)
- ✅ **Reddit**: Subreddit search with comments (requires `praw` + credentials in sidebar)

**Problematic platforms:**
- ⚠️ **X/Twitter**: Frequently blocked by Twitter - not recommended
- ⚠️ **VK**: May require VK Access Token for reliable results
                    """)

            # Find most recent social dir
            s_subs = sorted([p for p in pathlib.Path(s_out_root).iterdir() if p.is_dir()], reverse=True)
            if s_subs:
                social_results_dir = s_subs[0]
                # Check if directory has actual results
                index_file = pathlib.Path(social_results_dir) / "index.json"
                if index_file.exists():
                    # Count actual results by platform
                    try:
                        with open(index_file, 'r') as f:
                            index_data = __import__("json").load(f)
                            entries = index_data.get("entries", [])
                            platform_counts = {}
                            for entry in entries:
                                platform = entry.get("category", "unknown")
                                platform_counts[platform] = platform_counts.get(platform, 0) + 1
                            
                            if platform_counts:
                                st.session_state["social_results_dir"] = str(social_results_dir)
                                success_msg = f"Social results dir: {social_results_dir}"
                                for platform, count in platform_counts.items():
                                    success_msg += f"\n- {platform}: {count} queries processed"
                                st.success(success_msg)
                            else:
                                st.warning(f"Social collection completed but no results were saved. Check output above for errors.")
                    except Exception:
                        st.session_state["social_results_dir"] = str(social_results_dir)
                        st.success(f"Social results dir: {social_results_dir}")
                else:
                    st.warning(f"Social collection completed but no results were saved. Check output above for errors.")

    st.header("2) Export & Dedupe")
    export_disabled = not bool(results_dir)
    if st.button("Export CSV", disabled=export_disabled):
        if results_dir:
            args = [
                sys.executable, "export_results_to_csv.py",
                "--results-dir", str(results_dir),
                "--output", "results_deduped.csv",
                "--dedupe",
            ]
            e_prog = st.progress(0, text="Exporting and deduping...")
            eval = 0
            ep = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            while ep.poll() is None:
                eval = (eval + 5) % 100
                e_prog.progress(eval, text="Exporting and deduping...")
                time.sleep(0.2)
            e_stdout, e_stderr = ep.communicate()
            e_prog.progress(100, text="Export finished")
            st.code((e_stdout or "") + "\n" + (e_stderr or ""))
            out_csv = pathlib.Path(results_dir) / "results_deduped.csv"
            if out_csv.exists():
                st.dataframe(
                    __import__("pandas").read_csv(out_csv).head(50)
                )
    if export_disabled:
        st.info("Export will be enabled after Step 1 completes and a results directory is created.")

    # Export social CSV (visible always; disabled until social results exist)
    social_results_dir = st.session_state.get("social_results_dir")
    col_soc_a, col_soc_b = st.columns(2)
    with col_soc_a:
        social_export_disabled = not bool(social_results_dir)
        if st.button("Export Social CSV", disabled=social_export_disabled):
            if social_results_dir:
                s_args = [
                    sys.executable, "export_results_to_csv.py",
                    "--results-dir", str(social_results_dir),
                    "--output", "social_results.csv",
                    "--dedupe",
                ]
                s_prog = st.progress(0, text="Exporting social results...")
                sval = 0
                sp2 = subprocess.Popen(s_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                while sp2.poll() is None:
                    sval = (sval + 5) % 100
                    s_prog.progress(sval, text="Exporting social results...")
                    time.sleep(0.2)
                s_stdout2, s_stderr2 = sp2.communicate()
                s_prog.progress(100, text="Social export finished")
                st.code((s_stdout2 or "") + "\n" + (s_stderr2 or ""))
                s_out_csv = pathlib.Path(social_results_dir) / "social_results.csv"
                if s_out_csv.exists():
                    st.dataframe(__import__("pandas").read_csv(s_out_csv).head(50))
    with col_soc_b:
        # Merge web+social into the web results dir for downstream analysis/download
        merge_disabled = not bool(results_dir) or not bool(social_results_dir)
        if st.button("Merge Web + Social CSV", disabled=merge_disabled):
            if results_dir and social_results_dir:
                merged_out = pathlib.Path(results_dir) / "merged_results_with_social.csv"
                m_args = [
                    sys.executable, "merge_csv.py",
                    "--input-a", str(pathlib.Path(results_dir) / "results_deduped.csv"),
                    "--input-b", str(pathlib.Path(social_results_dir) / "social_results.csv"),
                    "--output", str(merged_out),
                    "--dedupe-on", "link",
                    "--prefer", "first",
                ]
                m_prog = st.progress(0, text="Merging web + social...")
                mval = 0
                mp = subprocess.Popen(m_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                while mp.poll() is None:
                    mval = (mval + 5) % 100
                    m_prog.progress(mval, text="Merging web + social...")
                    time.sleep(0.2)
                m_stdout, m_stderr = mp.communicate()
                m_prog.progress(100, text="Merge finished")
                st.code((m_stdout or "") + "\n" + (m_stderr or ""))
                if merged_out.exists():
                    st.success(f"Merged CSV created: {merged_out}")
                    st.dataframe(__import__("pandas").read_csv(merged_out).head(50))
    if social_export_disabled or merge_disabled:
        st.info("Social export/merge will be enabled once Step 1 creates web and/or social results.")

    st.header("3) Analyze")
    analyze_disabled = not bool(results_dir)
    model_default = "gpt-5"
    batch_default = 50 if st.session_state.get("speed_mode_active") else 20
    model = st.text_input("Model", value=model_default, disabled=analyze_disabled)
    batch_size = st.number_input("Batch size", value=batch_default, disabled=analyze_disabled)
    limit_default = 100 if st.session_state.get("speed_mode_active") else 0
    limit = st.number_input("Limit (0=all)", value=limit_default, disabled=analyze_disabled)
    no_fetch_default = True if st.session_state.get("speed_mode_active") else False
    no_fetch = st.checkbox("No fetch (skip article text)", value=no_fetch_default, disabled=analyze_disabled)
    no_cache = st.checkbox("No cache", disabled=analyze_disabled)

    # Content analysis controls
    col5, col6 = st.columns(2)
    # Persist speed mode in session for analysis defaults
    st.session_state["speed_mode_active"] = speed_mode
    with col5:
        default_mcc = 1500 if speed_mode else 8000
        max_content_chars = st.number_input("Max content chars", value=default_mcc, help="Truncate content beyond this length to control costs", disabled=analyze_disabled)
    with col6:
        default_cm_index = 2 if speed_mode else 0  # min if speed mode else auto
        content_mode = st.selectbox("Content mode", ["auto", "full", "min"], index=default_cm_index, help="auto: prefer full_content, full: always full, min: prefer snippet", disabled=analyze_disabled)

    # Allow selecting which CSV to analyze
    available_inputs = ["results_deduped.csv"]
    if results_dir:
        rd_path = pathlib.Path(results_dir)
        if (rd_path / "merged_results_with_social.csv").exists():
            available_inputs.insert(0, "merged_results_with_social.csv")
    input_choice = st.selectbox("Input CSV", available_inputs, index=0, disabled=analyze_disabled)

    run_analyze = st.button("Run Analysis", disabled=analyze_disabled)
    if run_analyze and results_dir:
        args = [
            sys.executable, "-u", "analyze_results.py",  # -u for unbuffered output
            "--results-dir", str(results_dir),
            "--input", input_choice,
            "--model", model,
            "--batch-size", str(int(batch_size)),
            "--max-content-chars", str(int(max_content_chars)),
            "--content-mode", content_mode,
        ]
        if int(limit) > 0:
            args += ["--limit", str(int(limit))]
        if no_fetch:
            args.append("--no-fetch")
        if no_cache:
            args.append("--no-cache")
        if speed_mode:
            args += ["--concurrency", "4"]
        
        a_prog = st.progress(0, text="Starting analysis...")
        status_placeholder = st.empty()
        
        ap = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1, universal_newlines=True)
        
        output_lines = []
        import re
        
        while ap.poll() is None:
            line = ap.stdout.readline()
            if line:
                output_lines.append(line)
                # Parse progress messages like "Progress: 20/100 (20%)"
                match = re.search(r'Progress: (\d+)/(\d+) \((\d+)%\)', line)
                if match:
                    current, total, pct = match.groups()
                    a_prog.progress(min(int(pct), 99) / 100, text=f"Analyzing... {current}/{total}")
                    status_placeholder.text(f"Processed {current} of {total} sources")
            time.sleep(0.05)
        
        # Get any remaining output
        remaining, _ = ap.communicate()
        if remaining:
            output_lines.append(remaining)
        
        a_prog.progress(1.0, text="Analysis finished")
        status_placeholder.empty()
        st.code("".join(output_lines))
        scored = pathlib.Path(results_dir) / "results_scored.csv"
        if scored.exists():
            st.success("Scored CSV generated")
            st.dataframe(__import__("pandas").read_csv(scored).head(100))
    if analyze_disabled:
        st.info("Analysis will be enabled after Step 2 produces input CSVs in the results directory.")

    st.header("4) Download")
    download_disabled = not bool(results_dir)
    if results_dir:
        rd = pathlib.Path(results_dir)
        bundle = io.BytesIO()
        with zipfile.ZipFile(bundle, "w", zipfile.ZIP_DEFLATED) as z:
            for name in [
                "results_scored.csv",
                "results_scored_intel.csv",
                "results_scored_non_intel.csv",
                "pmesii_infrastructure.md",
                "intel_sources.bib",
                "analysis_cache.jsonl",
                "results_deduped.csv",
            ]:
                p = rd / name
                if p.exists():
                    z.write(p, arcname=name)
        st.download_button(
            "Download bundle (zip)",
            data=bundle.getvalue(),
            file_name="qatis_outputs.zip",
            mime="application/zip",
        )
    else:
        st.download_button(
            "Download bundle (zip)",
            data=b"",
            file_name="qatis_outputs.zip",
            mime="application/zip",
            disabled=True,
        )
        st.info("Download will be enabled after Steps 2–3 generate outputs in the results directory.")


if __name__ == "__main__":
    main()


