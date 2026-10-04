"""Write the M1 contract from source without modifying the supplied baseline."""

import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / "apps/api"))
from app.main import app  # noqa: E402

destination = root / "openapi/m1.openapi.json"
destination.write_text(
    json.dumps(app.openapi(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
)
print("Updated versioned M1 contract:", destination.name)
