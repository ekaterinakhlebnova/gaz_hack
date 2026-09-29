import json
import logging
import os
import threading

from gigachat import GigaChat

MODEL = os.getenv("GIGACHAT_MODEL", "GigaChat-2-Max")

os.makedirs("logs", exist_ok=True)
log = logging.getLogger("llm")
log.addHandler(logging.FileHandler("logs/llm.log", encoding="utf-8"))
log.setLevel(logging.INFO)

client = GigaChat(
    credentials=os.environ["GIGACHAT_CREDENTIALS"],
    scope=os.getenv("GIGACHAT_SCOPE", "GIGACHAT_API_PERS"),
    model=MODEL,
    verify_ssl_certs=False,
    timeout=180,
    max_retries=5,
    retry_backoff_factor=2,
)
# на личном тарифе GigaChat разрешён один запрос одновременно, лишние получают 429
slots = threading.Semaphore(int(os.getenv("GIGACHAT_CONCURRENCY", "1")))


def ask_json(task, prompt, attempts=2):
    for _ in range(attempts):
        with slots:
            text = client.chat(prompt).choices[0].message.content
        log.info("model=%s task=%s\nPROMPT: %s\nANSWER: %s\n", MODEL, task, prompt[:500], text)
        try:
            answer = json.loads(text[text.find("{"): text.rfind("}") + 1])
        except json.JSONDecodeError:
            continue
        if isinstance(answer, dict):
            return answer
    raise ValueError(f"GigaChat не вернул JSON-объект ({task}), попыток: {attempts}")
