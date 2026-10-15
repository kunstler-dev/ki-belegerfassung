"""Plausibility checks on an extracted invoice.

The model can misread a digit, so every result is checked with plain arithmetic before
anyone books it. A finding doesn't reject the invoice; it marks it for a human to look at.
"""

from __future__ import annotations

import re
from datetime import date
from decimal import Decimal

from .models import Beleg

# Rounding differences of a few cents are normal on invoices with many line items
TOLERANZ = Decimal("0.02")
UBLICHE_MWST_SAETZE = {Decimal("0"), Decimal("7"), Decimal("19")}
UST_ID = re.compile(r"^[A-Z]{2}[0-9A-Z]{2,13}$")


def _de(betrag: Decimal) -> str:
    """1234.5 -> '1.234,50' as printed on German invoices."""
    return f"{betrag:,.2f}".replace(",", " ").replace(".", ",").replace(" ", ".")


def iban_gueltig(iban: str) -> bool:
    """ISO 13616 checksum (mod 97)."""
    s = iban.replace(" ", "").upper()
    if not re.fullmatch(r"[A-Z]{2}[0-9]{2}[0-9A-Z]{10,30}", s):
        return False
    umgestellt = s[4:] + s[:4]
    zahl = "".join(str(int(c, 36)) for c in umgestellt)
    return int(zahl) % 97 == 1


def pruefen(beleg: Beleg, heute: date | None = None) -> list[str]:
    """Returns human-readable findings in German; an empty list means the invoice looks consistent."""
    heute = heute or date.today()
    hinweise: list[str] = []

    if abs(beleg.netto + beleg.mwst_betrag - beleg.brutto) > TOLERANZ:
        hinweise.append(f"Netto + MwSt. ({_de(beleg.netto + beleg.mwst_betrag)}) ergibt nicht den Bruttobetrag ({_de(beleg.brutto)}).")

    if beleg.mwst_satz is not None:
        if beleg.mwst_satz not in UBLICHE_MWST_SAETZE:
            hinweise.append(f"Ungewöhnlicher MwSt.-Satz: {beleg.mwst_satz} %.")
        erwartet = (beleg.netto * beleg.mwst_satz / 100).quantize(Decimal("0.01"))
        if abs(erwartet - beleg.mwst_betrag) > TOLERANZ:
            hinweise.append(f"MwSt.-Betrag {_de(beleg.mwst_betrag)} passt nicht zu {beleg.mwst_satz} % von {_de(beleg.netto)} (erwartet {_de(erwartet)}).")

    if beleg.positionen:
        summe = sum((p.gesamt for p in beleg.positionen), Decimal("0"))
        if abs(summe - beleg.netto) > TOLERANZ:
            hinweise.append(f"Summe der Positionen ({_de(summe)}) weicht vom Nettobetrag ({_de(beleg.netto)}) ab.")

    if beleg.rechnungsdatum > heute:
        hinweise.append("Rechnungsdatum liegt in der Zukunft.")
    if beleg.faelligkeitsdatum and beleg.faelligkeitsdatum < beleg.rechnungsdatum:
        hinweise.append("Fälligkeitsdatum liegt vor dem Rechnungsdatum.")

    if beleg.iban and not iban_gueltig(beleg.iban):
        hinweise.append("IBAN hat eine ungültige Prüfsumme.")
    if beleg.lieferant_ust_id and not UST_ID.match(beleg.lieferant_ust_id.replace(" ", "")):
        hinweise.append("USt-IdNr. hat ein ungültiges Format.")

    if beleg.waehrung.upper() != "EUR":
        hinweise.append(f"Rechnung in Fremdwährung ({beleg.waehrung}).")

    return hinweise
