"""The payment QR has to be a real payment instrument.

v3 encoded the string "PAYMENT|68.48|<uuid>", which no banking app can read -
the code on screen looked like a way to pay and was decoration.
"""
import pytest

from server.services.promptpay import (build_payload, crc16_ccitt, decode,
                                       normalise_target, parse_fields)


def test_the_checksum_matches_the_published_check_value():
    """CRC-16/CCITT-FALSE of "123456789" is 0x29B1 by definition."""
    assert crc16_ccitt("123456789") == 0x29B1


def test_a_payload_decodes_back_to_what_went_in():
    payload = build_payload("081-234-5678", 68.48)
    d = decode(payload)
    assert d.crc_ok and d.is_promptpay
    assert d.amount == 68.48
    assert d.target == "0066812345678"


def test_the_amount_is_carried_to_the_satang():
    assert decode(build_payload("0812345678", 1234.56)).amount == 1234.56


def test_a_code_with_no_amount_is_marked_static():
    d = decode(build_payload("0812345678"))
    assert d.crc_ok and d.amount is None
    assert d.fields["01"] == "11"          # static: the customer types it


def test_a_code_with_an_amount_is_marked_dynamic():
    assert decode(build_payload("0812345678", 20.0)).fields["01"] == "12"


def test_a_tampered_payload_fails_its_checksum():
    payload = build_payload("0812345678", 20.0)
    tampered = payload.replace("20.00", "10.00")
    assert not decode(tampered).crc_ok


@pytest.mark.parametrize("written", [
    "0812345678", "66812345678", "+66 81 234 5678", "0066812345678", "081 234 5678",
])
def test_every_way_of_writing_one_mobile_number_gives_the_same_id(written):
    assert normalise_target(written) == ("01", "0066812345678")


def test_a_national_id_and_an_ewallet_id_are_recognised():
    assert normalise_target("1234567890123")[0] == "02"
    assert normalise_target("123456789012345")[0] == "03"


@pytest.mark.parametrize("bad", ["12345", "not-a-number", ""])
def test_something_that_is_not_a_promptpay_id_is_refused(bad):
    with pytest.raises(ValueError):
        normalise_target(bad)


def test_a_negative_amount_is_refused():
    with pytest.raises(ValueError):
        build_payload("0812345678", -5.0)


def test_the_required_emvco_fields_are_all_present():
    fields = parse_fields(build_payload("0812345678", 20.0))
    for tag in ("00", "01", "29", "53", "54", "58", "63"):
        assert tag in fields, f"missing EMVCo field {tag}"
    assert fields["53"] == "764" and fields["58"] == "TH"


def test_the_till_refuses_to_show_an_unpayable_code_as_payable(client):
    """Without a configured PromptPay id the payload cannot be paid, and the
    response says so rather than letting the till imply otherwise."""
    payment = client.post("/api/checkout", json={"items": [{"product_id": "pepsi"}]}).json()
    assert payment["payable"] is False
    assert not decode(payment["qr_payload"]).is_promptpay


def test_a_configured_till_produces_a_payable_code(client):
    import server.main as main
    main.db.set_setting("promptpay_id", "0812345678")
    payment = client.post("/api/checkout", json={"items": [{"product_id": "pepsi"}]}).json()
    assert payment["payable"] is True
    d = decode(payment["qr_payload"])
    assert d.crc_ok and d.is_promptpay
    assert d.amount == pytest.approx(round(payment["total"], 2))
