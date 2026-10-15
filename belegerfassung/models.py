"""Data model of an invoice as Claude returns it, plus the result of the plausibility checks."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class Position(BaseModel):
    """One line item on the invoice."""

    beschreibung: str = Field(description="Text of the line item as printed on the invoice")
    menge: Decimal | None = Field(description="Quantity, or null if not printed")
    einzelpreis: Decimal | None = Field(description="Net unit price, or null if not printed")
    gesamt: Decimal = Field(description="Net line total")


class Beleg(BaseModel):
    """Fields a German bookkeeper needs from an incoming invoice (Eingangsrechnung)."""

    lieferant: str = Field(description="Name of the company that issued the invoice")
    lieferant_ust_id: str | None = Field(description="Supplier VAT ID (USt-IdNr.), e.g. DE123456789, or null")
    rechnungsnummer: str = Field(description="Invoice number exactly as printed")
    rechnungsdatum: date = Field(description="Invoice date")
    faelligkeitsdatum: date | None = Field(description="Payment due date, or null if not printed")
    waehrung: str = Field(description="ISO 4217 currency code, e.g. EUR")
    netto: Decimal = Field(description="Total net amount")
    mwst_satz: Decimal | None = Field(description="VAT rate in percent, e.g. 19 or 7; null if mixed or not printed")
    mwst_betrag: Decimal = Field(description="Total VAT amount; 0 if none")
    brutto: Decimal = Field(description="Total gross amount to pay")
    iban: str | None = Field(description="Supplier IBAN for payment, or null")
    positionen: list[Position] = Field(description="Line items; empty list if none are listed")


class Ergebnis(BaseModel):
    """One processed file: the extracted invoice (if any) and what the checks found."""

    datei: str
    beleg: Beleg | None = None
    hinweise: list[str] = Field(default_factory=list)
    fehler: str | None = None

    @property
    def status(self) -> str:
        if self.fehler:
            return "Fehler"
        return "Prüfen" if self.hinweise else "OK"
