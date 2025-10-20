#!/bin/bash
# Run web searches for all 6 PMESII categories, classify with AI, and merge with existing results

set -e  # Exit on error

PMESII_DIR="pmesii_exports/20251020_144507"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
NEW_RESULTS_DIR="search_results/pmesii_web_${TIMESTAMP}"

echo "═══════════════════════════════════════════════════════════════"
echo "🚀 QATIS PMESII Web Search Pipeline"
echo "═══════════════════════════════════════════════════════════════"
echo ""

# Array of categories
categories=("political" "military" "economic" "social" "information" "infrastructure")

# Step 1: Run web searches for each category
echo "📡 Step 1/4: Running web searches for all categories..."
echo "─────────────────────────────────────────────────────────────"
mkdir -p "${NEW_RESULTS_DIR}"

for category in "${categories[@]}"; do
    echo ""
    echo "🔍 Searching: ${category}"
    python3 run_searches.py \
        --queries "queries/pmesii/${category}_google.yaml" \
        --output-dir "${NEW_RESULTS_DIR}/${category}" \
        --engines web \
        --top-k 5 \
        --year-min 2024 \
        --year-max 2025 \
        --no-markdown \
        --concurrency 1
    
    echo "✓ ${category} search complete"
done

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "📊 Step 2/4: Exporting results to CSV..."
echo "─────────────────────────────────────────────────────────────"

for category in "${categories[@]}"; do
    echo "📄 Exporting ${category}..."
    python3 export_results_to_csv.py \
        --results-dir "${NEW_RESULTS_DIR}/${category}" \
        --output results_deduped.csv \
        --dedupe
    
    # Check if we got any results
    row_count=$(tail -n +2 "${NEW_RESULTS_DIR}/${category}/results_deduped.csv" 2>/dev/null | wc -l | tr -d ' ')
    echo "  → ${row_count} unique items"
done

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "🤖 Step 3/4: Running AI classification..."
echo "─────────────────────────────────────────────────────────────"

for category in "${categories[@]}"; do
    csv_file="${NEW_RESULTS_DIR}/${category}/results_deduped.csv"
    
    # Skip if no results
    if [ ! -f "$csv_file" ]; then
        echo "⚠️  Skipping ${category}: no results file"
        continue
    fi
    
    row_count=$(tail -n +2 "$csv_file" 2>/dev/null | wc -l | tr -d ' ')
    if [ "$row_count" -eq "0" ]; then
        echo "⚠️  Skipping ${category}: no data rows"
        continue
    fi
    
    echo ""
    echo "🧠 Analyzing ${category} (${row_count} items)..."
    python3 analyze_results.py \
        --results-dir "${NEW_RESULTS_DIR}/${category}" \
        --input results_deduped.csv \
        --model gpt-4o-mini \
        --batch-size 20 \
        --no-fetch \
        --content-mode min
    
    echo "✓ ${category} classification complete"
done

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "🔄 Step 4/4: Merging with existing results..."
echo "─────────────────────────────────────────────────────────────"

for category in "${categories[@]}"; do
    new_csv="${NEW_RESULTS_DIR}/${category}/results_scored.csv"
    existing_csv="${PMESII_DIR}/${category}/results_scored.csv"
    merged_csv="${PMESII_DIR}/${category}/results_scored_merged_${TIMESTAMP}.csv"
    
    # Skip if new results don't exist
    if [ ! -f "$new_csv" ]; then
        echo "⚠️  Skipping ${category}: no new classified results"
        continue
    fi
    
    echo ""
    echo "🔀 Merging ${category}..."
    python3 merge_csv.py \
        --input-a "$existing_csv" \
        --input-b "$new_csv" \
        --output "$merged_csv" \
        --prefer first
    
    # Backup old file and replace
    cp "$existing_csv" "${existing_csv}.backup_${TIMESTAMP}"
    mv "$merged_csv" "$existing_csv"
    
    echo "✓ ${category} merged and updated"
    
    # Also update intel/non-intel splits
    python3 << PYEOF
import csv
import pathlib

base_dir = pathlib.Path("${PMESII_DIR}/${category}")
scored_csv = base_dir / "results_scored.csv"

with open(scored_csv, 'r') as f:
    rows = list(csv.DictReader(f))
    fieldnames = f.name and list(csv.DictReader(f).fieldnames or [])

# Re-read to get fieldnames
with open(scored_csv, 'r') as f:
    reader = csv.DictReader(f)
    fieldnames = reader.fieldnames

intel_rows = [r for r in rows if r.get('label') == 'intel']
non_intel_rows = [r for r in rows if r.get('label') == 'non_intel']

# Write splits
for filename, data in [('results_scored_intel.csv', intel_rows), ('results_scored_non_intel.csv', non_intel_rows)]:
    with open(base_dir / filename, 'w', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(data)

print(f"  → Intel: {len(intel_rows)}, Non-intel: {len(non_intel_rows)}")
PYEOF
    
done

echo ""
echo "═══════════════════════════════════════════════════════════════"
echo "✅ PIPELINE COMPLETE!"
echo "═══════════════════════════════════════════════════════════════"
echo ""
echo "📁 New web results stored in: ${NEW_RESULTS_DIR}/"
echo "🔄 Updated files in: ${PMESII_DIR}/"
echo "💾 Backups created with suffix: .backup_${TIMESTAMP}"
echo ""
echo "🎯 Next step: Run merge_pmesii_categories.py to update master files"
echo "═══════════════════════════════════════════════════════════════"

