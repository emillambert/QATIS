#!/usr/bin/env python3
"""Run all 6 PMESII web searches, classify with AI, and merge with existing results."""
import os
import subprocess
import csv
from datetime import datetime

categories = ["political", "military", "economic", "social", "information", "infrastructure"]
timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
base_results_dir = f"search_results/pmesii_web_final_{timestamp}"
pmesii_dir = "pmesii_exports/20251020_144507"

print("\n" + "="*80)
print("🚀 QATIS PMESII WEB PIPELINE - FULL RUN")
print("="*80)
print(f"Timestamp: {timestamp}")
print(f"Target: {pmesii_dir}")
print("="*80 + "\n")

stats = {"collected": 0, "classified": 0, "merged": 0, "failed": 0}

for idx, category in enumerate(categories, 1):
    print(f"\n{'='*80}")
    print(f"[{idx}/6] {category.upper()}")
    print(f"{'='*80}\n")
    
    category_dir = f"{base_results_dir}/{category}"
    
    # STEP 1: Collect
    print("🔍 Step 1/4: Collecting web results...")
    result = subprocess.run([
        "python3", "run_searches.py",
        "--queries", f"queries/pmesii/{category}_google.yaml",
        "--output-dir", category_dir,
        "--engines", "web",
        "--top-k", "5",
        "--year-min", "2024",
        "--year-max", "2025",
        "--no-markdown",
        "--concurrency", "1"
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ Collection failed: {result.stderr[:300]}")
        stats["failed"] += 1
        continue
    
    print(f"✓ Collection complete")
    stats["collected"] += 1
    
    # Find actual results directory
    subdirs = [d for d in os.listdir(category_dir) if os.path.isdir(os.path.join(category_dir, d))]
    if not subdirs:
        print(f"⚠️  No results directory found")
        continue
    
    results_dir = os.path.join(category_dir, subdirs[0])
    
    # STEP 2: Export
    print("\n📊 Step 2/4: Exporting to CSV...")
    result = subprocess.run([
        "python3", "export_results_to_csv.py",
        "--results-dir", results_dir,
        "--output", "results_deduped.csv",
        "--dedupe"
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ Export failed")
        stats["failed"] += 1
        continue
    
    csv_file = os.path.join(results_dir, "results_deduped.csv")
    try:
        with open(csv_file, 'r') as f:
            row_count = len(f.readlines()) - 1
    except:
        row_count = 0
    
    print(f"✓ Exported {row_count} items")
    
    if row_count == 0:
        print(f"⚠️  No data, skipping classification")
        continue
    
    # STEP 3: AI Classification
    print("\n🤖 Step 3/4: AI Classification...")
    result = subprocess.run([
        "python3", "analyze_results.py",
        "--results-dir", results_dir,
        "--input", "results_deduped.csv",
        "--model", "gpt-4o-mini",
        "--batch-size", "20",
        "--no-fetch",
        "--content-mode", "min"
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ Classification failed: {result.stderr[:300]}")
        stats["failed"] += 1
        continue
    
    print(f"✓ Classification complete")
    stats["classified"] += 1
    
    # STEP 4: Merge
    print("\n🔄 Step 4/4: Merging with existing...")
    new_csv = os.path.join(results_dir, "results_scored.csv")
    existing_csv = os.path.join(pmesii_dir, category, "results_scored.csv")
    backup_csv = f"{existing_csv}.backup_{timestamp}"
    temp_merged = f"{existing_csv}.temp"
    
    if not os.path.exists(new_csv):
        print(f"⚠️  No classified results")
        continue
    
    # Backup
    subprocess.run(["cp", existing_csv, backup_csv], check=True)
    
    # Merge
    result = subprocess.run([
        "python3", "merge_csv.py",
        "--input-a", existing_csv,
        "--input-b", new_csv,
        "--output", temp_merged,
        "--prefer", "first"
    ], capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ Merge failed: {result.stderr[:300]}")
        stats["failed"] += 1
        continue
    
    # Replace
    subprocess.run(["mv", temp_merged, existing_csv], check=True)
    
    # Update splits
    with open(existing_csv, 'r') as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames
        rows = list(reader)
    
    intel_rows = [r for r in rows if r.get('label') == 'intel']
    non_intel_rows = [r for r in rows if r.get('label') == 'non_intel']
    
    intel_csv = os.path.join(pmesii_dir, category, "results_scored_intel.csv")
    non_intel_csv = os.path.join(pmesii_dir, category, "results_scored_non_intel.csv")
    
    for filename, data in [(intel_csv, intel_rows), (non_intel_csv, non_intel_rows)]:
        with open(filename, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)
    
    print(f"✓ Merged! Intel: {len(intel_rows)}, Non-intel: {len(non_intel_rows)}")
    print(f"💾 Backup: {os.path.basename(backup_csv)}")
    stats["merged"] += 1
    
    print(f"\n✅ {category.upper()} COMPLETE!\n")

# Final summary
print("\n" + "="*80)
print("🎉 PIPELINE COMPLETE!")
print("="*80)
print(f"📊 Collected: {stats['collected']}/6")
print(f"🤖 Classified: {stats['classified']}/6")
print(f"🔄 Merged: {stats['merged']}/6")
print(f"❌ Failed: {stats['failed']}/6")
print("="*80)
print(f"\n💾 Backups saved with suffix: .backup_{timestamp}")
print(f"📁 Updated category files in: {pmesii_dir}/")
print(f"🔍 Raw results stored in: {base_results_dir}/")
print("\n🎯 NEXT STEP: Run merge_pmesii_categories.py to update master files!")
print("="*80 + "\n")

