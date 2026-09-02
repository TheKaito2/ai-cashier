"""Cart -> payment -> stock, through the functions the till calls and the REST
wrappers the dashboard calls.  One code path, two doors."""
import re

import pytest

from server.services.checkout import CheckoutError, confirm_payment, create_payment


def stock(db, pid):
    return db.get_product(pid)["stock"]


def test_total_is_subtotal_plus_seven_percent(db):
    payment = create_payment(db, [{"product_id": "pepsi", "quantity": 2}])   # 14.00 x 2
    assert payment["subtotal"] == 28.0
    assert round(payment["tax"], 2) == 1.96
    assert round(payment["total"], 2) == 29.96


def test_repeats_of_a_product_become_one_line(db):
    payment = create_payment(db, [{"product_id": "pepsi"}, {"product_id": "pepsi"}])
    assert len(payment["items"]) == 1 and payment["items"][0]["quantity"] == 2


def test_unknown_product_is_refused(db):
    with pytest.raises(CheckoutError) as e:
        create_payment(db, [{"product_id": "not-a-product"}])
    assert e.value.status == 404


def test_a_product_id_must_match_exactly(db):
    """v4 accepted any product whose id merely contained the request."""
    with pytest.raises(CheckoutError):
        create_payment(db, [{"product_id": "peps"}])


def test_cannot_buy_more_than_the_shelf_holds(db):
    with pytest.raises(CheckoutError) as e:
        create_payment(db, [{"product_id": "pepsi", "quantity": stock(db, "pepsi") + 1}])
    assert e.value.status == 400 and "stock" in e.value.payload["error"].lower()


def test_empty_cart_cannot_be_paid_for(db):
    with pytest.raises(CheckoutError) as e:
        create_payment(db, [])
    assert e.value.status == 400


def test_confirming_payment_takes_the_stock_down(db):
    before = stock(db, "sprite")
    payment = create_payment(db, [{"product_id": "sprite", "quantity": 2}])
    assert before == stock(db, "sprite")            # pending: nothing moved yet
    confirm_payment(db, payment["payment_id"])
    assert stock(db, "sprite") == before - 2


def test_a_payment_cannot_be_confirmed_twice(db):
    payment = create_payment(db, [{"product_id": "sprite"}])
    confirm_payment(db, payment["payment_id"])
    with pytest.raises(CheckoutError) as e:
        confirm_payment(db, payment["payment_id"])
    assert e.value.status == 400


def test_sales_rung_up_in_the_same_second_get_different_ids(db):
    """The id used to be the timestamp to the second, so a busy till collided."""
    ids = [confirm_payment(db, create_payment(db, [{"product_id": "crystal-water"}])["payment_id"])["id"]
           for _ in range(4)]
    assert len(set(ids)) == 4, ids


def test_payment_carries_a_scannable_qr(db):
    payment = create_payment(db, [{"product_id": "pepsi"}])
    assert re.match(r"^data:image/png;base64,[A-Za-z0-9+/=]+$", payment["qr_code"])


def test_analytics_counts_only_confirmed_sales(db):
    before = db.get_analytics()["total_sales"]
    payment = create_payment(db, [{"product_id": "pepsi"}])
    assert db.get_analytics()["total_sales"] == before          # still pending
    confirm_payment(db, payment["payment_id"])
    assert db.get_analytics()["total_sales"] == before + 1


# ------------------------------------------------------------- the REST door

def test_the_dashboard_can_ring_up_and_confirm_a_sale(client):
    r = client.post("/api/checkout", json={"items": [{"product_id": "pepsi", "quantity": 2}]})
    assert r.status_code == 200, r.text
    payment = r.json()
    assert round(payment["total"], 2) == 29.96
    r = client.post(f"/api/confirm-payment/{payment['payment_id']}", json={})
    assert r.status_code == 200 and r.json()["items"][0]["quantity"] == 2


def test_the_rest_door_reports_the_same_refusals(client):
    assert client.post("/api/checkout", json={"items": []}).status_code == 400
    assert client.post("/api/checkout", json={"items": [{"product_id": "ghost"}]}).status_code == 404
    assert client.post("/api/confirm-payment/nope", json={}).status_code == 404


def test_on_the_lan_writes_need_the_pin_and_reads_do_not(client):
    import server.main as main
    main.app.state.lan = True
    try:
        assert client.get("/api/products").status_code == 200
        r = client.post("/api/restock/pepsi?quantity=1")
        assert r.status_code == 401                       # no PIN configured: refuse
        main.db.set_setting("dashboard_pin", "4321")
        assert client.post("/api/restock/pepsi?quantity=1").status_code == 401
        assert client.post("/api/restock/pepsi?quantity=1",
                           headers={"X-Dashboard-Pin": "0000"}).status_code == 401
        assert client.post("/api/restock/pepsi?quantity=1",
                           headers={"X-Dashboard-Pin": "4321"}).status_code == 200
    finally:
        main.app.state.lan = False


def test_on_the_loopback_no_pin_is_needed(client):
    assert client.post("/api/restock/pepsi?quantity=1").status_code == 200
