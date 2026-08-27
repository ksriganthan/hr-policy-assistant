# Eval-Set

Ab Woche 2: 10 Fragen. Ab Woche 3: 20–30, inklusive Fangfragen.

**Kategorien, die drin sein müssen:**
- *beantwortbar* – Antwort steht wörtlich in genau einem Dokument
- *mehrteilig* – Antwort erfordert zwei Chunks aus verschiedenen Abschnitten
- *nicht beantwortbar* – die Antwort steht in keinem Dokument. Erwartetes Verhalten: das System sagt es, statt zu raten.
- *veraltet* – die Antwort steht in einer alten Fassung. Erwartetes Verhalten: aktuelle Fassung zitieren oder auf die Version hinweisen.
- *ausserhalb Geltungsbereich* – Frage betrifft Bundespersonal, Dokument gilt für Kanton BS (oder umgekehrt)

Format (Vorschlag, entscheide selbst): `eval_set.jsonl` mit
`{"id", "frage", "referenzantwort", "erwartete_quellen": [...], "kategorie"}`
