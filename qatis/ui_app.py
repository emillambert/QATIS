import io
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
        if st.button("Save Keys"):
            save_keys(Keys(openai, scraperapi))
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
        # Default: short and properly formatted
        default_queries = (
            "areas:\n"
            "  - 'Moldova infrastructure 2024'\n"
            "  - 'Moldelectrica energy grid'\n"
        )
        queries_text = st.text_area("Queries (YAML)", height=200, value=default_queries, key="queries_yaml_input")
        
        st.markdown("")
        st.subheader("Social Queries")
        social_platforms = st.multiselect("Social platforms (optional)", ["x", "youtube"], default=[])
        default_social = (
            "x:\n"
            "  queries:\n"
            "    - 'Moldelectrica 2024'\n"
            "youtube:\n"
            "  queries:\n"
            "    - 'Moldelectrica 2024'\n"
        )
        social_queries_text = st.text_area("Social Queries (YAML)", height=140, value=default_social, help="Used if social platforms are selected")
    with col2:
        st.subheader("Search Settings")
        year_min = st.number_input("Year min", value=2024)
        year_max = st.number_input("Year max", value=2025)
        top_k = st.number_input("Results per query (per engine)", value=20)
        engines = st.multiselect("Engines", ["web", "scholar"], default=["web", "scholar"])
        lang_choice = st.selectbox("Language bias", ["English only", "Russian only", "Romanian only", "All (en+ru+ro)"], index=0)
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
        total_web_scholar = total_queries * len(engines) * lang_variants
        
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
            "--engines", *engines,
        ]
        if include_ru:
            args.append("--include-ru")
        if include_ro:
            args.append("--include-ro")
        
        prog = st.progress(0, text="Starting collection...")
        start_time = time.time()
        p = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        
        while p.poll() is None:
            elapsed = time.time() - start_time
            # Estimate: 2 seconds per query
            if total_tasks > 0:
                estimated_total = total_tasks * 2
                progress_pct = min(int((elapsed / estimated_total) * 50), 49)  # Cap at 49% for web/scholar phase
                remaining = max(0, int(estimated_total - elapsed))
                prog.progress(progress_pct, text=f"Collecting web/scholar results... (~{remaining}s remaining)")
            else:
                prog.progress(0, text="Collecting web/scholar results...")
            time.sleep(0.5)
        
        stdout, stderr = p.communicate()
        completed_tasks = total_web_scholar
        if total_tasks > 0:
            progress_pct = int((completed_tasks / total_tasks) * 100)
        else:
            progress_pct = 50
        prog.progress(progress_pct, text="Web/scholar collection finished")
        st.code((stdout or "") + "\n" + (stderr or ""))
        
        # Find most recent dir
        subs = sorted([p for p in pathlib.Path(out_root).iterdir() if p.is_dir()], reverse=True)
        if subs:
            results_dir = subs[0]
            st.session_state["results_dir"] = str(results_dir)
            st.success(f"Results dir: {results_dir}")

        # Social collection if selected
        if social_platforms:
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
            social_start = time.time()
            sp = subprocess.Popen(s_args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            while sp.poll() is None:
                s_elapsed = time.time() - social_start
                if total_tasks > 0:
                    s_estimated = total_social * 2
                    s_pct_phase = min(int((s_elapsed / s_estimated) * 50), 49) if s_estimated > 0 else 0
                    current_pct = progress_pct + s_pct_phase
                    s_remaining = max(0, int(s_estimated - s_elapsed))
                    prog.progress(min(current_pct, 99), text=f"Collecting social results... (~{s_remaining}s remaining)")
                else:
                    prog.progress(50, text="Collecting social results...")
                time.sleep(0.5)
            s_stdout, s_stderr = sp.communicate()
            prog.progress(100, text="Collection finished")
            st.code((s_stdout or "") + "\n" + (s_stderr or ""))

    st.header("2) Export & Dedupe")
    if results_dir:
        if st.button("Export CSV"):
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

    st.header("3) Analyze")
    if results_dir:
        model = st.text_input("Model", value="gpt-4o-mini")
        batch_size = st.number_input("Batch size", value=20)
        limit = st.number_input("Limit (0=all)", value=0)
        no_fetch = st.checkbox("No fetch (skip article text)")
        no_cache = st.checkbox("No cache")
        run_analyze = st.button("Run Analysis")
        if run_analyze:
            args = [
                sys.executable, "-u", "analyze_results.py",  # -u for unbuffered output
                "--results-dir", str(results_dir),
                "--input", "results_deduped.csv",
                "--model", model,
                "--batch-size", str(int(batch_size)),
            ]
            if int(limit) > 0:
                args += ["--limit", str(int(limit))]
            if no_fetch:
                args.append("--no-fetch")
            if no_cache:
                args.append("--no-cache")
            
            a_prog = st.progress(0, text="Starting analysis...")
            status_placeholder = st.empty()
            
            import subprocess
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

    st.header("4) Download")
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


if __name__ == "__main__":
    main()


