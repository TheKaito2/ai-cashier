"""The receipt, in the two forms Thai law knows.

docs/research/01-legal-thailand.md section 4 and 04 section 5 (ledger H08, L09):

  VAT-registered shop (turnover > THB 1.8 m/yr)  ->  abbreviated tax invoice,
      Revenue Code s.86/6: the words "Tax Invoice (ABB)", seller name, address
      and taxpayer id, a running number, date, items, amount, and a line saying
      VAT is included.
  everyone else                                  ->  a plain receipt, no VAT lines.

Plain text, 32 columns, which is what an ESC/POS thermal printer takes as-is.
"""

from __future__ import annotations

from datetime import datetime

WIDTH = 32


def _line(left: str, right: str = "") -> str:
    left = left[:WIDTH - len(right) - 1] if right else left[:WIDTH]
    return f"{left:<{WIDTH - len(right)}}{right}" if right else left


def _centre(text: str) -> str:
    return text[:WIDTH].center(WIDTH).rstrip()


def render(sale: dict, settings: dict) -> str:
    """One sale row (as `Database.get_sale` returns it) to printable text."""
    vat = bool(settings.get("vat_registered"))
    cur = settings.get("currency", "฿")
    rate = float(settings.get("tax_rate", 0.07))
    when = datetime.fromisoformat(sale["timestamp"]).strftime("%d/%m/%Y %H:%M")

    out = [_centre(settings.get("store_name", "Store"))]
    if settings.get("store_address"):
        out.append(_centre(settings["store_address"]))
    if vat:
        out += [_centre("ใบกำกับภาษีอย่างย่อ"), _centre("TAX INVOICE (ABB)"),
                _centre(f"TIN {settings.get('tin', '') or '-'}")]
    else:
        out.append(_centre("ใบเสร็จรับเงิน / RECEIPT"))
    out += [_line(f"No. {sale['id']}"), _line(when), "-" * WIDTH]

    for it in sale["items"]:
        out.append(_line(it["product_name"]))
        out.append(_line(f"  {it['quantity']} x {it['price']:.2f}", f"{it['total']:.2f}"))

    out.append("-" * WIDTH)
    if vat:
        out.append(_line("Subtotal", f"{sale['subtotal']:.2f}"))
        out.append(_line(f"VAT {rate * 100:.0f}%", f"{sale['tax']:.2f}"))
    out.append(_line("TOTAL", f"{cur}{sale['total']:.2f}"))
    if vat:
        out.append(_centre("VAT included / รวม VAT แล้ว"))
    out.append(_centre("Thank you / ขอบคุณค่ะ"))
    return "\n".join(out) + "\n"
