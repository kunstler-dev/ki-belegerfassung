# KI-Belegerfassung (AI invoice capture)

**Read incoming invoices with AI, check them automatically and export them to Excel.**

[Deutsch](README.md) · English

![Web interface in demo mode](docs/screenshot.png)

## What it does

In many small companies someone types supplier invoices into a spreadsheet or accounting software by hand. This tool does the first step:

1. **Read.** PDF invoices and photos or scans are sent to Claude. The reply is structured JSON that matches a fixed schema (structured outputs), not free text.
2. **Check.** Every invoice is verified with plain arithmetic, not with AI: net + VAT = gross, VAT amount matches the rate (0, 7 or 19 %), line items add up to the net amount, IBAN checksum, VAT ID format, dates and currency.
3. **Export.** Results go to an Excel workbook colored by status and to a CSV with semicolons and decimal commas for German accounting software.

An invoice that fails a check is not rejected; it is marked **"Prüfen"** (review) so a person looks at it before it is booked.

The UI and output are in German because the target users are German businesses.

## Quick start

```bash
git clone https://github.com/kunstler-dev/ki-belegerfassung
cd ki-belegerfassung
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

belege web --demo                 # no API key needed, three sample invoices
export ANTHROPIC_API_KEY=...      # from console.anthropic.com
belege einlesen beispiele/        # writes belege.xlsx and belege.csv
```

The `beispiele/` folder holds three **fictional** invoices: a correct PDF, a PDF with a deliberately wrong gross total, and a PNG scan with two VAT rates. The demo results are prepared sample data; a test checks that their findings match what the check logic produces for those invoices.

## Design

- `client.beta.messages.parse(..., output_format=Beleg)` returns a validated Pydantic object; missing fields come back as `null`.
- The model reads, Python checks: the arithmetic is deterministic and explainable.
- Errors are recorded per invoice, so one bad file doesn't stop a batch.
- Refused requests are retried on a recommended fallback model (`fallbacks: "default"`).
- `--effort low` by default; raise it for poor scans.
- 21 tests with a fake API client, so the test suite costs nothing to run.

## My role

I built this project with the AI coding assistant Claude Code. I am not a trained programmer. My part was choosing a real bookkeeping use case, deciding which fields to extract and which checks to run, directing the implementation step by step, testing the results against the sample invoices and writing the documentation.

## Limits

Not a replacement for bookkeeping: flagged invoices need a human review. Invoices are sent to the Anthropic API, so clarify data protection (GDPR) before using real customer data. XRechnung/ZUGFeRD e-invoices are already machine-readable and don't need AI.

## License

MIT
