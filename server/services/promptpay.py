"""A payment QR a Thai banking app will actually open.

Version 3 encoded the string `PAYMENT|68.48|<uuid>`, which is not a payment
instrument - no bank reads it, so the QR on screen was decoration.  This builds
a real EMVCo QR payload with a PromptPay merchant account, which any Thai
banking app recognises and pre-fills with the amount.

Reference: EMVCo "Merchant-Presented Mode" specification, and the Bank of
Thailand PromptPay profile (application id A000000677010111).

The payload is a chain of tag-length-value fields:

    ID (2 digits) | length (2 digits) | value

with a CRC-16/CCITT-FALSE over the whole string, the checksum's own "6304"
header included.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

AID_PROMPTPAY = "A000000677010111"

TAG_FORMAT = "00"
TAG_INITIATION = "01"
TAG_MERCHANT = "29"
TAG_CURRENCY = "53"
TAG_AMOUNT = "54"
TAG_COUNTRY = "58"
TAG_CRC = "63"

CURRENCY_THB = "764"          # ISO 4217 numeric
COUNTRY_TH = "TH"

STATIC = "11"                 # customer types the amount
DYNAMIC = "12"                # amount is in the code


def crc16_ccitt(data: str) -> int:
    """CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, no reflection, no final xor."""
    crc = 0xFFFF
    for byte in data.encode("ascii"):
        crc ^= byte << 8
        for _ in range(8):
            crc = ((crc << 1) ^ 0x1021) & 0xFFFF if crc & 0x8000 else (crc << 1) & 0xFFFF
    return crc


def _field(tag: str, value: str) -> str:
    if len(value) > 99:
        raise ValueError(f"field {tag} is too long for a two-digit length")
    return f"{tag}{len(value):02d}{value}"


def normalise_target(target: str) -> tuple[str, str]:
    """Work out whether this is a phone number, a national ID or an e-wallet.

    Returns (sub-tag, formatted value) for the merchant account field.
    """
    digits = re.sub(r"\D", "", target)
    if len(digits) == 15:
        return "03", digits                                   # e-wallet id
    if len(digits) == 13 and not digits.startswith("0066"):
        return "02", digits                                   # national / tax id
    # a Thai mobile: drop the leading 0, prefix the country code, pad to 13
    if digits.startswith("0066"):
        return "01", digits
    if digits.startswith("66"):
        digits = "00" + digits          # 66812345678 -> 0066812345678
    elif digits.startswith("0"):
        digits = "0066" + digits[1:]
    else:
        digits = "0066" + digits
    if len(digits) != 13:
        raise ValueError(f"{target!r} is not a Thai mobile number, national ID or e-wallet id")
    return "01", digits


def build_payload(target: str, amount: float | None = None) -> str:
    """The string that goes inside the QR image.

    `target` is the shop's PromptPay id - a mobile number, a national/tax id or
    an e-wallet id.  Omit `amount` for a static code the customer types into.
    """
    sub_tag, value = normalise_target(target)
    merchant = _field("00", AID_PROMPTPAY) + _field(sub_tag, value)

    payload = (
        _field(TAG_FORMAT, "01")
        + _field(TAG_INITIATION, DYNAMIC if amount is not None else STATIC)
        + _field(TAG_MERCHANT, merchant)
        + _field(TAG_CURRENCY, CURRENCY_THB)
    )
    if amount is not None:
        if amount <= 0:
            raise ValueError("amount must be positive")
        payload += _field(TAG_AMOUNT, f"{amount:.2f}")
    payload += _field(TAG_COUNTRY, COUNTRY_TH)

    # the CRC covers its own tag and length, so they are appended before hashing
    payload += TAG_CRC + "04"
    return payload + f"{crc16_ccitt(payload):04X}"


# ------------------------------------------------------------------ decoding

@dataclass(frozen=True)
class DecodedPayload:
    fields: dict[str, str]
    crc_ok: bool

    @property
    def amount(self) -> float | None:
        raw = self.fields.get(TAG_AMOUNT)
        return float(raw) if raw else None

    @property
    def target(self) -> str | None:
        merchant = self.fields.get(TAG_MERCHANT)
        if not merchant:
            return None
        inner = parse_fields(merchant)
        return inner.get("01") or inner.get("02") or inner.get("03")

    @property
    def is_promptpay(self) -> bool:
        merchant = self.fields.get(TAG_MERCHANT, "")
        return AID_PROMPTPAY in merchant


def parse_fields(payload: str) -> dict[str, str]:
    """Split a tag-length-value chain into a mapping."""
    fields, i = {}, 0
    while i + 4 <= len(payload):
        tag = payload[i:i + 2]
        try:
            length = int(payload[i + 2:i + 4])
        except ValueError:
            break
        value = payload[i + 4:i + 4 + length]
        if len(value) != length:
            break
        fields[tag] = value
        i += 4 + length
    return fields


def decode(payload: str) -> DecodedPayload:
    """Read a payload back and check its checksum. Used by the tests and by
    anyone verifying a code before it is shown to a customer."""
    body, given = payload[:-4], payload[-4:]
    crc_ok = len(payload) > 8 and f"{crc16_ccitt(body):04X}" == given.upper()
    return DecodedPayload(fields=parse_fields(payload), crc_ok=crc_ok)
