import io
import pathlib
import zipfile
from typing import Optional

import streamlit as st

from qatis.config import Keys, ensure_dirs, load_keys, save_keys, PROMPTS_DIR


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
        srobot = st.text_input("SCRAPING_ROBOT_API_KEY", value=keys.scraping_robot_api_key or "", type="password")
        serp = st.text_input("SERPAPI_API_KEY (optional)", value=keys.serpapi_api_key or "", type="password")
        if st.button("Save Keys"):
            save_keys(Keys(openai, srobot, serp))
            st.success("Saved to ~/.qatis/.env")

        st.divider()
        st.subheader("Prompt")
        use_custom = st.checkbox("Use custom prompt", value=False)
        custom_text: Optional[str] = None
        if use_custom:
            existing = ""
            custom_path = PROMPTS_DIR / "custom.md"
            if custom_path.exists():
                existing = custom_path.read_text(encoding="utf-8")
            custom_text = st.text_area("Custom Prompt", value=existing, height=300)
            if st.button("Save Prompt"):
                p = save_prompt(custom_text or "")
                st.success(f"Saved to {p}")

    st.header("1) Collect")
    col1, col2 = st.columns(2)
    with col1:
        queries_text = st.text_area("Queries (YAML)", height=220, placeholder="areas:\n  - 'Moldelectrica 2024'\n")
        upload = st.file_uploader("...or upload queries.yaml", type=["yaml", "yml"])
    with col2:
        year_min = st.number_input("Year min", value=2024)
        year_max = st.number_input("Year max", value=2025)
        top_k = st.number_input("Top K", value=3)
        engines = st.multiselect("Engines", ["web", "scholar"], default=["web", "scholar"])
        include_ru = st.checkbox("Include Russian bias (lr=lang_ru)")
        include_ro = st.checkbox("Include Romanian bias (lr=lang_ro)")

    run_collect = st.button("Run Collection")
    results_dir = st.session_state.get("results_dir")
    if run_collect:
        ensure_dirs()
        out_root = pathlib.Path("search_results")
        # Persist queries to a temp file
        if upload is not None:
            q_path = pathlib.Path("queries_ui.yaml")
            q_path.write_bytes(upload.getvalue())
        else:
            q_path = pathlib.Path("queries_ui.yaml")
            q_path.write_text(queries_text or "", encoding="utf-8")

        import subprocess, sys
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
        r = subprocess.run(args, capture_output=True, text=True)
        st.code(r.stdout + "\n" + r.stderr)
        # Find most recent dir
        subs = sorted([p for p in pathlib.Path(out_root).iterdir() if p.is_dir()], reverse=True)
        if subs:
            results_dir = subs[0]
            st.session_state["results_dir"] = str(results_dir)
            st.success(f"Results dir: {results_dir}")

    st.header("2) Export & Dedupe")
    if results_dir:
        if st.button("Export CSV"):
            import subprocess, sys
            args = [
                sys.executable, "export_results_to_csv.py",
                "--results-dir", str(results_dir),
                "--output", "results_deduped.csv",
                "--dedupe",
            ]
            r = subprocess.run(args, capture_output=True, text=True)
            st.code(r.stdout + "\n" + r.stderr)
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
            import subprocess, sys
            args = [
                sys.executable, "analyze_results.py",
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
            r = subprocess.run(args, capture_output=True, text=True)
            st.code(r.stdout + "\n" + r.stderr)
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


