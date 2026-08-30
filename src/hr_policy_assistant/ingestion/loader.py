import re
import unicodedata
from pathlib import Path
from collections import Counter

import pdfplumber

PROJEKT_WURZEL = Path(__file__).resolve().parents[3]

# parents[0]  ingestion
# parents[1]  hr_policy_assistant
# parents[2]  src
# parents[3]  D:\hr-policy-assistant     ← die Wurzel


def lade_pdf(pfad: Path, ueberspringen: set[int] | None = None) -> list[str]:
    """Extrahiert den Text jeder Seite einer PDF, eine Seite pro Listeneintrag.
       ueberspringen: Seitenzahlen (1-basiert), die nicht gelesen werden.
    """
    ueberspringen = ueberspringen or set() #None oder eingegebener Wert
    seiten = []

    with pdfplumber.open(pfad) as pdf:
        for nummer, page in enumerate(pdf.pages, start=1):
            if nummer in ueberspringen:
                continue
            text = page.extract_text()
            if text:
                seiten.append(text)
    return seiten

def bereinige_text(text: str) -> str:
    """Normalisiert und säubert den rohen PDF-Text."""
    text = unicodedata.normalize("NFC", text)

    # Wingdings-Aufzählungspunkte, Unicode-Kategorie Co, tragen keine Information
    text = "".join(z for z in text if unicodedata.category(z) != "Co")
    return text


def signatur(zeile: str) -> str:
    """ Form einer Zeile, jede Ziffernfolge wird durch '#' ersetzt.
        Damit gelten 'GAV 1 / 26' und 'GAV 2 / 26' als dieselbe Zeile.
        GAV 2 / 26'   →   'GAV # / #
    """
    return re.sub(r"\d+", "#", zeile).strip()


def finde_wiederholte_zeilen(seiten: list[str], schwelle: float = 0.8) -> set[str]:
    """Signaturen von Zeilen, die auf mindestens `schwelle` aller Seiten stehen.

    Kopf- und Fusszeilen wiederholen sich auf fast jeder Seite, Regelungstext
    nicht. Gemessen an den zwei GAV liegen Kopf- und Fusszeilen bei 95 bis 100
    Prozent, die naechsthaeufige Zeile bei 10 Prozent.

    Setzt ein Dokument mit genuegend Seiten voraus. Bei drei Seiten kann ein
    normaler Satz, der auf zweien steht, die Schwelle reissen.
    """
    zaehler = Counter()
    for text in seiten:
        for sig in {signatur(z) for z in text.split("\n") if z.strip()}:
            zaehler[sig] += 1

    # 21 Seiten mal 0.8 ergibt 16.8. Alles ab 17 Seiten gilt als Kopf- oder Fusszeile
    mindestens = schwelle * len(seiten)
    return {sig for sig, anzahl in zaehler.items() if anzahl >= mindestens}


def entferne_wiederholte_zeilen(seiten: list[str], signaturen: set[str]) -> list[str]:
    """Entfernt aus jeder Seite die Zeilen, deren Signatur in `signaturen` steht."""
    bereinigt = []
    for text in seiten:
        behalten = [z for z in text.split("\n") if signatur(z) not in signaturen]
        bereinigt.append("\n".join(behalten))
    return bereinigt


if __name__ == "__main__":
    pfad = PROJEKT_WURZEL / "data" / "raw" / "gav_universitaetsspital_basel.pdf"
    seiten = [bereinige_text(s) for s in lade_pdf(pfad, ueberspringen={2, 3})]
    seiten = entferne_wiederholte_zeilen(seiten, finde_wiederholte_zeilen(seiten))

    text = "\n".join(seiten)
    print("Kündigungsfrist" in text)
    print(text[:1500])

