import json
import os

from sqlalchemy import Column, Integer, MetaData, String, Table, Text, create_engine, select

engine = create_engine(os.getenv("DATABASE_URL", "sqlite:///data/app.db"))
meta = MetaData()
runs = Table(
    "runs", meta,
    Column("id", Integer, primary_key=True),
    Column("query", String(500)),
    Column("created_at", String(30)),
    Column("result", Text),
)
meta.create_all(engine)


def save_run(result):
    with engine.begin() as con:
        return con.execute(runs.insert().values(
            query=result["query"], created_at=result["created_at"],
            result=json.dumps(result, ensure_ascii=False))).inserted_primary_key[0]


def list_runs():
    with engine.connect() as con:
        return con.execute(select(runs.c.id, runs.c.query, runs.c.created_at).order_by(runs.c.id.desc())).all()


def get_run(run_id):
    with engine.connect() as con:
        result = con.execute(select(runs.c.result).where(runs.c.id == run_id)).scalar()
    return json.loads(result) if result else None
