import os
import time
import traceback

import requests

from src import db, pipeline

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
API = f"https://api.telegram.org/bot{TOKEN}"
ALLOWED = {int(x) for x in os.getenv("TELEGRAM_ALLOWED_USERS", "").replace(",", " ").split()}

HELP = """Напишите направление, например: перспективные решения в финтехе.

Я найду до 15 слабых сигналов — зарождающихся технологий — по arXiv, OpenAlex и Hacker News.
Поиск занимает 2–5 минут."""


def send(chat_id, text):
    # лимит Telegram — 4096 символов, режем по пустым строкам между сигналами
    chunk = ""
    for block in text.split("\n\n"):
        if chunk and len(chunk) + len(block) + 2 > 4000:
            _send(chat_id, chunk)
            chunk = ""
        chunk = f"{chunk}\n\n{block}" if chunk else block[:4000]
    _send(chat_id, chunk)


def _send(chat_id, text):
    try:
        requests.post(f"{API}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=60)
    except requests.RequestException as e:
        # только тип ошибки: в её тексте URL с токеном бота
        print(f"не удалось отправить сообщение: {type(e).__name__}")


def format_result(run_id, r):
    if not r["signals"]:
        return f"«{r['query']}»: слабых сигналов не найдено ({len(r['candidates'])} кандидатов, запуск №{run_id})."
    blocks = [f"«{r['query']}»: {len(r['signals'])} слабых сигналов из {len(r['candidates'])} кандидатов, "
              f"запуск №{run_id}"]
    for i, s in enumerate(r["signals"], 1):
        block = (f"{i}. {s['name_ru']} — уверенность {s['confidence']:.0%}\n"
                 f"Работ: {s['total']}, рост за год x{s['growth']} ({s['prev']} → {s['last']})")
        if s.get("description"):
            block += f"\n{s['description']}"
        blocks.append(block)
    return "\n\n".join(blocks)


def handle(msg):
    chat_id, user_id, text = msg["chat"]["id"], msg.get("from", {}).get("id"), msg["text"].strip()
    print(f"{user_id}: {text}")
    if ALLOWED and user_id not in ALLOWED:
        send(chat_id, f"Нет доступа. Ваш id: {user_id}")
        return
    if text.startswith("/"):
        send(chat_id, HELP)
        return
    send(chat_id, f"Ищу слабые сигналы по запросу «{text}», это займёт 2–5 минут.")
    try:
        result = pipeline.run(text)
        run_id = db.save_run(result)
    except Exception:
        # подробности только в консоль: в тексте ошибок бывают URL с ключами
        traceback.print_exc()
        send(chat_id, "Поиск не удался, попробуйте позже.")
        return
    send(chat_id, format_result(run_id, result))


def main():
    if not TOKEN:
        # выходим без ошибки, чтобы Docker не перезапускал бота по кругу
        print("TELEGRAM_BOT_TOKEN не задан, бот не запущен")
        return
    offset = None
    print("бот запущен")
    while True:
        try:
            r = requests.get(f"{API}/getUpdates", params={"offset": offset, "timeout": 50}, timeout=60).json()
        except requests.RequestException as e:
            print(f"Telegram недоступен: {type(e).__name__}")
            time.sleep(5)
            continue
        if not r["ok"]:
            raise SystemExit(f"Telegram: {r['description']} (проверьте TELEGRAM_BOT_TOKEN и что бот не запущен дважды)")
        for u in r["result"]:
            offset = u["update_id"] + 1
            msg = u.get("message")
            if msg and msg.get("text"):
                handle(msg)


if __name__ == "__main__":
    main()
