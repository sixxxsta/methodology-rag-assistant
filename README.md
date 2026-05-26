# Методолог — RAG-ассистент по проектной методологии

> Канал куратора: [Telegram](https://t.me/+Xqp0SQjGmVA1ODgy)

## Микросервисная архитектура

```
                    ┌─────────────┐
  Браузер ─────────►│   gateway   │ :8090  (Go — UI + API)
                    └──────┬──────┘
                           │ HTTP
                    ┌──────▼──────┐
                    │     rag     │ :8100  (Python — RAG, сессии, feedback)
                    └──┬──────┬───┘
                       │      │
              ┌────────▼──┐   │ HTTP (LLM_PROVIDER=inference)
              │  qdrant   │   └──────────► ┌────────────┐
              └───────────┘                │ inference  │ :8000 (GPU, опционально)
                                           └────────────┘
```

| Сервис | Роль |
|--------|------|
| **gateway** | Статика, `/api/chat`, `/api/feedback` |
| **rag** | Embeddings, Qdrant, RAG, GigaChat или inference |
| **qdrant** | Векторная БД |
| **inference** | Локальная LLM (профиль `gpu`) |

### Нужен ли брокер сообщений?

**Нет.** Все взаимодействия — синхронный HTTP (запрос → ответ). Чат не требует очередей; ingest выполняется при старте RAG или через `POST /ingest`. RabbitMQ/Kafka добавили бы сложность без выгоды на текущем масштабе.

Брокер понадобится, если появятся: асинхронная переиндексация больших корпусов, фоновые отчёты, event-driven аналитика.

## Структура проекта

```
.
├── .env.example          # единый конфиг
├── docker-compose.yml
├── knowledge/            # база знаний (общий том)
└── services/
    ├── gateway/          # Go
    ├── rag/              # Python
    └── inference/        # Python (GPU)
```

## Сайт

После запуска: **http://localhost:8090** (сервис `gateway`).

## Запуск

```bash
cp .env.example .env
docker compose up --build -d
```

### Переключение LLM (одна строка в `.env`)

| `LLM_PROVIDER` | Когда использовать |
|----------------|-------------------|
| `auto` | По умолчанию: GigaChat если есть `GIGACHAT_CREDENTIALS`, иначе локальная модель |
| `gigachat` | Только API Сбера |
| `inference` | Только локальная Qwen (нужен GPU) |

**Локальная модель:**

```bash
# .env: LLM_PROVIDER=inference
docker compose --profile gpu up --build -d
```

**GigaChat (без GPU):**

```bash
# .env: LLM_PROVIDER=gigachat
# GIGACHAT_CREDENTIALS=<base64 client_id:client_secret>
docker compose up --build -d
```

После смены провайдера: `docker compose up -d --force-recreate rag`

## Конфигурация

Один файл **`.env`** в корне — все сервисы читают его через `env_file: .env` в Compose.

Ключевые переменные:

| Переменная | Описание |
|------------|----------|
| `LLM_PROVIDER` | `gigachat` или `inference` |
| `GIGACHAT_CREDENTIALS` | Base64 `client_id:client_secret` |
| `QDRANT_URL` | В Docker: `http://qdrant:6333` |
| `KNOWLEDGE_DIR` | В Docker: `/knowledge` |

## API (gateway)

- `POST /api/chat` — диалог с RAG
- `POST /api/feedback` — оценка ответа
- `GET /api/health` — статус RAG/Qdrant

Прямой доступ к RAG (отладка): `http://localhost:8100/chat`, `/ingest`, `/health`.

## Локальная разработка

```bash
# Qdrant
docker run -p 6333:6333 qdrant/qdrant:v1.15.1

# RAG (из корня репозитория, подхватит .env)
cd services/rag && pip install -r requirements.txt && uvicorn main:app --port 8100

# Gateway
cd services/gateway && go run . 
```

## База знаний

Подробно: [`knowledge/README.md`](knowledge/README.md).

Кратко: кладите `.md` / `.txt` в `knowledge/` (Agile, Scrum, DevOps, ГОСТ-выжимки, регламенты курса), затем:

```bash
curl -X POST http://localhost:8100/ingest
```
