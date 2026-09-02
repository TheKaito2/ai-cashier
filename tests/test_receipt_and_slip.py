"""Receipts in both legal forms, and the payment loop that checks the slip."""
from server.services.receipt import WIDTH, render
from server.services.slip_verify import HttpSlipVerifier, NullVerifier, SlipResult

SALE = {"id": "SALE-20260902-abc", "timestamp": "2026-09-02T12:00:00",
        "subtotal": 28.0, "tax": 1.96, "total": 29.96,
        "items": [{"product_name": "Pepsi 325ml", "quantity": 2, "price": 14.0, "total": 28.0}]}


def test_a_vat_registered_shop_prints_an_abbreviated_tax_invoice():
    text = render(SALE, {"store_name": "Krist Mart", "vat_registered": True,
                         "tin": "0123456789012", "tax_rate": 0.07})
    assert "TAX INVOICE (ABB)" in text and "0123456789012" in text
    assert "VAT 7%" in text and "SALE-20260902-abc" in text


def test_a_small_shop_prints_a_plain_receipt():
    text = render(SALE, {"store_name": "Krist Mart", "vat_registered": False})
    assert "RECEIPT" in text and "TAX INVOICE" not in text and "VAT" not in text


def test_every_line_fits_a_thermal_printer():
    text = render(SALE, {"store_name": "A" * 60, "vat_registered": True, "tin": "1"})
    assert all(len(line) <= WIDTH for line in text.splitlines())


def test_no_verifier_accepts_but_says_it_did_not_check():
    r = NullVerifier().verify(None, 29.96)
    assert r.ok and not r.checked


class FakeSession:
    def __init__(self, amount, status=200):
        self.amount, self.status = amount, status

    def post(self, url, json, headers, timeout):
        session = self

        class R:
            status_code = session.status
            def json(self):
                return {"status": 200, "data": {"amount": {"amount": session.amount},
                                                "transRef": "TR1"}}
        return R()


def test_http_verifier_refuses_a_slip_for_the_wrong_amount():
    v = HttpSlipVerifier("https://verifier.example/api", session=FakeSession(10.0))
    r = v.verify("00020101...", 29.96)
    assert not r.ok and r.checked and "10.00" in r.reason


def test_http_verifier_accepts_a_matching_slip():
    v = HttpSlipVerifier("https://verifier.example/api", session=FakeSession(29.96))
    r = v.verify("00020101...", 29.96)
    assert r == SlipResult(True, True, "slip verified", 29.96, "TR1")


def test_http_verifier_needs_a_slip_at_all():
    assert not HttpSlipVerifier("https://x", session=FakeSession(1)).verify(None, 1).ok


def test_confirm_returns_a_receipt_and_the_receipt_endpoint_serves_it(client):
    payment = client.post("/api/checkout", json={"items": [{"product_id": "pepsi"}]}).json()
    sale = client.post(f"/api/confirm-payment/{payment['payment_id']}", json={}).json()
    assert sale["slip_checked"] is False and "RECEIPT" in sale["receipt"]
    r = client.get(f"/api/receipt/{sale['id']}")
    assert r.status_code == 200 and sale["id"] in r.text


def test_confirm_is_refused_when_a_verifier_is_set_and_no_slip_is_shown(client, monkeypatch):
    import server.main as main
    main.db.set_setting("slip_verifier_url", "https://verifier.example/api")
    payment = client.post("/api/checkout", json={"items": [{"product_id": "pepsi"}]}).json()
    r = client.post(f"/api/confirm-payment/{payment['payment_id']}", json={})
    assert r.status_code == 402 and "slip" in r.json()["error"]
