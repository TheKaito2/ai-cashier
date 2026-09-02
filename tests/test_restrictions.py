"""Thai law at the till: alcohol hours and ID checks, tobacco staff-only."""
from datetime import datetime

from server.services.restrictions import customer_visible, sale_gate

MORNING = datetime(2026, 9, 2, 9, 30)
AFTERNOON = datetime(2026, 9, 2, 15, 0)
LATE = datetime(2026, 9, 2, 23, 30)
AFTER_MIDNIGHT = datetime(2026, 9, 3, 0, 5)


def test_ordinary_goods_are_never_gated():
    assert sale_gate("none").ok and sale_gate(None).ok


def test_alcohol_is_refused_before_eleven_and_after_midnight():
    assert not sale_gate("alcohol", staff_confirmed=True, now=MORNING)
    assert not sale_gate("alcohol", staff_confirmed=True, now=AFTER_MIDNIGHT)


def test_the_afternoon_window_is_open_since_29_may_2026():
    g = sale_gate("alcohol", now=AFTERNOON)
    assert g.needs_staff and not g.ok          # in hours, but nobody checked an ID


def test_alcohol_in_hours_needs_a_staff_id_check():
    assert sale_gate("alcohol", staff_confirmed=True, now=LATE).ok
    assert not sale_gate("alcohol", staff_confirmed=False, now=LATE).ok


def test_tobacco_is_staff_only_at_any_hour():
    assert sale_gate("tobacco", now=MORNING).needs_staff
    assert sale_gate("tobacco", staff_confirmed=True, now=MORNING).ok


def test_tobacco_is_never_shown_to_customers():
    assert customer_visible("alcohol") and customer_visible("none")
    assert not customer_visible("tobacco")


def test_the_api_refuses_a_restricted_item_without_staff(client):
    r = client.patch("/api/products/pepsi/restriction", json={"restricted": "tobacco"})
    assert r.status_code == 200 and r.json()["restricted"] == "tobacco"
    r = client.post("/api/checkout", json={"items": [{"product_id": "pepsi"}]})
    assert r.status_code == 403 and r.json()["needs_staff"]
    r = client.post("/api/checkout",
                    json={"items": [{"product_id": "pepsi"}], "staff_confirmed": True})
    assert r.status_code == 200
    # and the confirmation is on the record
    kinds = [e["kind"] for e in client.get("/api/events").json()]
    assert "override" in kinds


def test_customer_product_list_hides_tobacco(client):
    client.patch("/api/products/pepsi/restriction", json={"restricted": "tobacco"})
    staff = {p["id"] for p in client.get("/api/products").json()}
    customer = {p["id"] for p in client.get("/api/products?staff=false").json()}
    assert "pepsi" in staff and "pepsi" not in customer


def test_an_unknown_restriction_is_rejected(client):
    r = client.patch("/api/products/pepsi/restriction", json={"restricted": "fireworks"})
    assert r.status_code == 400
