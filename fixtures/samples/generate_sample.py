"""Generate the committed synthetic strata package. Reproducible; no real data.

Run: uv run python fixtures/samples/generate_sample.py
"""

from pathlib import Path

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

OUT = Path(__file__).parent / "sample-strata-package.pdf"

PAGES = [
    [
        "STRATA PLAN BCS9999 - GARDENS AT YALETOWN",
        "Combined Document Package (SYNTHETIC - NOT A REAL BUILDING)",
        "",
        "Unit 304 - Strata Lot 18",
        "Unit Entitlement: 18 / 2719",
    ],
    [
        "ANNUAL GENERAL MEETING - MINUTES",
        "Date: March 12, 2024",
        "",
        "1. The reserve (contingency) fund balance as of Dec 31, 2023",
        "   was $412,000. The fund has been DECLINING over three years.",
        "2. A special levy of $4,200 per unit was approved on",
        "   November 15, 2023 for roof replacement.",
    ],
    [
        "SPECIAL GENERAL MEETING - MINUTES",
        "Date: February 2, 2024",
        "",
        "A special levy of $850 per unit was approved on",
        "February 2, 2024 for elevator modernization.",
        "",
        "No litigation is currently pending against the strata corporation.",
    ],
]


def main() -> None:
    c = canvas.Canvas(str(OUT), pagesize=letter)
    for page in PAGES:
        text = c.beginText(72, 720)
        text.setFont("Helvetica", 12)
        for line in page:
            text.textLine(line)
        c.drawText(text)
        c.showPage()
    c.save()
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
