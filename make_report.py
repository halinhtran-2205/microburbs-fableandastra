"""Build report.html: compute the chart data, then fill the template.

Run after: model.py --holdout 2026-03-01, --holdout 2025-09-01 and --final fableandastra.
"""
import json
import runpy

runpy.run_path("report_data.py", run_name="__main__")
d = json.load(open("report_data.json"))
m = d["holdout"]["2026-03-01"]
page = open("report_template.html", encoding="utf-8").read()
page = (page.replace("/*DATA*/null", json.dumps(d, separators=(",", ":")))
        .replace("__W10__", f"{m['model']['within_10pct']:.4f}")
        .replace("__LIFT__", f"{m['model']['within_10pct'] / m['median']['within_10pct']:.2f}")
        .replace("__MAE__", f"{m['model']['median_abs_err']:.0f}"))
open("report.html", "w", encoding="utf-8").write(page)
print("wrote report.html", len(page) // 1024, "KB")
