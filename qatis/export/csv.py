import subprocess
import pathlib


def export_results(results_dir: pathlib.Path, output: str = "results_deduped.csv", dedupe: bool = True):
    args = [
        "python", "export_results_to_csv.py",
        "--results-dir", str(results_dir),
        "--output", output,
    ]
    if dedupe:
        args.append("--dedupe")
    subprocess.run(args, check=True)



