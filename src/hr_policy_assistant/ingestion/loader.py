from pathlib import Path
import unicodedata

import pdfplumber
PROJEKT_WURZEL = Path(__file__).resolve().parents[3]

# parents[0]  ingestion
# parents[1]  hr_policy_assistant
# parents[2]  src
# parents[3]  D:\hr-policy-assistant     ← die Wurzel

import re
TOC_ZEILE = re.compile(r"^\d+(\.\d+)*\.?\s+.+\s+\d+\s*$")
SEITENMARKE = re.compile(r"^.*Seite\s+\d+\s+von\s+\d+\s*$")

# | ^ | Zeilenanfang |
# | \d+ | eine oder mehrere Ziffern — die 2 in 2.3.3 |
# | (\.\d+)* | beliebig oft «Punkt plus Ziffern» — die .3.3 |
# | \.? | ein optionaler Punkt am Ende der Nummer — 1. |
# | \s+ | Leerzeichen |
# | .+ | der Titel, egal was |
# | \s+\d+ | Leerzeichen und dann Ziffern — die Seitenzahl |
# | \s*$ | Zeilenende, eventuell mit Leerzeichen davor |

def lade_pdf(pfad: Path, ueberspringen: set[int] | None = None) -> str:
    """Extrahiert den Text aller Seiten einer PDF als einen String.

    ueberspringen: Seitenzahlen (1-basiert), die nicht gelesen werden.
    """
    ueberspringen = ueberspringen or set()
    seiten = []

    with pdfplumber.open(pfad) as pdf:
        for nummer, page in enumerate(pdf.pages, start=1):
            if nummer in ueberspringen:
                continue
            text = page.extract_text()
            if text:
                seiten.append(text)

    return "\n".join(seiten)

def bereinige_text(text: str) -> str:
    """Normalisiert und säubert den rohen PDF-Text."""
    text = unicodedata.normalize("NFC", text)

    """Entfernt die Wingdings-Aufzählungspunkte - Unsichtbare, unbedeutende Symbolzeichen im Text"""
    text = "".join(z for z in text if unicodedata.category(z) != "Co")
    return text

def entferne_toc(text: str) -> str:
    """Wirft Inhaltsverzeichnis-Zeilen weg (Nummer + Titel + Seitenzahl)."""
    zeilen = text.split("\n")
    behalten = [z for z in zeilen if not TOC_ZEILE.match(z)]
    return "\n".join(behalten)

def entferne_seitenmarken(text: str) -> str:
    """Wirft die auf jeder Seite wiederholte Seitenmarke weg."""
    zeilen = text.split("\n")
    behalten = [z for z in zeilen if not SEITENMARKE.match(z)]
    return "\n".join(behalten)

if __name__ == "__main__":
    pfad = PROJEKT_WURZEL / "data" / "raw" / "gav_universitaetsspital_basel.pdf"
    text = lade_pdf(pfad, ueberspringen={2, 3})
    text = bereinige_text(text)
    text = entferne_toc(text)
    text = entferne_seitenmarken(text)

    print("Kündigungsfrist" in text)
    print(text[:1500])


    """
    Einen Loader mit Seitenauswahl, Unicode-Normalisierung, Entfernung der Symbolzeichen, einen TOC-Filter und einen Seitenmarken-Filter.
    Aus einem PDF, in dem Python das Wort «Kündigungsfrist» nicht finden konnte, ist sauberer Text geworden, in dem die Struktur erhalten ist.
    Wichtiger als der Code: Du hast jeden Schritt an einer Zahl geprüft — 106 entfernte Zeilen, das verschwundene 1. Allgemeines, das True nach der Normalisierung.
    Und du hast selbst gesehen, warum ein Seitenschnitt zu grob ist, statt es mir zu glauben.
       """
