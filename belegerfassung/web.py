"""Small web interface: drop invoices in, check the table, download Excel or CSV."""

from __future__ import annotations

import tempfile
from importlib.resources import files
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, HTMLResponse

from .export import als_csv, als_excel
from .models import Ergebnis

MAX_BYTES = 20 * 1024 * 1024


def create_app(demo: bool = False, client=None) -> FastAPI:
    app = FastAPI(title="KI-Belegerfassung", docs_url=None, redoc_url=None)
    # Single-user tool: the last batch lives in memory until the next upload
    state: dict[str, list[Ergebnis]] = {"ergebnisse": []}
    if demo:
        from .cli import demo_ergebnisse

        state["ergebnisse"] = demo_ergebnisse()

    seite = files("belegerfassung").joinpath("templates/index.html").read_text(encoding="utf-8")

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return seite.replace("{{DEMO}}", "true" if demo else "false")

    @app.get("/api/belege")
    def liste() -> list[dict]:
        return [{**e.model_dump(mode="json"), "status": e.status} for e in state["ergebnisse"]]

    @app.post("/api/belege")
    async def hochladen(dateien: list[UploadFile] = File(...)) -> list[dict]:
        if demo:
            raise HTTPException(400, "Im Demo-Modus werden keine Dateien verarbeitet.")
        from .extract import ENDUNGEN, verarbeiten

        nonlocal client
        if client is None:
            import anthropic

            client = anthropic.Anthropic()
        neu: list[Ergebnis] = []
        with tempfile.TemporaryDirectory() as tmp:
            for datei in dateien:
                name = Path(datei.filename or "beleg").name
                if Path(name).suffix.lower() not in ENDUNGEN:
                    neu.append(Ergebnis(datei=name, fehler="Nur PDF, JPG, PNG, WEBP oder GIF."))
                    continue
                daten = await datei.read(MAX_BYTES + 1)
                if len(daten) > MAX_BYTES:
                    neu.append(Ergebnis(datei=name, fehler="Datei größer als 20 MB."))
                    continue
                pfad = Path(tmp) / name
                pfad.write_bytes(daten)
                neu.append(verarbeiten(client, pfad))
        state["ergebnisse"] = neu
        return liste()

    @app.get("/export/{format}")
    def export(format: str) -> FileResponse:
        if format not in ("xlsx", "csv"):
            raise HTTPException(404)
        ziel = Path(tempfile.gettempdir()) / f"belege.{format}"
        (als_excel if format == "xlsx" else als_csv)(state["ergebnisse"], ziel)
        return FileResponse(ziel, filename=f"belege.{format}")

    return app
