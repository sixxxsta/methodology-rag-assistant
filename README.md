# Методолог — RAG-ассистент по проектной методологии

> Канал куратора: [Telegram](https://t.me/+Xqp0SQjGmVA1ODgy)

## Архитектура

```
  Браузер ──► web (Next.js) :3000
                  │  proxy /api/*
                  ▼
              gateway (Go API) :8090
                  │
                  ▼
              rag (Python) :8100 ──► qdrant
                  │
                  └──► inference :8000 (GPU, опционально)
```

| Сервис | Порт | Роль |
|--------|------|------|
| **web** | 3000 | React / Next.js UI |
| **gateway** | 8090 | Auth, admin API, прокси к RAG |
| **rag** | 8100 | RAG, embeddings, LLM |
| **qdrant** | 6333 | Векторная БД |
| **inference** | 8000 | Локальная LLM (`--profile gpu`) |

## Сайт

**http://localhost:3000** — чат, вход, админка.

- `/login` — регистрация и вход  
- `/admin` — база знаний (только admin)  

Первый зарегистрированный пользователь — admin. Дополнительно: `ADMIN_EMAILS` в `.env`.

## Запуск

```bash
cp .env.example .env
# JWT_SECRET, RAG_INTERNAL_SECRET — обязательно смените

docker compose up --build -d
# с GPU:
docker compose --profile gpu up --build -d
```

### Локальная разработка фронтенда

```bash
# Терминал 1: backend
docker compose up qdrant rag gateway -d

# Терминал 2: Next.js
cd services/web
npm install
npm run dev
# http://localhost:3000 → API проксируется на :8090
```

## Структура

```
.
├── .env
├── docker-compose.yml
├── knowledge/
└── services/
    ├── web/         # Next.js 15 + React 19 + Tailwind 4
    ├── gateway/     # Go API
    ├── rag/
    └── inference/
```

## LLM

| `LLM_PROVIDER` | Режим |
|----------------|--------|
| `auto` | GigaChat если есть credentials, иначе inference |
| `gigachat` | API Сбера |
| `inference` | Локальная Qwen + `--profile gpu` |

## База знаний

См. [`knowledge/README.md`](knowledge/README.md). Админка: загрузка файлов → «Переиндексировать RAG».

## Переменные

Единый `.env` — см. [`.env.example`](.env.example).
