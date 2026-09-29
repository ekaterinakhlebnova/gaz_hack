STAGES = {1: "Концепция/Исследование", 2: "Прототип/PoC", 3: "Пилот", 4: "Раннее внедрение", 5: "Массовое внедрение"}
TRENDS = {1: "Стабильный", 2: "Растёт", 3: "Растёт быстро"}


def stage_from_text(text):
    # «Прототип → Пилот»: методологи засчитывают целевую стадию
    return max(_stage_part(part) for part in text.lower().split("→"))


def _stage_part(t):
    if "массов" in t or "зрел" in t or "мейнстрим" in t:
        return 5
    if "раннее" in t or "ранние" in t:
        return 4
    if "пилот" in t:
        return 3
    if "прототип" in t or ("исследование" in t and "концепция" not in t):
        return 2
    return 1


def trend_from_text(text):
    t = text.lower()
    if "быстро" in t:
        return 3
    if "растёт" in t or "растет" in t or "ускорен" in t:
        return 2
    return 1


def stage_from_metrics(total_works, novelty):
    if novelty < 0.6 and total_works >= 1000:
        return 5
    if total_works < 300:
        return 1
    if total_works < 3000:
        return 2
    if total_works < 15000:
        return 3
    if total_works < 50000:
        return 4
    return 5


def trend_from_metrics(growth):
    if growth >= 2:
        return 3
    if growth >= 1.2:
        return 2
    return 1


def score(stage, trend, hype=False, noise=False):
    points = stage + trend
    is_signal = stage <= 4 and trend >= 2 and not hype and not noise
    confidence = 0.45 + 0.07 * points
    if hype:
        confidence -= 0.25
    if stage == 5 or trend == 1 or noise:
        confidence = 0.1
    reasons = [f"Стадия: {STAGES[stage]} (+{stage})", f"Тренд: {TRENDS[trend]} (+{trend})"]
    if stage == 5:
        reasons.append("Исключено: зрелая технология")
    if trend == 1:
        reasons.append("Исключено: нет роста интереса")
    if hype:
        reasons.append("Исключено: хайп, обсуждений больше, чем научных работ")
    if noise:
        reasons.append("Исключено: шум, почти нет научных работ")
    return {"points": points, "is_signal": is_signal, "confidence": round(confidence, 2), "reasons": reasons}
