"""Cart -> payment -> sale, as plain functions over the database.

Version 4 kept this logic inside FastAPI route handlers behind a server-side
in-memory cart, and the Qt till reached it over HTTP on the loopback interface.
Two carts existed - the till's and the server's - and they disagreed: the
quantity stepper changed one and not the other, so the payment could be raised
for the wrong total.  The money path could also only be exercised by starting a
web server.

Now there is one cart, the one on the till's screen, and both the till and the
REST endpoints call these two functions (docs/research/09, D2).
"""

from __future__ import annotations

import base64
import logging
import uuid
from datetime import datetime
from io import BytesIO

import qrcode

from server.services import promptpay, receipt, slip_verify
from server.services.restrictions import sale_gate

logger = logging.getLogger(__name__)


class CheckoutError(Exception):
    """A refusal with an HTTP-shaped status and a JSON-shaped payload, so the
    REST wrapper and the till can both show the same reason."""

    def __init__(self, status: int, **payload):
        super().__init__(payload.get("error", "checkout refused"))
        self.status = status
        self.payload = payload


def _merge(items: list[dict]) -> dict[str, int]:
    """product_id -> quantity; repeats of a product add up."""
    merged: dict[str, int] = {}
    for it in items:
        pid = it.get("product_id")
        qty = int(it.get("quantity", 1))
        if not pid:
            raise CheckoutError(400, error="every line needs a product_id")
        if qty <= 0:
            raise CheckoutError(400, error=f"{pid}: quantity must be positive")
        merged[pid] = merged.get(pid, 0) + qty
    return merged


def create_payment(db, items: list[dict], staff_confirmed: bool = False) -> dict:
    """Price the cart, apply the law, and hand back a pending payment with a QR.

    Refuses (CheckoutError) when the cart is empty, a product is unknown, stock
    is short, or a restricted item has no staff confirmation.  Stock is not
    taken down here - that happens in `confirm_payment`, in one transaction.
    """
    lines = []
    for pid, qty in _merge(items).items():
        product = db.get_product(pid)          # exact id: no fuzzy matching
        if not product:
            raise CheckoutError(404, error=f"Product {pid} not found")
        if product["stock"] < qty:
            raise CheckoutError(400, error=f"Insufficient stock for {product['name']}",
                                available=product["stock"], requested=qty)
        # Thai law: alcohol only 11:00-24:00 and only after staff confirm the
        # buyer's age; tobacco staff-only (docs/research/01, section 2)
        gate = sale_gate(product.get("restricted"), staff_confirmed)
        if not gate:
            raise CheckoutError(403, error=gate.reason, needs_staff=gate.needs_staff,
                                restricted=product.get("restricted"))
        if product.get("restricted", "none") != "none":
            db.log_event("override", {"kind": "restricted_sale", "product_id": pid,
                                      "restricted": product["restricted"]})
        lines.append({"product_id": pid, "product_name": product["name"],
                      "quantity": qty, "price": product["price"],
                      "total": product["price"] * qty})
    if not lines:
        raise CheckoutError(400, error="Cart is empty")

    settings = db.get_settings()
    subtotal = sum(line["total"] for line in lines)
    tax = subtotal * settings.get("tax_rate", 0.07)
    total = subtotal + tax
    payment_id = str(uuid.uuid4())

    # A real PromptPay payload, so a banking app opens with the amount filled
    # in.  Never show a code that looks real but cannot be paid.
    promptpay_id = settings.get("promptpay_id")
    if promptpay_id:
        qr_data, payable = promptpay.build_payload(promptpay_id, round(total, 2)), True
    else:
        qr_data, payable = f"NOT-CONFIGURED|{total:.2f}|{payment_id}", False
        logger.warning("promptpay_id is not set - the payment QR is not payable")

    payment = {
        "payment_id": payment_id,
        "timestamp": datetime.now().isoformat(),
        "items": lines,
        "subtotal": subtotal, "tax": tax, "total": total,
        "status": "pending",
        "qr_code": _qr_png_data_url(qr_data),
        "qr_payload": qr_data,
        "payable": payable,
    }
    db.add_pending_payment(payment_id, payment)
    logger.info("Payment created: %s for ฿%.2f", payment_id, total)
    return payment


def confirm_payment(db, payment_id: str, slip: str | None = None) -> dict:
    """Close the sale.  With a slip verifier configured, the customer's transfer
    slip must verify for the right amount first (docs/research/04, section 4)."""
    pending = db.get_pending_payment(payment_id)
    if not pending:
        raise CheckoutError(404, error="Payment not found")
    if pending["status"] != "pending":
        raise CheckoutError(400, error="Payment already processed")

    settings = db.get_settings()
    result = slip_verify.from_settings(settings).verify(slip, float(pending["total"]))
    if not result.ok:
        logger.warning("payment %s refused: %s", payment_id, result.reason)
        raise CheckoutError(402, error=result.reason, slip_checked=result.checked)

    sale = db.process_pending_payment(payment_id)
    if not sale:
        raise CheckoutError(400, error="Failed to process payment")
    sale["slip_checked"] = result.checked
    sale["slip_reference"] = result.reference
    sale["receipt"] = receipt.render(sale, settings)
    logger.info("Payment confirmed: %s (slip checked: %s)", payment_id, result.checked)
    return sale


def _qr_png_data_url(data: str) -> str:
    qr = qrcode.QRCode(error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=4)
    qr.add_data(data)
    qr.make(fit=True)
    buffer = BytesIO()
    qr.make_image(fill_color="black", back_color="white").save(buffer, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
