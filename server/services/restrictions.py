"""What Thai law lets a till sell, and when.

Sources: docs/research/01-legal-thailand.md, section 2 (ledger rows L03-L06, L13).

  alcohol  Alcoholic Beverage Control Act (No. 2) B.E. 2568: sale 11:00-24:00
           only (permanent since 29 May 2026), buyer 20+ and sober, seller must
           verify.  Machines may sell only with identity verification under
           Committee rules not yet issued, so an unattended till never completes
           an alcohol sale: a member of staff confirms the ID check.
  tobacco  Tobacco Products Control Act B.E. 2560: no sale under 20, no display,
           no vending or electronic sale.  Staff-only, never shown to customers.

ponytail: hours are a constant, not a setting - the law sets them, not the shop.
Change here when the Royal Gazette does; the docstring cites the notice.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time

ALCOHOL_HOURS = (time(11, 0), time(23, 59, 59))    # 11:00 to midnight
MIN_AGE = 20


@dataclass(frozen=True)
class Gate:
    ok: bool
    reason: str = ""
    needs_staff: bool = False

    def __bool__(self) -> bool:
        return self.ok


def alcohol_hours_open(now: datetime | None = None) -> bool:
    t = (now or datetime.now()).time()
    return ALCOHOL_HOURS[0] <= t <= ALCOHOL_HOURS[1]


def sale_gate(restricted: str, staff_confirmed: bool = False,
              now: datetime | None = None) -> Gate:
    """May this item go into the basket right now?

    `staff_confirmed` means a member of staff has checked the buyer's ID and
    pressed confirm.  The till records that as an override event.
    """
    restricted = (restricted or "none").lower()
    if restricted == "none":
        return Gate(True)
    if restricted == "alcohol":
        if not alcohol_hours_open(now):
            return Gate(False, "alcohol may only be sold 11:00-24:00 (Alcoholic Beverage "
                               "Control Act No. 2 B.E. 2568)")
        if not staff_confirmed:
            return Gate(False, f"alcohol: staff must confirm the buyer is {MIN_AGE}+ and sober",
                        needs_staff=True)
        return Gate(True)
    if restricted == "tobacco":
        if not staff_confirmed:
            return Gate(False, f"tobacco: staff-only sale, buyer must be {MIN_AGE}+ "
                               "(Tobacco Products Control Act B.E. 2560)", needs_staff=True)
        return Gate(True)
    return Gate(False, f"unknown restriction {restricted!r}")


def customer_visible(restricted: str) -> bool:
    """Tobacco may not be displayed, so the customer-facing screens never list it."""
    return (restricted or "none").lower() != "tobacco"
