"""Build a self-contained bilingual explorer from the saved analysis results."""

import csv
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "data" / "results"


def read_rows(filename):
    """Read a result table without changing the analysis values."""
    path = RESULTS / filename
    if not path.exists():
        raise FileNotFoundError(f"Run src/analyze.py first: missing {path}")
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def build_explorer():
    """Embed the real result tables in a portable HTML document."""
    tables = {
        "monthly": "monthly_metrics.csv",
        "distance": "distance_metrics.csv",
        "hourly": "hourly_metrics.csv",
        "airport": "airport_metrics.csv",
        "snapshot": "company_snapshot.csv",
        "borough": "borough_metrics.csv",
        "zones": "zone_metrics.csv",
        "congestion": "congestion_comparison.csv",
        "congestionTrends": "congestion_trends.csv",
    }
    payload = {name: read_rows(filename) for name, filename in tables.items()}
    payload["keyNumbers"] = json.loads((RESULTS / "key_numbers.json").read_text())
    manifest = ROOT / "data" / "processed" / "manifest.json"
    payload["manifest"] = json.loads(manifest.read_text()) if manifest.exists() else {}
    # Escape HTML delimiters so embedded text cannot end the JSON script element.
    embedded = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    embedded = embedded.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")
    template = (ROOT / "docs" / "explorer_template.html").read_text(encoding="utf-8")
    if template.count("__RESULTS_JSON__") != 1:
        raise ValueError("The explorer template must have exactly one data placeholder.")
    output = ROOT / "docs" / "index.html"
    output.write_text(template.replace("__RESULTS_JSON__", embedded), encoding="utf-8")
    print(f"Built {output.relative_to(ROOT)} from {len(payload['monthly'])} monthly result rows.")


if __name__ == "__main__":
    build_explorer()
