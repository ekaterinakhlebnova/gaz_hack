import pandas as pd
from sklearn.metrics import classification_report

from src.scoring import score, stage_from_text, trend_from_text

pos = pd.read_excel("data/signals.xlsx", header=1).iloc[:, 1:]
neg = pd.read_csv("data/mature.csv")
pos["label"] = 1
neg["label"] = 0
df = pd.concat([pos, neg], ignore_index=True)

df["stage"] = df["Стадия развития"].map(stage_from_text)
df["trend"] = df["Тренд упоминаний"].map(trend_from_text)
res = [score(s, t) for s, t in zip(df["stage"], df["trend"])]
df["pred"] = [int(r["is_signal"]) for r in res]
df["points"] = [r["points"] for r in res]

report = classification_report(df["label"], df["pred"], target_names=["не сигнал", "слабый сигнал"], digits=3)

p = df[df["label"] == 1]
exact = (p["points"] == p["Балл (стадия+тренд)"]).mean()
near = ((p["points"] - p["Балл (стадия+тренд)"]).abs() <= 1).mean()

errors = df[df["label"] != df["pred"]][["Технология (слабый сигнал)", "Стадия развития", "Тренд упоминаний"]]

text = f"""# Оценка модели

Позитивы: {len(pos)} слабых сигналов из датасета, негативы: {len(neg)} зрелых технологий и хайпа (data/mature.csv).

## Классификация «слабый сигнал / нет»
```
{report}
```

## Совпадение балла (стадия + тренд) с разметкой методологов
- точное совпадение: {exact:.1%}
- с точностью ±1: {near:.1%}

## Ошибки
{errors.to_string() if len(errors) else "нет"}
"""
open("reports/metrics.md", "w", encoding="utf-8").write(text)
print(text)
