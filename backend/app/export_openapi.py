"""Write the API schema for the frontend's generated types: python -m app.export_openapi <path>."""

import json
import sys
from pathlib import Path

from app.main import create_app


def main(argv: list[str]) -> int:
    target = Path(argv[1]) if len(argv) > 1 else Path("openapi.json")
    schema = create_app().openapi()
    text = json.dumps(schema, indent=2, ensure_ascii=False, sort_keys=True)
    target.write_text(text + "\n", "utf-8")
    print(f"wrote {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
