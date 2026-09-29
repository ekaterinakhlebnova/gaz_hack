import datetime as dt
import os
import time

import feedparser
import requests_cache
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

session = requests_cache.CachedSession("data/http_cache", expire_after=dt.timedelta(days=1))
retry = HTTPAdapter(max_retries=Retry(total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504]))
session.mount("http://", retry)
session.mount("https://", retry)

OPENALEX = "https://api.openalex.org/works"
OPENALEX_PARAMS = {"mailto": os.getenv("OPENALEX_MAILTO"), "api_key": os.getenv("OPENALEX_API_KEY")}


def days_ago(n):
    return (dt.date.today() - dt.timedelta(days=n)).isoformat()


def arxiv_search(query, n=40):
    # поиск по отдельным словам со стеммингом даёт много нерелевантного, поэтому он только запасной
    docs = _arxiv_query(f'all:"{query}"', n)
    if len(docs) < n // 2 and " " in query:
        words = query.lower().split()
        seen = {d["url"] for d in docs}
        for d in _arxiv_query(" AND ".join(f"all:{w}" for w in words), n):
            text = (d["title"] + " " + d["abstract"]).lower()
            if d["url"] not in seen and all(w in text for w in words) and len(docs) < n:
                docs.append(d)
    return docs


def _arxiv_query(search_query, n):
    params = {"search_query": search_query, "sortBy": "submittedDate", "max_results": n}
    r = session.get("https://export.arxiv.org/api/query", params=params, timeout=60)
    if not r.from_cache:
        time.sleep(3)  # правила arXiv API: не чаще раза в 3 секунды
    feed = feedparser.parse(r.text)
    return [{
        "title": " ".join(e.title.split()),
        "url": e.link,
        "date": e.published[:10],
        "abstract": " ".join(e.summary.split())[:600],
        "type": "Препринт arXiv",
        "lang": "en",
        "trust": "средний",
        "trust_reason": "препринт без рецензирования",
    } for e in feed.entries]


def _abstract(inverted):
    # OpenAlex отдаёт аннотацию как {слово: [позиции]}
    words = sorted((pos, w) for w, positions in (inverted or {}).items() for pos in positions)
    return " ".join(w for _, w in words)[:600]


def _openalex_doc(w):
    source = (w["primary_location"] or {}).get("source") or {}
    reviewed = source.get("type") in ("journal", "conference")
    return {
        "title": w["title"],
        "url": w["doi"] or w["id"],
        "date": w["publication_date"],
        "abstract": _abstract(w["abstract_inverted_index"]),
        "type": source.get("display_name", "OpenAlex"),
        "lang": w["language"],
        "trust": "высокий" if reviewed else "средний",
        "trust_reason": "рецензируемый журнал" if reviewed else "препринт без рецензирования",
    }


def openalex_search(query, n=20, lang=None, since_days=730):
    flt = f"title_and_abstract.search:{query},from_publication_date:{days_ago(since_days)}"
    if lang:
        flt += f",language:{lang}"
    params = {**OPENALEX_PARAMS, "filter": flt, "per_page": n, "sort": "relevance_score:desc"}
    return [_openalex_doc(w) for w in session.get(OPENALEX, params=params, timeout=60).json()["results"]]


def openalex_count(phrase, from_days=None, to_days=None):
    flt = f'title_and_abstract.search:"{phrase.replace(",", " ")}"'
    if from_days:
        flt += f",from_publication_date:{days_ago(from_days)}"
    if to_days:
        flt += f",to_publication_date:{days_ago(to_days)}"
    params = {**OPENALEX_PARAMS, "filter": flt, "per_page": 1}
    return session.get(OPENALEX, params=params, timeout=60).json()["meta"]["count"]


def hn_search(phrase, since_days=365):
    # начало дня, а не текущая секунда, иначе не работает кэш
    day = dt.date.today() - dt.timedelta(days=since_days)
    ts = int(dt.datetime.combine(day, dt.time()).timestamp())
    params = {"query": f'"{phrase}"', "tags": "story", "numericFilters": f"created_at_i>{ts}", "hitsPerPage": 1}
    r = session.get("https://hn.algolia.com/api/v1/search", params=params, timeout=60).json()
    top = [{
        "title": h["title"],
        "url": h["url"] or f"https://news.ycombinator.com/item?id={h['objectID']}",
        "date": h["created_at"][:10],
        "abstract": "",
        "type": "Hacker News",
        "lang": "en",
        "trust": "низкий",
        "trust_reason": "агрегатор, только индикатор интереса",
    } for h in r["hits"]]
    return r["nbHits"], top
