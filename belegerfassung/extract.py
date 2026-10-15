"""Reads an invoice (PDF or image) with Claude and returns it as a validated `Beleg`."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

import anthropic

from .checks import pruefen
from .models import Beleg, Ergebnis

MODEL = "claude-opus-5-5"
# If the model declines a request, the API re-runs it on a recommended fallback model
FALLBACK_BETA = "server-side-fallback-2026-07-01"

BILDTYPEN = {"image/png", "image/jpeg", "image/webp", "image/gif"}
ENDUNGEN = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".gif"}

SYSTEM = """Du bist eine sorgfältige Buchhaltungskraft in einem deutschen Unternehmen.
Du liest Eingangsrechnungen und überträgst die Angaben exakt so, wie sie auf dem Beleg stehen.

Regeln:
- Erfinde nichts. Steht eine Angabe nicht auf dem Beleg, gib null zurück.
- Beträge als Zahl mit Punkt als Dezimaltrennzeichen, ohne Tausenderpunkte und ohne Währungszeichen.
- Daten im Format JJJJ-MM-TT. Deutsche Datumsangaben wie 03.11.2026 sind Tag.Monat.Jahr.
- Rechnungsnummer und IBAN Zeichen für Zeichen übernehmen.
- Bei mehreren MwSt.-Sätzen: mwst_satz = null, mwst_betrag = Summe aller MwSt.-Beträge."""


def _inhalt(pfad: Path) -> dict[str, Any]:
    """The file as a content block: PDFs as a document, photos and scans as an image."""
    daten = base64.standard_b64encode(pfad.read_bytes()).decode("ascii")
    typ = mimetypes.guess_type(pfad.name)[0] or ""
    if typ == "application/pdf":
        return {"type": "document", "source": {"type": "base64", "media_type": typ, "data": daten}}
    if typ in BILDTYPEN:
        return {"type": "image", "source": {"type": "base64", "media_type": typ, "data": daten}}
    raise ValueError(f"Nicht unterstütztes Dateiformat: {pfad.suffix}")


def lesen(client: anthropic.Anthropic, pfad: Path, effort: str = "low") -> Beleg:
    """One API call per invoice. Structured outputs guarantee the reply matches the `Beleg` schema."""
    antwort = client.beta.messages.parse(
        model=MODEL,
        max_tokens=16000,
        betas=[FALLBACK_BETA],
        fallbacks="default",
        output_config={"effort": effort},
        output_format=Beleg,
        system=SYSTEM,
        messages=[{
            "role": "user",
            "content": [_inhalt(pfad), {"type": "text", "text": "Lies diese Rechnung aus."}],
        }],
    )
    if antwort.stop_reason == "refusal":
        raise RuntimeError("Das Modell hat die Verarbeitung dieses Belegs abgelehnt.")
    if antwort.stop_reason == "max_tokens" or antwort.parsed_output is None:
        raise RuntimeError("Die Antwort war unvollständig. Bitte erneut versuchen.")
    return antwort.parsed_output


def verarbeiten(client: anthropic.Anthropic, pfad: Path, effort: str = "low") -> Ergebnis:
    """Reads one file and runs the checks. Errors end up in the result instead of stopping a whole batch."""
    try:
        beleg = lesen(client, pfad, effort)
    except (anthropic.APIConnectionError, anthropic.RateLimitError, anthropic.APIStatusError) as e:
        return Ergebnis(datei=pfad.name, fehler=f"API-Fehler: {e.__class__.__name__}")
    except (ValueError, RuntimeError) as e:
        return Ergebnis(datei=pfad.name, fehler=str(e))
    return Ergebnis(datei=pfad.name, beleg=beleg, hinweise=pruefen(beleg))


def dateien(ordner: Path) -> list[Path]:
    return sorted(p for p in ordner.iterdir() if p.suffix.lower() in ENDUNGEN)
