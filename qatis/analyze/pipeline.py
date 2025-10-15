import subprocess
import pathlib
from typing import Optional


def analyze_results(
    results_dir: pathlib.Path,
    input_csv: str = "results_deduped.csv",
    model: str = "gpt-4o-mini",
    batch_size: int = 20,
    limit: int = 0,
    no_fetch: bool = False,
    no_cache: bool = False,
    prompt_path: Optional[pathlib.Path] = None,
):
    args = [
        "python", "analyze_results.py",
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
    if prompt_path:
        override_path = pathlib.Path(results_dir) / "custom_analyze_prompt.md"
        override_path.write_text(pathlib.Path(prompt_path).read_text(encoding="utf-8"), encoding="utf-8")
    subprocess.run(args, check=True)



