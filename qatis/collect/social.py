import subprocess
import pathlib
from typing import List


def collect_social(
    queries_social: pathlib.Path,
    output_dir: pathlib.Path,
    year_min: int,
    year_max: int,
    top_k: int,
    platforms: List[str],
    telegram: bool = False,
    tele_api_id: int | None = None,
    tele_api_hash: str | None = None,
):
    args = [
        "python", "run_social_searches.py",
        "--queries", str(queries_social),
        "--output-dir", str(output_dir),
        "--year-min", str(year_min),
        "--year-max", str(year_max),
        "--top-k", str(top_k),
        "--platforms", *platforms,
    ]
    if telegram:
        args.append("--telegram")
        if tele_api_id and tele_api_hash:
            args += ["--tele-api-id", str(tele_api_id), "--tele-api-hash", tele_api_hash]
    subprocess.run(args, check=True)



