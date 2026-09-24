# -*- coding: utf-8 -*-
import json
from pathlib import Path

p = Path(r"D:\hr-policy-assistant\logs\llm.jsonl")
zeilen = [json.loads(z) for z in p.read_text(encoding="utf-8").splitlines() if z.strip()]
qwen = [z for z in zeilen if z.get("modell") == "qwen2.5:14b"]

steuerung = [z for z in qwen if z.get("werkzeugrufe")]
print("qwen-Aufrufe gesamt   ", len(qwen))
print("davon Steuerungsrunden", len(steuerung))
print("Sekunden gesamt       ", round(sum(z["dauer_s"] for z in qwen), 1))
print()
for z in steuerung:
    w = z["werkzeugrufe"][0]
    print(z["zeit"], w["name"], w["argumente"])
