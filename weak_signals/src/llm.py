import json
import logging
import os

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
)


def ask_json(task, prompt):
    text = client.chat(prompt).choices[0].message.content
    log.info("model=%s task=%s\nPROMPT: %s\nANSWER: %s\n", MODEL, task, prompt[:500], text)
    return json.loads(text[text.find("{"): text.rfind("}") + 1])
