# PMESII Query Packs (Google/Scholar + Social)

These query files target Moldova (2024–2025) for PMESII analysis focused on Russian external influence during EU accession.

## Files

- political_google.yaml, political_social.yaml
- military_google.yaml, military_social.yaml
- economic_google.yaml, economic_social.yaml
- social_google.yaml, social_social.yaml
- information_google.yaml, information_social.yaml
- infrastructure_google.yaml, infrastructure_social.yaml

## Usage

Web/Scholar collection (per element):
```bash
python run_searches.py \
  --queries queries/pmesii/<element>_google.yaml \
  --engines web scholar \
  --output-dir search_results \
  --year-min 2024 --year-max 2025
```

Social collection (per element):
```bash
python run_social_searches.py \
  --queries queries/pmesii/<element>_social.yaml \
  --output-dir search_results_social
```

Tips:
- Add --include-ru and/or --include-ro to broaden language coverage.
- Review a small sample first (e.g., --top-k 2) before full runs.
- Deduplicate and merge later with existing CSV tools.
