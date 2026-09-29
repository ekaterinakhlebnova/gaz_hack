# Слабые сигналы

По запросу вроде «перспективные решения в финтехе» сервис ищет свежие работы в arXiv и OpenAlex,
выделяет технологии-кандидаты и отбирает ТОП-15 слабых сигналов. Методология — в [METHODOLOGY.md](METHODOLOGY.md),
оценка на датасете — в [reports/metrics.md](reports/metrics.md).

## Запуск

Нужны ключ GigaChat и бесплатный ключ OpenAlex (без него дневной лимит заканчивается за пару запросов).

```bash
cp .env.example .env    # вписать ключи
docker compose up --build
```

API: http://localhost:8000/docs

Без Docker:

```bash
pip install -r requirements.txt
python -m src.evaluate                           # метрики на датасете
python -m src.pipeline "технологии в ИИ"         # поиск из консоли
uvicorn api:app                                  # API, SQLite в data/app.db
```

## API

- `POST /search` `{"query": "..."}` — поиск, 1–3 минуты
- `GET /runs` — история запросов
- `GET /runs/{id}` — ТОП-15 и исключённые кандидаты
- `GET /runs/{id}/signals/{n}` — отчёт по сигналу
- `GET /runs/{id}/candidates` — все кандидаты с признаками
- `GET /evaluation` — оценка модели

## Код

- `src/scoring.py` — модель: стадия + тренд
- `src/evaluate.py` — проверка на датасете
- `src/sources.py` — arXiv, OpenAlex, Hacker News
- `src/llm.py` — GigaChat
- `src/pipeline.py` — запрос → ТОП-15
- `src/db.py` — хранение запусков
- `api.py` — FastAPI
