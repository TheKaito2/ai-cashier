"""Was the money actually sent?

A static PromptPay QR tells the phone where to pay; it tells the till nothing.
Until now the sale was marked paid when staff looked at the customer's slip,
and fake slips are common enough that banks publish guides on spotting them
(docs/research/04 section 4, ledger H02).

Two verifiers behind one interface.  `NullVerifier` keeps the demo working and
says plainly that nothing was checked.  `HttpSlipVerifier` posts the slip's QR
string to a verification service (EasySlip-style: 18+ Thai banks) and refuses
the sale when the amount does not match.  Which one runs is a setting.

ponytail: the HTTP shape follows EasySlip's public docs; other services need a
subclass that maps their response.  Bank webhooks (tag-30 merchant accounts)
are the next step up and need no slip at all.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SlipResult:
    ok: bool
    checked: bool                # False = accepted without verification
    reason: str = ""
    paid_amount: float | None = None
    reference: str | None = None


class NullVerifier:
    name = "none"

    def verify(self, slip_qr: str | None, expected_amount: float) -> SlipResult:
        return SlipResult(ok=True, checked=False,
                          reason="no slip verifier configured - accepted on staff's word")


class HttpSlipVerifier:
    """POST the slip QR to a verification API and compare the amount."""

    name = "http"
    AMOUNT_TOLERANCE = 0.01

    def __init__(self, url: str, token: str = "", timeout: float = 8.0, session=None):
        import requests
        self.url, self.token, self.timeout = url, token, timeout
        self.session = session or requests.Session()

    def verify(self, slip_qr: str | None, expected_amount: float) -> SlipResult:
        if not slip_qr:
            return SlipResult(False, True, "no slip presented - scan the customer's transfer slip")
        try:
            r = self.session.post(self.url, json={"payload": slip_qr},
                                  headers={"Authorization": f"Bearer {self.token}"} if self.token else {},
                                  timeout=self.timeout)
            body = r.json()
        except Exception as e:                       # network, bad JSON
            return SlipResult(False, True, f"slip service unreachable: {e}")
        if r.status_code != 200 or body.get("status") not in (200, "success", None):
            return SlipResult(False, True, f"slip rejected by verifier: {body.get('message', r.status_code)}")
        data = body.get("data", body)
        amount = data.get("amount")
        amount = float(amount.get("amount", amount) if isinstance(amount, dict) else amount or 0)
        ref = data.get("transRef") or data.get("reference")
        if abs(amount - expected_amount) > self.AMOUNT_TOLERANCE:
            return SlipResult(False, True, f"slip is for {amount:.2f}, sale is {expected_amount:.2f}",
                              paid_amount=amount, reference=ref)
        return SlipResult(True, True, "slip verified", paid_amount=amount, reference=ref)


def from_settings(settings: dict):
    url = (settings.get("slip_verifier_url") or "").strip()
    if not url:
        return NullVerifier()
    return HttpSlipVerifier(url, settings.get("slip_verifier_token") or "")
