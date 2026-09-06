"""What the till does when something looks wrong and nobody is standing there.

An attended till can afford to be blunt: it stops, and a member of staff sorts
it out.  An unattended one cannot.  It has to choose a response proportionate to
what is actually at stake, because the alternative - treating every discrepancy
as theft - is both wrong and expensive.

Two facts shape every rule below.

The first is that most self-checkout loss is *accidental*, not malicious
(docs/research/03-market.md, rows M19 and M20).  A shop that accuses on every
mismatch is mostly accusing honest people who made a mistake, which costs more
in goodwill than the shrink it prevents.  That is why the incumbents nudge
rather than accuse (row H04), and why nothing here locks a door: detaining a
customer on a false positive is a far worse outcome than losing a packet of
crisps, and it is not a decision a weight sensor gets to make.

The second is that the value at risk is not constant.  The expected loss from
letting a discrepancy through scales with the price of what might have gone
missing; the cost of interrupting an honest customer does not.  So the response
is graded by baht, not by suspicion, and the shop sets where the line falls.

This module decides only *what response is warranted*.  It performs no action,
touches no database and knows nothing about Qt - so it can be tested exhaustively
and argued about on its own terms.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Trigger(str, Enum):
    """Why the till is unhappy."""
    #: the pan disagrees with what is about to be charged for - something was
    #: added, removed or swapped after it was scanned
    WEIGHT_MISMATCH = "weight_mismatch"
    #: goods were scanned, then taken off the mat, and the sale was never paid
    WALK_AWAY = "walk_away"


class Response(str, Enum):
    """What the till should do about it, in increasing order of intrusion."""
    #: write it to the events table and carry on; nobody is interrupted
    LOG = "log"
    #: say something on screen, phrased as a question and not an accusation
    NUDGE = "nudge"
    #: refuse to complete the sale until it is resolved, and make the till
    #: visible from across the room
    HOLD = "hold"
    #: everything HOLD does, and call a person
    SUPERVISE = "supervise"

    @property
    def calls_a_person(self) -> bool:
        return self is Response.SUPERVISE


@dataclass(frozen=True)
class EscalationPolicy:
    """The shop's own settings.  Off by default, deliberately.

    A till that starts calling for a supervisor the moment it is switched on,
    before anyone has calibrated a scale or measured a threshold, would teach the
    shop to ignore it within a day.
    """
    enabled: bool = False
    #: at or above this much baht at risk, a person is called.  Below it the
    #: till handles the situation itself.  100 is a starting point, not a
    #: measured value - research/experiments.py e6_fusion sweeps the tolerance
    #: that feeds it, and the right number depends on the shop's own basket mix.
    supervise_above_baht: float = 100.0


@dataclass(frozen=True)
class Escalation:
    response: Response
    trigger: Trigger
    value_at_risk: float
    reason: str

    @property
    def blocks_the_sale(self) -> bool:
        """Whether the till should refuse to complete the transaction.

        Not a property of the response tier alone: a walk-away calls for a
        person precisely *because* there is no longer a sale to hold on to.
        """
        return (self.trigger is Trigger.WEIGHT_MISMATCH
                and self.response in (Response.HOLD, Response.SUPERVISE))

    @property
    def calls_a_person(self) -> bool:
        return self.response.calls_a_person

    def __str__(self) -> str:
        return f"{self.trigger.value} -> {self.response.value} (฿{self.value_at_risk:.0f})"


def value_at_risk_for_swap(cart_prices: list[float]) -> float:
    """A swap substitutes one item for another, so the exposure is one item.

    The most expensive thing in the basket is the bound: nobody swaps a label to
    pay *more*.  Using the basket total instead would make a large trolley of
    cheap goods look like a bigger threat than a single bottle of spirits, which
    is backwards.
    """
    return max(cart_prices, default=0.0)


def value_at_risk_for_walk_away(cart_total: float) -> float:
    """Nothing was paid for, so the whole basket is the exposure."""
    return max(cart_total, 0.0)


def decide(trigger: Trigger, value_at_risk: float,
           policy: EscalationPolicy | None = None) -> Escalation:
    """The response a shop should make, given what is at stake.

    A weight mismatch always holds the sale, policy or not: that behaviour
    predates this module and weakening it would let a discrepancy through
    silently.  What the policy adds is whether a person is called as well.
    """
    policy = policy or EscalationPolicy()
    at_risk = max(float(value_at_risk), 0.0)
    over = policy.enabled and at_risk >= policy.supervise_above_baht

    if trigger is Trigger.WEIGHT_MISMATCH:
        if over:
            return Escalation(Response.SUPERVISE, trigger, at_risk,
                              f"the pan disagrees and ฿{at_risk:.0f} is at risk")
        return Escalation(Response.HOLD, trigger, at_risk,
                          "the pan disagrees with the basket")

    # walk-away: the goods are already gone, so holding the sale achieves
    # nothing.  The only useful responses are to say something, or to fetch
    # somebody who can look.
    if not policy.enabled:
        return Escalation(Response.LOG, trigger, at_risk,
                          "unpaid goods left the mat")
    if over:
        return Escalation(Response.SUPERVISE, trigger, at_risk,
                          f"unpaid goods left the mat, ฿{at_risk:.0f} at risk")
    return Escalation(Response.NUDGE, trigger, at_risk,
                      "unpaid goods left the mat")
