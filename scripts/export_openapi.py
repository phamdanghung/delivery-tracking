"""Write the current milestone contract without modifying supplied/M1 baselines."""

import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "apps/api"))
from app.main import app  # noqa: E402

destination = root / "openapi/m3.openapi.json"
destination.write_text(
    json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print("Updated versioned M3 contract:", destination.name)
