# Basis. "slim" ist Debian ohne Compiler und Doku, rund 50 MB statt 400.
# Die Version ist festgenagelt, "3.12" ohne Zusatz waere ein bewegliches Ziel.
FROM python:3.12-slim

# uv aus dem offiziellen uv-Image herueberkopieren, statt es per Skript zu installieren.
# COPY --from=... holt Dateien aus einem fremden Image, ohne dieses Image zu starten.
COPY --from=ghcr.io/astral-sh/uv:0.5.11 /uv /uvx /bin/

# Arbeitsverzeichnis im Container. Ab hier sind alle Pfade relativ dazu.
WORKDIR /app

# Umgebungsvariablen fuer den Betrieb im Container.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONUNBUFFERED=1 \
    CHROMA_PATH=/app/chroma \
    HRPA_MODELL=qwen2.5:14b \
    OLLAMA_HOST=http://host.docker.internal:11434

# ---- Schicht A: Abhaengigkeiten. Aendert sich nur, wenn pyproject.toml oder uv.lock sich aendern.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# ---- Schicht B: der Index. Aendert sich nur bei einer Neuindexierung, also
# seltener als der Code und deshalb davor.
COPY chroma/ ./chroma/

# ---- Schicht C: der Code. Aendert sich bei jeder Codeaenderung.
# README.md muss mit, weil pyproject.toml es als readme deklariert und hatchling
# es beim Paketbau liest. Bewusst hier unten und nicht bei pyproject.toml, sonst
# wuerde jede README-Aenderung die teure Installation ungueltig machen.
COPY README.md ./
COPY src/ ./src/
RUN uv sync --frozen --no-dev

# Der Dienst hoert auf 8000. EXPOSE oeffnet nichts, es ist eine Angabe fuer den Leser
# und fuer Werkzeuge. Geoeffnet wird beim Start mit -p.
EXPOSE 8000

# Lebenszeichen. Docker ruft das selbst auf und markiert den Container als gesund oder krank.
# Genau dafuer gibt es /gesund ohne Modellaufruf.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request;urllib.request.urlopen('http://localhost:8000/gesund')"

# Startbefehl. Ohne --reload, das ist eine Entwicklerhilfe und gehoert nicht ins Image.
# 0.0.0.0 statt 127.0.0.1, sonst waere der Dienst nur im Container selbst erreichbar.
CMD ["uv", "run", "--no-dev", "uvicorn", "hr_policy_assistant.api.main:app", \
     "--host", "0.0.0.0", "--port", "8000"]