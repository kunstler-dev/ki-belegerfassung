"""Command line: `belege einlesen <ordner>` reads every invoice in a folder and writes Excel and CSV."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .export import als_csv, als_excel
from .models import Ergebnis

DEMO = Path(__file__).resolve().parent.parent / "beispiele" / "ergebnisse.json"


def demo_ergebnisse() -> list[Ergebnis]:
    """Sample results for the bundled example invoices, so the tool can be shown without an API key."""
    return [Ergebnis.model_validate(e) for e in json.loads(DEMO.read_text(encoding="utf-8"))]


def einlesen(args: argparse.Namespace) -> int:
    if args.demo:
        ergebnisse = demo_ergebnisse()
    else:
        import anthropic

        from .extract import dateien, verarbeiten

        ordner = Path(args.ordner)
        liste = dateien(ordner)
        if not liste:
            print(f"Keine Belege (PDF/JPG/PNG) in {ordner} gefunden.", file=sys.stderr)
            return 1
        client = anthropic.Anthropic()
        ergebnisse = []
        for i, pfad in enumerate(liste, start=1):
            print(f"[{i}/{len(liste)}] {pfad.name} …", flush=True)
            ergebnisse.append(verarbeiten(client, pfad, args.effort))

    ziel = Path(args.ausgabe)
    als_excel(ergebnisse, ziel.with_suffix(".xlsx"))
    als_csv(ergebnisse, ziel.with_suffix(".csv"))

    zaehler = {s: sum(e.status == s for e in ergebnisse) for s in ("OK", "Prüfen", "Fehler")}
    print(f"\n{len(ergebnisse)} Belege: {zaehler['OK']} OK, {zaehler['Prüfen']} zu prüfen, {zaehler['Fehler']} Fehler")
    for e in ergebnisse:
        for h in e.hinweise:
            print(f"  ⚠ {e.datei}: {h}")
        if e.fehler:
            print(f"  ✖ {e.datei}: {e.fehler}")
    print(f"Gespeichert: {ziel.with_suffix('.xlsx')} und {ziel.with_suffix('.csv')}")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="belege", description="Eingangsrechnungen mit KI auslesen und prüfen.")
    sub = p.add_subparsers(dest="befehl", required=True)

    e = sub.add_parser("einlesen", help="Alle Belege in einem Ordner auslesen")
    e.add_argument("ordner", nargs="?", default="beispiele", help="Ordner mit PDF- oder Bilddateien")
    e.add_argument("-o", "--ausgabe", default="belege", help="Dateiname ohne Endung für .xlsx und .csv")
    e.add_argument("--effort", default="low", choices=["low", "medium", "high"], help="Gründlichkeit des Modells")
    e.add_argument("--demo", action="store_true", help="Beispielergebnisse ohne API-Aufruf verwenden")
    e.set_defaults(func=einlesen)

    w = sub.add_parser("web", help="Weboberfläche starten")
    w.add_argument("--port", type=int, default=8000)
    w.add_argument("--demo", action="store_true", help="Mit Beispielergebnissen starten")
    w.set_defaults(func=web)

    args = p.parse_args(argv)
    return args.func(args)


def web(args: argparse.Namespace) -> int:
    import uvicorn

    from .web import create_app

    uvicorn.run(create_app(demo=args.demo), host="127.0.0.1", port=args.port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
