#!/usr/bin/env python3
"""Export successful communication outcomes to JSONL for QLoRA fine-tuning (T26).

Usage (from services/core):
  python scripts/export_qlora_dataset.py
  python scripts/train_qlora_comms.py --epochs 1
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from app.database import SessionLocal
from app.memory.qlora_export import export_training_jsonl


def main() -> None:
    db = SessionLocal()
    try:
        meta = export_training_jsonl(db)
        print(json_dumps(meta))
    finally:
        db.close()


def json_dumps(obj: object) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
