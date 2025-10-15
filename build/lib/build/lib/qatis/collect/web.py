import subprocess
import pathlib


def collect_web(
    queries: pathlib.Path,
    output_dir: pathlib.Path,
    year_min: int,
    year_max: int,
    top_k: int,
    engines: str,
    include_ru: bool,
    include_ro: bool,
):
    args = [
        "python", "run_searches.py",
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


