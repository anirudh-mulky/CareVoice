"""Command line: python -m app.modules.demo.cli seed|reset (uses DATABASE_URL)."""

import sys

from app.core.config import get_settings
from app.core.db import Database
from app.core.events import EventBus
from app.modules.demo import service


def main(argv: list[str]) -> int:
    command = argv[1] if len(argv) > 1 else ""
    db = Database(get_settings().database_url)
    bus = EventBus()
    if command == "seed":
        db.create_all()
        inserted = service.seed_if_empty(db, bus)
        print("Seeded demo data." if inserted else "Database already has data; nothing to do.")
        return 0
    if command == "reset":
        counts = service.reset(db, bus)
        print("Demo data reset:", ", ".join(f"{k}={v}" for k, v in counts.items()))
        return 0
    print("usage: python -m app.modules.demo.cli seed|reset", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
