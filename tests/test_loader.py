"""Tests fuer den PDF-Loader und die Textbereinigung."""

import pytest

from hr_policy_assistant.ingestion.loader import (
    PROJEKT_WURZEL,
    Seite,
    bereinige_text,
    entferne_wiederholte_zeilen,
    finde_wiederholte_zeilen,
    lade_pdf,
    schneide_in_abschnitte,
    signatur,
)

# Zwei Miniseiten mit Kopfzeile, Fusszeile und echtem Inhalt.
# Die Inhaltszeilen sind genau die, die der geloeschte TOC-Filter
# frueher faelschlich weggeworfen hat.
SEITEN = [
    Seite(1, "GAV Musterspital\nGAV 1 / 2\n1. Einleitung\n10 ¼ 5\n7 Stand 2016"),
    Seite(2, "GAV Musterspital\nGAV 2 / 2\n2. Ziel\n1 Der GAV stuetzt sich auf § 11 vom 2011"),
]


def _bereinigt() -> str:
    """Die Miniseiten durch die volle Kopfzeilen-Bereinigung."""
    marken = finde_wiederholte_zeilen(SEITEN)
    return "\n".join(s.text for s in entferne_wiederholte_zeilen(SEITEN, marken))


def test_bereinige_text_normalisiert_umlaute():
    zerlegt = "Ku\u0308ndigungsfrist"
    assert "Kündigungsfrist" not in zerlegt
    assert "Kündigungsfrist" in bereinige_text(zerlegt)


def test_bereinige_text_entfernt_symbolzeichen():
    assert bereinige_text("\uf0b7 Ferien") == " Ferien"


def test_signatur_macht_seitenzahlen_gleich():
    assert signatur("GAV 1 / 26") == signatur("GAV 2 / 26")


def test_signatur_ersetzt_ziffernfolge_durch_ein_zeichen():
    assert signatur("GAV 1 / 26") == "GAV # / #"


def test_signatur_ignoriert_randleerzeichen():
    assert signatur("  GAV 1 / 26  ") == "GAV # / #"


def test_finde_wiederholte_zeilen_erkennt_kopf_und_fusszeile():
    assert finde_wiederholte_zeilen(SEITEN) == {"GAV Musterspital", "GAV # / #"}


def test_finde_wiederholte_zeilen_verschont_inhalt():
    assert signatur("1. Einleitung") not in finde_wiederholte_zeilen(SEITEN)


def test_entferne_wiederholte_zeilen_behaelt_seitenanzahl():
    marken = finde_wiederholte_zeilen(SEITEN)
    assert len(entferne_wiederholte_zeilen(SEITEN, marken)) == len(SEITEN)


def test_entferne_wiederholte_zeilen_wirft_marken_weg():
    sauber = _bereinigt()
    assert "GAV Musterspital" not in sauber
    assert "GAV 1 / 2" not in sauber


def test_tabellenzeilen_und_fussnoten_ueberleben():
    """Regression: der geloeschte TOC-Filter hat genau diese Zeilen entfernt."""
    sauber = _bereinigt()
    assert "10 ¼ 5" in sauber
    assert "7 Stand 2016" in sauber
    assert "1 Der GAV stuetzt sich auf § 11 vom 2011" in sauber


PDF = PROJEKT_WURZEL / "data" / "raw" / "gav_universitaetsspital_basel.pdf"


@pytest.mark.skipif(not PDF.exists(), reason="Korpus liegt nicht im Repo")
def test_lade_pdf_gibt_liste_von_seiten_zurueck():
    seiten = lade_pdf(PDF)
    assert isinstance(seiten, list)
    assert all(isinstance(s, Seite) for s in seiten)
    assert len(seiten) > 20


@pytest.mark.skipif(not PDF.exists(), reason="Korpus liegt nicht im Repo")
def test_lade_pdf_ueberspringt_genau_die_angegebenen_seiten():
    assert len(lade_pdf(PDF, ueberspringen={2, 3})) == len(lade_pdf(PDF)) - 2


def test_schneide_in_abschnitte_merkt_die_seite():
    abschnitte = schneide_in_abschnitte(SEITEN)
    assert abschnitte[0].nummer == "1"
    assert abschnitte[0].seite == 1
    assert abschnitte[1].nummer == "2"
    assert abschnitte[1].seite == 2


@pytest.mark.skipif(not PDF.exists(), reason="Korpus liegt nicht im Repo")
def test_lade_pdf_fuehrt_die_echte_seitenzahl_mit():
    """Regression: der Listenindex ist nicht die Seitenzahl."""
    seiten = lade_pdf(PDF, ueberspringen={1, 2, 3})
    assert seiten[0].nummer == 4