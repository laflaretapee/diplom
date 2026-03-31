from __future__ import annotations

import argparse
import json
from pathlib import Path

from backend.app.main import app


def main() -> None:
    parser = argparse.ArgumentParser(description="Export OpenAPI schema to JSON.")
    parser.add_argument(
        "--output",
        default="openapi.json",
        help="Path to write the exported schema.",
    )
    args = parser.parse_args()

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(app.openapi(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"OpenAPI exported to {output_path}")


if __name__ == "__main__":
    main()
