# Методолог — RAG-ассистент по проектной методологии

> Канал куратора: [Telegram](https://t.me/+Xqp0SQjGmVA1ODgy)

## Архитектура

```
  Браузер ──► web (Next.js) :3000
                  │  proxy /api/*
                  ▼
              gateway (Go API) :8090
                  ├──► rag :8100 ──► qdrant
                  ├──► core :8200 ──► postgres
                  └──► inference :8000 (GPU, опционально)
```

| Сервис | Порт | Роль |
|--------|------|------|
| **web** | 3000 | React / Next.js UI |
| **gateway** | 8090 | Auth, admin API, прокси к RAG и Core |
| **core** | 8200 | EdAgent: фазы, эскалации, audit log |
| **postgres** | 5432 | Реляционные данные EdAgent |
| **redis** | 6379 | Очереди (Celery, следующие спринты) |
| **rag** | 8100 | RAG, embeddings, LLM |
| **qdrant** | 6333 | Векторная БД |
| **inference** | 8000 | Локальная LLM (`--profile gpu`) |

## Сайт

**http://localhost:3000** — чат, вход, админка.

- `/login` — регистрация и вход  
- `/dashboard` — EdAgent: 5 фаз цикла партнёрства  
- `/dashboard/competencies` — сбор вакансий HH и матрица компетенций (Фаза 1)  
- `/dashboard/companies` — поиск компаний, скоринг, шорт-лист (Фаза 2)  
- `/dashboard/communications` — письма, FAQ, план касаний (Фаза 3)  
- `/dashboard/outreach` — отправка, ответы, follow-up, соглашения (Фаза 4)  
- `/dashboard/projects` — генерация ТЗ, утверждение, публикация в каталог (Фаза 5)  
- `/catalog` — каталог опубликованных проектов для студентов  
- `/admin` — база знаний (только admin)  

Админка доступна только пользователю с email из `ADMIN_EMAIL` в `.env`. Регистрация открыта только для **учеников**; кураторов создаёт модератор в `/admin`.

## Запуск

```bash
cp .env.example .env
# JWT_SECRET, RAG_INTERNAL_SECRET — обязательно смените

docker compose up --build -d

# Чат «Методолог» нужен сервис inference (локальная LLM):
docker compose --profile gpu up -d inference
# Дождитесь готовности: docker compose logs -f inference
# (первый запуск — загрузка модели, до ~20 мин)
```

### Локальная разработка фронтенда

```bash
# Терминал 1: backend
docker compose up postgres core qdrant rag gateway -d

# Терминал 2: Next.js
cd services/web
npm install
npm run dev
# http://localhost:3000 → API проксируется на :8090
# Важно: gateway должен быть запущен (см. терминал 1)
```

Если в Docker-логах `web` пишет `ECONNREFUSED 127.0.0.1:8090` — пересоберите образ (URL API зашивается при `next build`):

```bash
docker compose build --no-cache web
docker compose up -d web gateway rag qdrant
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
    ├── core/        # EdAgent workflow (FastAPI)
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
