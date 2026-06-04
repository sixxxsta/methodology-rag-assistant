# QLoRA pipeline (Sprint 5 / T26)

## 1. Накопить успешные исходы

- Зафиксируйте соглашения в фазе Outreach (`outcome=success` в `communication_outcomes`).
- Или: `POST /api/ed/memory/sync` — пересобрать strategy patterns из outcomes.

## 2. Экспорт датасета

```bash
cd services/core
python scripts/export_qlora_dataset.py
```

Или через API (куратор):

`POST /api/ed/memory/qlora/export`

Файл: `services/core/data/qlora/comms_success.jsonl`

## 3. Обучение (опционально, нужен GPU)

```bash
pip install -r requirements-train.txt
python scripts/train_qlora_comms.py --epochs 1 --max-samples 32
```

Адаптер сохранится в `data/qlora/lora_adapter/`.

## Env

```
STRATEGY_MEMORY_ENABLED=true
QLORA_DATASET_DIR=data/qlora
QLORA_BASE_MODEL=IlyaGusev/saiga_llama3_8b
```

## Strategy memory (T27)

- Паттерны из успешных писем подмешиваются в промпт генерации (фаза 3 и follow-up).
- `GET /api/ed/memory/strategies` — список паттернов.
- `POST /api/ed/memory/sync` — синхронизация из outcomes.
