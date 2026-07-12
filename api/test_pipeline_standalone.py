"""Build-order step 1 check: run the extracted pipeline with no web framework.

Usage: .venv/bin/python test_pipeline_standalone.py ["City, Country"]
"""
import json
import sys
import time

from engine.pipeline import run_full_analysis

city = sys.argv[1] if len(sys.argv) > 1 else "Blois, France"
t0 = time.time()
result = run_full_analysis(city, {"city_size": "Small (< 100k)"},
                           progress=lambda m: print(f"  → {m}"))
dt = time.time() - t0

artifacts = result.pop("artifacts")
print(f"\n=== {city} in {dt:.0f}s ===")
print("metrics_summary:", json.dumps(result["metrics_summary"], indent=2))
print("scalars:", json.dumps({k: v for k, v in result["scalars"].items()
                              if k != "typology_counts"}, indent=2))
print("charts:", sorted(result["charts"].keys()))
print("district_scores rows:", len(result["district_scores"]))
print("warnings:", result["warnings"])
for k, v in artifacts.items():
    print(f"artifact {k}: {type(v).__name__}, rows={len(v) if v is not None else 0}")

# the JSON-facing part must actually serialize
s = json.dumps(result)
print(f"result JSON size: {len(s)/1e6:.1f} MB")
