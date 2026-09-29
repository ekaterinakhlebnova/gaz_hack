import datetime as dt
from concurrent.futures import ThreadPoolExecutor

import requests

from src import llm, sources
from src.scoring import score, stage_from_metrics, trend_from_metrics

TERMS_PROMPT = """Пользователь ищет зарождающиеся технологии по направлению: «{query}».
Составь широкие поисковые фразы для научных баз, покрывающие разные части предметной области
(для «финтеха»: "digital payments", "credit scoring", "banking fraud"), без слов вроде "weak signals", "emerging", "trends".
Верни только JSON:
{{"en": ["3-4 короткие английские фразы по 1-3 слова"], "ru": "одна короткая русская фраза"}}"""

CANDIDATES_PROMPT = """Направление: «{query}».
Ниже заголовки свежих научных работ. Выдели до 40 конкретных технологий или технических подходов,
которые упоминаются в заголовках (не общие области вроде "machine learning" или "cybersecurity").
Бери только технологии, применимые именно в направлении «{query}»: без общих архитектур моделей
(LSTM, трансформеры) и без технологий из соседних отраслей, случайно попавших в заголовки.
Для каждой дай короткое устоявшееся английское название (2-4 слова, как пишут в статьях),
1-2 альтернативных полных английских названия (синонимы, без аббревиатур), русское название
(устоявшийся отраслевой термин, а не дословный перевод) и номера заголовков, где она упоминается. Верни только JSON:
{{"items": [{{"name_en": "...", "aliases": ["..."], "name_ru": "...", "docs": [1, 5]}}]}}

Заголовки:
{titles}"""

REPORT_PROMPT = """Ты технологический аналитик. Технология: «{name}» (направление «{query}»).
Метрики по OpenAlex: всего работ {total}, за последние 12 мес. {last},
за предыдущие 12 мес. {prev}, рост x{growth}, доля работ за 2 года {novelty:.0%}. Модель: {reasons}.

Источники:
{docs}

Опирайся только на источники и метрики, пиши на русском. Не добавляй фактов, которых нет в источниках,
и не расшифровывай аббревиатуры, если расшифровки нет в источниках. Верни только JSON:
{{"description": "что это за технология, 2-3 предложения",
  "advantage": "потенциальное преимущество",
  "case": "конкретный кейс-пример из источников",
  "why": "почему это слабый сигнал, а не зрелый тренд (ссылайся на метрики)",
  "reports": "оценки технологии в аналитических отчётах и обзорах из источников, если есть",
  "summaries": ["краткое русское резюме каждого источника по порядку"]}}"""

TRUST_ORDER = {"высокий": 2, "средний": 1, "низкий": 0}
REPORT_FIELDS = ("description", "advantage", "case", "why", "reports")


def collect_docs(terms):
    calls = []
    for t in terms["en"]:
        calls += [(sources.arxiv_search, t, {"n": 40}), (sources.openalex_search, t, {"n": 15})]
    calls.append((sources.openalex_search, terms["ru"], {"n": 15, "lang": "ru"}))
    docs, failed = [], set()
    for search, q, kwargs in calls:
        if search in failed:
            continue
        try:
            docs += search(q, **kwargs)
        except requests.RequestException as e:
            # недоступный источник (например, 429 от arXiv) пропускаем до конца запуска
            print(f"{search.__name__} недоступен, пропускаю: {e}")
            failed.add(search)
    if not docs:
        raise RuntimeError("ни один источник не ответил")
    return list({d["url"]: d for d in docs}.values())


def measure(cand):
    # берём вариант названия, под которым больше всего работ
    counts = {n: sources.openalex_count(n) for n in [cand["name_en"]] + cand["aliases"]}
    name = max(counts, key=counts.get)
    total = counts[name]
    last = sources.openalex_count(name, from_days=365)
    prev = sources.openalex_count(name, from_days=730, to_days=366)
    hn, hn_docs = sources.hn_search(name)
    growth = round(last / max(prev, 1), 2)
    novelty = (last + prev) / max(total, 1)
    stage = stage_from_metrics(total, novelty)
    trend = trend_from_metrics(growth)
    # рост на единицах работ (1 → 4) — случайность, а не тренд
    model = score(stage, trend, hype=hn > 30 and hn > 3 * last, noise=total < 5 or last < 10)
    predictors = [
        f"Работ в OpenAlex: {total} («{name}») → {model['reasons'][0]}",
        f"Рост за год: x{growth} ({prev} → {last}) → {model['reasons'][1]}",
        f"Новизна: {novelty:.0%} работ за последние 2 года",
        f"Hacker News за год: {hn}",
    ] + model["reasons"][2:]
    return {**cand, "matched_name": name, "total": total, "last": last, "prev": prev, "growth": growth,
            "novelty": novelty, "hn": hn, "hn_docs": hn_docs, "stage": stage, "trend": trend, **model,
            "predictors": predictors}


def write_report(c, query):
    docs_text = "\n".join(f"{i + 1}. [{d['type']}, {d['date']}] {d['title']}. {d['abstract'][:400]}"
                          for i, d in enumerate(c["sources"]))
    try:
        rep = llm.ask_json("report", REPORT_PROMPT.format(
            name=c["matched_name"], query=query, docs=docs_text, reasons="; ".join(c["reasons"]), total=c["total"],
            last=c["last"], prev=c["prev"], growth=c["growth"], novelty=c["novelty"]))
    except ValueError as e:
        # сигнал остаётся в выдаче с метриками, но без текстового отчёта
        print(f"отчёт по «{c['name_ru']}» не получен: {e}")
        rep = {}
    for d, s in zip(c["sources"], rep.get("summaries") or []):
        d["summary_ru"] = s
    c.update({k: rep.get(k, "") for k in REPORT_FIELDS})
    return c


def run(query):
    terms = llm.ask_json("terms", TERMS_PROMPT.format(query=query))
    docs = collect_docs(terms)
    print(f"{query}: фразы {terms}, документов {len(docs)}")

    titles = "\n".join(f"{i + 1}. {d['title']}" for i, d in enumerate(docs[:250]))
    items = llm.ask_json("candidates", CANDIDATES_PROMPT.format(query=query, titles=titles)).get("items", [])
    unique = {}
    for c in items:
        if not isinstance(c.get("name_en"), str) or not c["name_en"].strip():
            continue
        c["aliases"] = [a for a in c.get("aliases") or [] if isinstance(a, str) and a.strip()]
        c["name_ru"] = c.get("name_ru") or c["name_en"]
        unique.setdefault(c["name_en"].lower(), c)
    cands = list(unique.values())
    n_titles = min(len(docs), 250)
    for c in cands:
        valid = [i for i in c.get("docs", []) if isinstance(i, int) and 1 <= i <= n_titles]
        # копии, чтобы резюме одного сигнала не затирало резюме другого
        c["sources"] = [dict(docs[i - 1]) for i in valid[:3]]

    with ThreadPoolExecutor(8) as pool:
        cands = list(pool.map(measure, cands))
    cands.sort(key=lambda c: (c["is_signal"], c["confidence"], c["growth"]), reverse=True)

    signals = [c for c in cands if c["is_signal"]][:15]
    for c in signals:
        c["sources"] += c["hn_docs"]
        c["sources"].sort(key=lambda d: (TRUST_ORDER[d["trust"]], d["date"]), reverse=True)
    print(f"кандидатов {len(cands)}, сигналов {len(signals)}")

    with ThreadPoolExecutor(5) as pool:
        signals = list(pool.map(lambda c: write_report(c, query), signals))

    return {
        "query": query,
        "created_at": dt.datetime.now().isoformat(timespec="seconds"),
        "model": llm.MODEL,
        "terms": terms,
        "candidates": cands,
        "signals": signals,
        "excluded": [c for c in cands if not c["is_signal"]],
        "docs": docs,
    }


if __name__ == "__main__":
    import json
    import sys
    # при перенаправлении вывода Windows берёт cp1251, где нет «→»
    sys.stdout.reconfigure(encoding="utf-8")
    result = run(" ".join(sys.argv[1:]))
    json.dump(result, open("reports/last_run.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for s in result["signals"]:
        print(f"{s['confidence']:.0%}  {s['name_ru']}  |  " + "; ".join(s["predictors"][:2]))
