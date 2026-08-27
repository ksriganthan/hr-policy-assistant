# hr-policy-assistant

> ⚠️ **In Arbeit** – AI-Engineering-Sprint 24.08.–04.10.2026. Dieses README wird in Woche 6 finalisiert.

RAG-System über öffentliche Schweizer HR-Dokumente (GAV, Personalreglemente), das Fragen mit
nachprüfbaren Quellenzitaten beantwortet.

## Warum dieses Projekt
<!-- TODO: Problem in 3 Sätzen. Wer hat es? Warum ist eine Ähnlichkeitssuche allein zu wenig? -->

## Architektur
<!-- TODO Woche 6: Diagramm (Mermaid). Ingestion -> Chroma -> Retrieval -> LangGraph (Entwurf -> Kritik) -> FastAPI -->

## Resultate
<!-- TODO ab Woche 3: harte Zahlen. Ohne Zahlen überzeugt das Repo nicht. -->

| Setup | Retrieval-Precision | Groundedness | Halluzinationsrate | CHF/Anfrage | p95-Latenz |
|---|---|---|---|---|---|
| Baseline (naives RAG) |  |  |  |  |  |
| LangGraph + Kritik-Rolle |  |  |  |  |  |
| Agent-Loop |  |  |  |  |  |
| On-Premise (Ollama) |  |  |  |  |  |

## Technische Entscheide
<!-- Pro Entscheid: was gewählt, welche Alternativen, warum, wann würde ich anders entscheiden -->

| Entscheid | Gewählt | Alternativen | Begründung |
|---|---|---|---|
| Vektor-DB | Chroma | pgvector, Qdrant | lokal, kein Betriebsaufwand; Repository-Interface, damit pgvector austauschbar bleibt |
| Paketmanager | uv | poetry, pip-tools |  |
| Chunking |  |  |  |
| Embedding-Modell |  |  |  |
| Workflow vs. Agent |  |  |  |

## Datenschutz / Datenhoheit (revDSG)
<!-- TODO Woche 5: On-Premise-Variante, warum das im CH-Kontext (Spital, Versicherung, Pharma) zählt -->

## Setup
```bash
uv sync
cp .env.example .env   # Keys eintragen
uv run pytest
uv run ruff check .
```

## Was ich gelernt habe / was schiefging
<!-- TODO Woche 6: ehrlich. Dieser Abschnitt unterscheidet ein Portfolio-Repo von einem Tutorial-Repo. -->

## Daten
Der Korpus wird **nicht** mitgeliefert (`data/raw/` ist gitignored). Quellen und Abrufdatum: siehe `docs/korpus.md`.
