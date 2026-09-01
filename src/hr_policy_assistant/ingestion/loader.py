import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import pdfplumber

PROJEKT_WURZEL = Path(__file__).resolve().parents[3]

# parents[0]  ingestion
# parents[1]  hr_policy_assistant
# parents[2]  src
# parents[3]  D:\hr-policy-assistant     ← die Wurzel

# Ueberschrift: mehrstufige Nummer mit optionalem Schlusspunkt (2.5.9 / 9.1.)
# ODER einstufige mit Punkt (1.), danach Leerzeichen und ein Nicht-Ziffer-Zeichen.
UEBERSCHRIFT = re.compile(r"^(\d+(\.\d+)+\.?|\d+\.)\s+\D")

# Notbremse gegen Satzzeilen. Die laengste echte Ueberschrift hat 81 Zeichen.
MAX_UEBERSCHRIFT = 100

# Schwelle: Ab wie viel mal vorkommen, soll die Signatur entfernt werden
SCHWELLE = 0.8


@dataclass
class Seite:
    """Eine Seite mit ihrer echten Seitenzahl."""

    nummer: int
    text: str


@dataclass
class Abschnitt:
    """Ein Abschnitt des Dokuments, erkannt an seiner Gliederungsnummer."""

    nummer: str
    titel: str
    text: str
    seite: int = 0
    pfad: str = ""


def lade_pdf(pfad: Path, ueberspringen: set[int] | None = None) -> list[Seite]:
    """Extrahiert den Text jeder Seite einer PDF, eine Seite pro Listeneintrag.
    ueberspringen: Seitenzahlen (1-basiert), die nicht gelesen werden.
    """
    if ueberspringen is None:  # None oder eingegebener Wert
        ueberspringen = set()
    seiten = []

    with pdfplumber.open(pfad) as pdf:
        for nummer, page in enumerate(pdf.pages, start=1):
            if nummer in ueberspringen:
                continue
            text = page.extract_text()
            if text:  # Wenn PDF ein Scann ist, würde das hier nie erfüllt werden
                seiten.append(Seite(nummer, text))
    return seiten


def bereinige_text(text: str) -> str:
    """Normalisiert und säubert den rohen PDF-Text."""
    # Unicode kennt zwei Schreibweisen fuer denselben Buchstaben. Ein «ü» ist
    # entweder ein fertiges Zeichen oder ein «u» plus eine Anweisung, zwei
    # Punkte darueberzusetzen. Beide sehen identisch aus, sind fuer Python aber
    # verschiedene Zeichenketten, und «für» == «für» ergibt False.
    # NFC schreibt alles auf die fertige Form um.
    #
    # Am Korpus gemessen (01.09.): das USB-PDF ist gemischt kodiert, 520 Umlaute
    # fertig, 262 zerlegt. Ohne diese Zeile findet eine Suche nach «Kündigung»
    # im USB-GAV null Treffer, obwohl das Wort 25 mal darin steht. Das KSBL-PDF
    # ist durchgehend fertig kodiert. Der Fehler traefe also nur eines der zwei
    # Dokumente und saehe beim Testen wie ein Retrieval-Problem aus.
    #
    # NFC und nicht NFKC, weil NFKC auch bedeutungstragende Zeichen ersetzt
    # («²» wuerde zu «2»). In einem Rechtstext ist das nicht hinnehmbar.
    text = unicodedata.normalize("NFC", text)

    # Wingdings-Aufzaehlungspunkte, Unicode-Kategorie Co. Private-Use-Zeichen
    # haben nur innerhalb einer bestimmten Schriftart eine Bedeutung, nach dem
    # Extrahieren sind sie inhaltsleer und kosten im Embedding nur Tokens.
    # Am Korpus gemessen: 43 mal U+F0B7 im USB, kein einziges im KSBL.
    text = "".join(z for z in text if unicodedata.category(z) != "Co")
    return text


def bereinige_seiten(seiten: list[Seite]) -> list[Seite]:
    """Wendet bereinige_text auf jede Seite an und behaelt die Seitenzahl."""
    return [Seite(s.nummer, bereinige_text(s.text)) for s in seiten]


def signatur(zeile: str) -> str:
    """Form einer Zeile, jede Ziffernfolge wird durch '#' ersetzt.
    Damit gelten 'GAV 1 / 26' und 'GAV 2 / 26' als dieselbe Zeile.
    GAV 2 / 26'   →   'GAV # / #
    """
    return re.sub(r"\d+", "#", zeile).strip()


def finde_wiederholte_zeilen(seiten: list[Seite], schwelle: float = SCHWELLE) -> set[str]:
    """Signaturen von Zeilen, die auf mindestens `schwelle` aller Seiten stehen.

    Kopf- und Fusszeilen wiederholen sich auf fast jeder Seite, Regelungstext
    nicht. Gemessen an den zwei GAV liegen Kopf- und Fusszeilen bei 95 bis 100
    Prozent, die naechsthaeufige Zeile bei 10 Prozent.

    Setzt ein Dokument mit genuegend Seiten voraus. Bei drei Seiten kann ein
    normaler Satz, der auf zweien steht, die Schwelle reissen.
    """
    zaehler = Counter()  # Wörterbuch mit null-Keys möglich
    for s in seiten:
        for sig in {signatur(z) for z in s.text.split("\n") if z.strip()}:
            zaehler[sig] += 1

    # 21 Seiten mal 0.8 ergibt 16.8. Alles ab 17 Seiten gilt als Kopf- oder Fusszeile
    mindestens = schwelle * len(seiten)
    return {sig for sig, anzahl in zaehler.items() if anzahl >= mindestens}


def entferne_wiederholte_zeilen(seiten: list[Seite], signaturen: set[str]) -> list[Seite]:
    """Entfernt aus jeder Seite die Zeilen, deren Signatur in `signaturen` steht."""
    bereinigt = []
    for s in seiten:
        behalten = [z for z in s.text.split("\n") if signatur(z) not in signaturen]
        bereinigt.append(Seite(s.nummer, "\n".join(behalten)))
    return bereinigt


def nummer_von(zeile: str) -> str:
    """Die Gliederungsnummer am Zeilenanfang, ohne Schlusspunkt.

    Gibt bei einer leeren Zeile einen leeren Text zurueck. Ohne diesen Fall
    wuerde `split()[0]` einen IndexError werfen. Im heutigen Ablauf kann das
    nicht eintreten, weil nur nach einem positiven `ist_ueberschrift`
    aufgerufen wird, aber die Funktion soll fuer sich allein halten.
    """
    teile = zeile.split()
    return teile[0].rstrip(".") if teile else ""


def titel_von(zeile: str) -> str:
    """Die Zeile ohne die fuehrende Gliederungsnummer."""
    teile = zeile.split(maxsplit=1)
    return teile[1] if len(teile) > 1 else ""


def ist_ueberschrift(zeile: str) -> bool:
    """Nummerierte Ueberschrift, kein Satz und keine Ordnungszahl im Fliesstext.

    Ein Satz enthaelt einen Punkt mit Leerzeichen dahinter ('berechnet. Fuer'),
    eine Ordnungszahl endet mit einem Punkt ('13. Monatslohn.').
    Beides geprueft am Titel, also ohne die eigene Nummer.

    An zwei GAV gemessen: KSBL findet 123 von 123 Verzeichnisnummern,
    USB alle 97 plus die tieferen Ebenen, die das Verzeichnis nicht auflistet.
    """
    if not UEBERSCHRIFT.match(zeile) or len(zeile) > MAX_UEBERSCHRIFT:
        return False
    t = titel_von(zeile)
    return ". " not in t and not t.endswith(".")


def schneide_in_abschnitte(seiten: list[Seite]) -> list[Abschnitt]:
    """Schneidet den Text an jeder nummerierten Ueberschrift.

    Vermerkt die Seite, auf der die Ueberschrift steht. Ein Abschnitt darf ueber
    einen Seitenumbruch laufen, gespeichert wird die Seite seines Beginns.
    Zeilen vor der ersten Ueberschrift entfallen.
    """
    abschnitte: list[Abschnitt] = []
    # nummer bleibt None, das ist der Waechter fuer "noch kein Abschnitt offen".
    # titel startet als leerer Text, damit die Typangabe `titel: str` stimmt.
    nummer, titel, seite, zeilen = None, "", 0, []

    for s in seiten:
        for zeile in s.text.split("\n"):
            if ist_ueberschrift(zeile):
                if nummer is not None:
                    text = "\n".join(zeilen).strip()
                    abschnitte.append(Abschnitt(nummer, titel, text, seite))
                nummer, titel, seite, zeilen = nummer_von(zeile), titel_von(zeile), s.nummer, []
            elif nummer is not None:
                zeilen.append(zeile)

    if nummer is not None:
        abschnitte.append(Abschnitt(nummer, titel, "\n".join(zeilen).strip(), seite))

    return abschnitte


def setze_pfade(abschnitte: list[Abschnitt]) -> list[Abschnitt]:
    """Traegt in jeden Abschnitt den Pfad seiner uebergeordneten Titel ein.

    Die Tiefe kommt aus der Anzahl Punkte in der Nummer. '2.3.3' ist Tiefe 3,
    also haengt der Abschnitt unter '2.3' und '2'. Gearbeitet wird in Lesereihenfolge
    mit einem Stapel, damit doppelt vergebene Nummern nicht durcheinanderbringen.
    Gemessen am USB: alle sechs einstelligen Nummern kommen doppelt vor. Ein
    Woerterbuch waere deshalb nicht entscheidbar, der Stapel meint immer das
    zuletzt gelesene Elternteil.

    ACHTUNG, veraendert die uebergebenen Abschnitte an Ort und Stelle und gibt
    dieselbe Liste zurueck, nicht eine neue. Anders als `bereinige_seiten` und
    `entferne_wiederholte_zeilen`, die neue Objekte bauen. Grund ist, dass der
    Pfad erst feststeht, wenn alle Abschnitte in Lesereihenfolge vorliegen.
    Deshalb kann `Abschnitt` auch nicht frozen sein, im Gegensatz zu `Dokument`.
    """
    stapel: list[str] = []

    for a in abschnitte:
        tiefe = a.nummer.count(".") + 1  # Z.B. 2 hat 0 -> 0 + 1 = 1 / 2.1 hat 1 -> 2
        stapel = stapel[: tiefe - 1]
        stapel.append(f"{a.nummer} {a.titel}")
        a.pfad = " > ".join(stapel)

    return abschnitte


if __name__ == "__main__":
    pfad = PROJEKT_WURZEL / "data" / "raw" / "gav_universitaetsspital_basel.pdf"
    seiten = bereinige_seiten(lade_pdf(pfad, ueberspringen={1, 2, 3}))
    seiten = entferne_wiederholte_zeilen(seiten, finde_wiederholte_zeilen(seiten))

    for a in setze_pfade(schneide_in_abschnitte(seiten))[:10]:
        print(f"S.{a.seite:3}  Ziff. {a.nummer:9} {a.titel[:50]} Pfade: {a.pfad}")
