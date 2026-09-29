from fastapi import FastAPI
from pydantic import BaseModel

from src import db, pipeline

app = FastAPI(title="Слабые сигналы", description="Поиск зарождающихся технологий по открытым источникам")


class SearchRequest(BaseModel):
    query: str


def signal_card(s):
    return {
        "technology": s["name_ru"],
        "technology_en": s["name_en"],
        "matched_name": s["matched_name"],
        "confidence": s["confidence"],
        "points": s["points"],
        "predictors": s["predictors"],
    }


def summary(run_id, r):
    return {
        "id": run_id,
        "query": r["query"],
        "created_at": r["created_at"],
        "model": r["model"],
        "search_terms": r["terms"],
        "stats": {
            "sources_processed": len(r["docs"]),
            "candidates": len(r["candidates"]),
            "signals": len(r["signals"]),
            "signals_confidence_over_75": sum(s["confidence"] > 0.75 for s in r["signals"]),
        },
        "signals": [signal_card(s) for s in r["signals"]],
        "excluded": [{
            "technology": c["name_ru"],
            "total_works": c["total"],
            "growth": c["growth"],
            "reasons": [x for x in c["reasons"] if x.startswith("Исключено")],
        } for c in r["excluded"]],
    }


@app.post("/search")
def search(req: SearchRequest):
    """Открытый запрос → ТОП-15 слабых сигналов (1-3 минуты)."""
    result = pipeline.run(req.query)
    return summary(db.save_run(result), result)


@app.get("/runs")
def runs():
    """История запросов."""
    return [{"id": r.id, "query": r.query, "created_at": r.created_at} for r in db.list_runs()]


@app.get("/runs/{run_id}")
def run(run_id: int):
    """Статистика, ТОП-15 и исключённые кандидаты."""
    return summary(run_id, db.get_run(run_id))


@app.get("/runs/{run_id}/signals/{n}")
def insight(run_id: int, n: int):
    """Отчёт по сигналу №n (с 1)."""
    s = db.get_run(run_id)["signals"][n - 1]
    return {
        **signal_card(s),
        "description": s["description"],
        "advantage": s["advantage"],
        "case": s["case"],
        "why": s["why"],
        "analyst_reports": s["reports"],
        "confidence_formula": f"0.45 + 0.07 × балл {s['points']} (стадия {s['stage']} + тренд {s['trend']})",
        "metrics": {k: s[k] for k in ("total", "last", "prev", "growth", "novelty", "hn")},
        "sources": [{
            "title": d["title"],
            "url": d["url"],
            "date": d["date"],
            "type": d["type"],
            "language": d["lang"],
            "trust": d["trust"],
            "trust_reason": d["trust_reason"],
            "summary_ru": d.get("summary_ru"),
            "summary_note": "генеративное резюме GigaChat" if "summary_ru" in d else None,
        } for d in s["sources"]],
    }


@app.get("/runs/{run_id}/candidates")
def candidates(run_id: int):
    """Все кандидаты с признаками."""
    keys = ("name_ru", "name_en", "matched_name", "is_signal", "confidence", "points", "stage", "trend",
            "total", "last", "prev", "growth", "novelty", "hn", "reasons")
    return [{k: c[k] for k in keys} for c in db.get_run(run_id)["candidates"]]


@app.get("/evaluation")
def evaluation():
    """Оценка модели на датасете."""
    return {"report": open("reports/metrics.md", encoding="utf-8").read()}
