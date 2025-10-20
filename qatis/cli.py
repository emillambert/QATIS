import pathlib
import subprocess
import sys
from typing import Optional

import typer

from qatis.config import Keys, ensure_dirs, load_keys, save_keys, PROMPTS_DIR

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.command()
def configure(
    openai_api_key: Optional[str] = typer.Option(None, help="OpenAI API key"),
    scraperapi_api_key: Optional[str] = typer.Option(None, help="ScraperAPI key (5000 free trial)"),
    prompt_path: Optional[pathlib.Path] = typer.Option(None, help="Path to default analysis prompt to copy as custom"),
):
    """Configure API keys and default prompt."""
    ensure_dirs()
    # If values not passed as flags, prompt interactively
    if openai_api_key is None:
        openai_api_key = typer.prompt("OPENAI_API_KEY", default=load_keys().openai_api_key or "", hide_input=True) or None
    if scraperapi_api_key is None:
        scraperapi_api_key = typer.prompt("SCRAPERAPI_API_KEY (get 5000 free at scraperapi.com)", default=load_keys().scraperapi_api_key or "", hide_input=True) or None
    save_keys(Keys(openai_api_key, scraperapi_api_key))
    typer.echo(f"Saved keys to {PROMPTS_DIR.parent}/.env")

    if prompt_path:
        dest = PROMPTS_DIR / "custom.md"
        dest.write_text(pathlib.Path(prompt_path).read_text(encoding="utf-8"), encoding="utf-8")
        typer.echo(f"Saved custom prompt to {dest}")


@app.command()
def collect(
    queries: pathlib.Path = typer.Option(..., help="Path to queries.yaml"),
    output_dir: pathlib.Path = typer.Option("search_results", help="Output directory root"),
    year_min: int = typer.Option(2024, help="Lower year bound"),
    year_max: int = typer.Option(2025, help="Upper year bound"),
    top_k: int = typer.Option(3, help="Top results per engine"),
    engines: str = typer.Option("web scholar", help="Engines to use (space-separated)"),
    include_ru: bool = typer.Option(False, help="Add Russian language bias"),
    include_ro: bool = typer.Option(False, help="Add Romanian language bias"),
):
    """Run web/scholar collection using existing runner."""
    args = [
        sys.executable, "run_searches.py",
        "--queries", str(queries),
        "--output-dir", str(output_dir),
        "--year-min", str(year_min),
        "--year-max", str(year_max),
        "--top-k", str(top_k),
        "--engines", *engines.split(),
    ]
    if include_ru:
        args.append("--include-ru")
    if include_ro:
        args.append("--include-ro")
    subprocess.run(args, check=True)


@app.command()
def export(
    results_dir: pathlib.Path = typer.Option(..., help="Timestamped results dir"),
    output: str = typer.Option("results_deduped.csv", help="CSV output filename"),
    dedupe: bool = typer.Option(True, help="Dedupe by link and union fields"),
):
    """Export JSON results to CSV using existing script."""
    args = [
        sys.executable, "export_results_to_csv.py",
        "--results-dir", str(results_dir),
        "--output", output,
    ]
    if dedupe:
        args.append("--dedupe")
    subprocess.run(args, check=True)


@app.command()
def analyze(
    results_dir: pathlib.Path = typer.Option(..., help="Results directory"),
    input_csv: str = typer.Option("results_deduped.csv", help="Input CSV inside results_dir"),
    model: str = typer.Option("gpt-5", help="OpenAI model"),
    batch_size: int = typer.Option(20, help="Batch size to LLM"),
    limit: int = typer.Option(0, help="Analyze first N rows if >0"),
    no_fetch: bool = typer.Option(False, help="Skip fetching article text"),
    no_cache: bool = typer.Option(False, help="Disable cache reuse"),
    prompt: Optional[pathlib.Path] = typer.Option(None, help="Custom prompt path"),
):
    """Run LLM classification and export scored CSV + artifacts."""
    args = [
        sys.executable, "analyze_results.py",
        "--results-dir", str(results_dir),
        "--input", input_csv,
        "--model", model,
        "--batch-size", str(batch_size),
    ]
    if limit and limit > 0:
        args += ["--limit", str(limit)]
    if no_fetch:
        args.append("--no-fetch")
    if no_cache:
        args.append("--no-cache")

    # If custom prompt provided, copy to results dir as override for this run
    if prompt:
        override_path = pathlib.Path(results_dir) / "custom_analyze_prompt.md"
        override_path.write_text(pathlib.Path(prompt).read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run(args, check=True)


@app.command("run-all")
def run_all(
    queries: pathlib.Path = typer.Option(..., help="Path to queries.yaml"),
    output_dir: pathlib.Path = typer.Option("search_results", help="Output root"),
    year_min: int = typer.Option(2024),
    year_max: int = typer.Option(2025),
    top_k: int = typer.Option(3),
    engines: str = typer.Option("web scholar"),
    include_ru: bool = typer.Option(False),
    include_ro: bool = typer.Option(False),
    model: str = typer.Option("gpt-5"),
    batch_size: int = typer.Option(20),
    limit: int = typer.Option(0),
    no_fetch: bool = typer.Option(False),
    no_cache: bool = typer.Option(False),
):
    """Run collect → export (dedupe) → analyze in one command."""
    collect(
        queries=queries,
        output_dir=output_dir,
        year_min=year_min,
        year_max=year_max,
        top_k=top_k,
        engines=engines,
        include_ru=include_ru,
        include_ro=include_ro,
    )
    # Discover latest timestamp folder
    out = pathlib.Path(output_dir)
    subdirs = sorted([p for p in out.iterdir() if p.is_dir()], reverse=True)
    if not subdirs:
        raise RuntimeError("No output subdirectory found")
    latest = subdirs[0]
    export(results_dir=latest, output="results_deduped.csv", dedupe=True)
    analyze(
        results_dir=latest,
        input_csv="results_deduped.csv",
        model=model,
        batch_size=batch_size,
        limit=limit,
        no_fetch=no_fetch,
        no_cache=no_cache,
        prompt=None,
    )
    typer.echo(str(latest))


@app.command()
def ui():
    """Launch the Streamlit UI."""
    # Resolve module path using importlib.resources to be robust outside repo
    import importlib.resources as ilres
    ui_path = ilres.files("qatis").joinpath("ui_app.py")
    subprocess.run(["streamlit", "run", str(ui_path)], check=True)


