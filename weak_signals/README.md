# Слабые сигналы

По запросу вроде «перспективные решения в финтехе» сервис ищет свежие работы в arXiv и OpenAlex,
выделяет технологии-кандидаты и отбирает ТОП-15 слабых сигналов. Методология — в [METHODOLOGY.md](METHODOLOGY.md),
оценка на датасете — в [reports/metrics.md](reports/metrics.md).

## Запуск

Для поиска нужны ключ GigaChat и бесплатный ключ OpenAlex. Оценка на датасете работает без ключей.

```bash
cp .env.example .env    # вписать ключи (в cmd: copy .env.example .env)
```

| Переменная | Что это |
|---|---|
| `GIGACHAT_CREDENTIALS` | ключ авторизации (Authorization key) из кабинета GigaChat API на developers.sber.ru |
| `GIGACHAT_SCOPE` | `GIGACHAT_API_PERS` для физлиц, `GIGACHAT_API_B2B` / `GIGACHAT_API_CORP` для юрлиц |
| `GIGACHAT_MODEL` | модель, по умолчанию `GigaChat-2-Max` |
| `GIGACHAT_CONCURRENCY` | сколько запросов к GigaChat одновременно; на личном тарифе 1, иначе API отвечает 429 |
| `OPENALEX_API_KEY` | бесплатный ключ: https://openalex.org/settings/api (без него дневной лимит заканчивается за пару запросов) |
| `OPENALEX_MAILTO` | ваша почта |
| `TELEGRAM_BOT_TOKEN` | токен Telegram-бота от @BotFather; пусто — бот не запускается |
| `TELEGRAM_ALLOWED_USERS` | id пользователей Telegram через запятую, кому доступен бот; пусто — всем |

Docker:

```bash
docker compose up --build
```

API: http://localhost:8000/docs

Без Docker нужен Python 3.11+. Все команды — из корня проекта (папки с этим README): пути к `.env`, `data/`, `reports/` и `logs/` относительные.

```bash
python -m venv .venv
.venv\Scripts\activate                           # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python -m src.evaluate                           # метрики на датасете → reports/metrics.md
python -m src.pipeline "технологии в ИИ"         # поиск из консоли → reports/last_run.json
uvicorn api:app                                  # API, SQLite в data/app.db
python bot.py                                    # Telegram-бот
```

Запросы и ответы GigaChat пишутся в `logs/llm.log`, ответы arXiv/OpenAlex/Hacker News кэшируются на сутки в `data/http_cache.sqlite`.

## API

- `POST /search` `{"query": "..."}` — поиск, 2–5 минут (отчёты GigaChat пишутся по одному)
- `GET /runs` — история запросов
- `GET /runs/{id}` — ТОП-15 и исключённые кандидаты
- `GET /runs/{id}/signals/{n}` — отчёт по сигналу
- `GET /runs/{id}/candidates` — все кандидаты с признаками
- `GET /evaluation` — оценка модели

## Telegram-бот

1. В Telegram написать @BotFather команду `/newbot`, придумать имя — он пришлёт токен.
2. Вписать токен в `TELEGRAM_BOT_TOKEN` в `.env`.
3. Запустить `python bot.py` (в Docker бот стартует сам вместе с API).

Боту пишут направление текстом («перспективные решения в финтехе»), через 2–5 минут он присылает ТОП слабых
сигналов. Запуски из бота сохраняются в ту же базу, номер запуска в ответе открывается в API: `GET /runs/{id}`.
Поиск тратит токены GigaChat, поэтому лучше ограничить доступ через `TELEGRAM_ALLOWED_USERS`: бот отвечает
чужим пользователям «Нет доступа» и показывает их id.

## Код

- `src/scoring.py` — модель: стадия + тренд
- `src/evaluate.py` — проверка на датасете
- `src/sources.py` — arXiv, OpenAlex, Hacker News
- `src/llm.py` — GigaChat
- `src/pipeline.py` — запрос → ТОП-15
- `src/db.py` — хранение запусков
- `api.py` — FastAPI
- `bot.py` — Telegram-бот
