#!/usr/bin/env python3
"""QLoRA fine-tune on exported comms_success.jsonl (T26).

Requires GPU and optional deps:
  pip install -r requirements-train.txt

Usage:
  python scripts/export_qlora_dataset.py
  python scripts/train_qlora_comms.py --epochs 1 --max-samples 32
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def load_samples(path: Path, max_samples: int | None) -> list[dict]:
    rows: list[dict] = []
    with path.open(encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            rows.append(json.loads(line))
            if max_samples and len(rows) >= max_samples:
                break
    return rows


def format_prompt(rec: dict) -> str:
    inst = rec.get("instruction", "")
    out = rec.get("output", "")
    return (
        f"### Instruction:\n{inst}\n\n"
        f"### Response:\n{out}"
    )


def train(
    *,
    dataset_path: Path,
    output_dir: Path,
    base_model: str,
    epochs: int,
    max_samples: int | None,
) -> dict:
    try:
        import torch
        from datasets import Dataset
        from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
        from transformers import (
            AutoModelForCausalLM,
            AutoTokenizer,
            BitsAndBytesConfig,
            TrainingArguments,
        )
        from trl import SFTTrainer
    except ImportError as exc:
        raise SystemExit(
            "Training deps missing. Install: pip install -r requirements-train.txt"
        ) from exc

    samples = load_samples(dataset_path, max_samples)
    if not samples:
        raise SystemExit(f"No samples in {dataset_path}. Run export_qlora_dataset.py first.")

    texts = [format_prompt(s) for s in samples]
    ds = Dataset.from_dict({"text": texts})

    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
    )
    tokenizer = AutoTokenizer.from_pretrained(base_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        base_model,
        quantization_config=bnb_config,
        device_map="auto",
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)
    lora = LoraConfig(
        r=8,
        lora_alpha=16,
        lora_dropout=0.05,
        bias="none",
        task_type="CAUSAL_LM",
    )
    model = get_peft_model(model, lora)

    output_dir.mkdir(parents=True, exist_ok=True)
    args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=epochs,
        per_device_train_batch_size=1,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        logging_steps=5,
        save_strategy="epoch",
        fp16=torch.cuda.is_available(),
        report_to="none",
    )
    trainer = SFTTrainer(
        model=model,
        train_dataset=ds,
        args=args,
        processing_class=tokenizer,
        dataset_text_field="text",
    )
    trainer.train()
    model.save_pretrained(output_dir)
    tokenizer.save_pretrained(output_dir)
    return {
        "status": "trained",
        "samples": len(samples),
        "output_dir": str(output_dir),
        "base_model": base_model,
    }


def main() -> None:
    from app.config import get_settings

    settings = get_settings()
    parser = argparse.ArgumentParser(description="QLoRA train on comms outcomes")
    parser.add_argument("--dataset", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--base-model", default=settings.qlora_base_model)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--max-samples", type=int, default=None)
    args = parser.parse_args()

    data_dir = Path(settings.qlora_dataset_dir)
    if not data_dir.is_absolute():
        data_dir = ROOT / data_dir
    dataset = args.dataset or (data_dir / "comms_success.jsonl")
    output = args.output or (data_dir / "lora_adapter")

    result = train(
        dataset_path=dataset,
        output_dir=output,
        base_model=args.base_model,
        epochs=args.epochs,
        max_samples=args.max_samples,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
