from hr_policy_assistant.gateway.llm import frage_modell

a = frage_modell(
    system="Antworte kurz und auf Deutsch.",
    nutzer="Was ist die Hauptstadt der Schweiz? Ein Satz.",
)

print(a.text)
print(f"{a.tokens_prompt} Tokens rein, {a.tokens_antwort} raus, {a.dauer_s} s, {a.modell}")