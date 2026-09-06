"""An unattended till decides, on its own, whether to interrupt a customer.

That is a decision with a cost on both sides, so every branch of it is pinned
here.  Most self-checkout loss is accidental rather than malicious, which means
a policy that escalates on everything is mostly escalating at honest people -
these tests exist to stop that happening by accident during a refactor.
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from server.services.escalation import (  # noqa: E402
    Escalation, EscalationPolicy, Response, Trigger, decide,
    value_at_risk_for_swap, value_at_risk_for_walk_away)

ON = EscalationPolicy(enabled=True, supervise_above_baht=100.0)


# ------------------------------------------------------------------ defaults

def test_a_shop_that_has_configured_nothing_calls_nobody():
    """A till that starts summoning staff the day it is unboxed gets ignored."""
    assert EscalationPolicy().enabled is False
    assert decide(Trigger.WALK_AWAY, 5000.0).response is Response.LOG


def test_a_weight_mismatch_still_stops_the_sale_even_with_the_policy_off():
    """This behaviour predates the policy; turning escalation off must not
    quietly start letting mismatched baskets through."""
    hold = decide(Trigger.WEIGHT_MISMATCH, 5.0)
    assert hold.response is Response.HOLD
    assert hold.blocks_the_sale
    assert not hold.calls_a_person


# --------------------------------------------------------------- the baht line

def test_a_cheap_walk_away_is_a_nudge_and_an_expensive_one_fetches_someone():
    assert decide(Trigger.WALK_AWAY, 20.0, ON).response is Response.NUDGE
    assert decide(Trigger.WALK_AWAY, 250.0, ON).response is Response.SUPERVISE


def test_the_threshold_is_inclusive_so_the_shop_can_reason_about_it():
    assert decide(Trigger.WALK_AWAY, 99.99, ON).response is Response.NUDGE
    assert decide(Trigger.WALK_AWAY, 100.0, ON).response is Response.SUPERVISE


def test_an_expensive_mismatch_holds_and_also_calls_someone():
    e = decide(Trigger.WEIGHT_MISMATCH, 250.0, ON)
    assert e.response is Response.SUPERVISE
    assert e.blocks_the_sale and e.calls_a_person


def test_a_shop_can_set_the_line_wherever_it_likes():
    strict = EscalationPolicy(enabled=True, supervise_above_baht=0.0)
    assert decide(Trigger.WALK_AWAY, 1.0, strict).response is Response.SUPERVISE
    relaxed = EscalationPolicy(enabled=True, supervise_above_baht=10_000.0)
    assert decide(Trigger.WALK_AWAY, 999.0, relaxed).response is Response.NUDGE


# --------------------------------------------------------- holding a sale open

def test_a_walk_away_never_blocks_a_sale_because_the_goods_are_already_gone():
    for value in (0.0, 50.0, 5000.0):
        e = decide(Trigger.WALK_AWAY, value, ON)
        assert not e.blocks_the_sale, "there is no sale left to hold"
    assert decide(Trigger.WALK_AWAY, 5000.0, ON).calls_a_person


def test_nothing_in_this_module_can_lock_a_door():
    """Detaining a customer on a false positive is worse than the loss it
    prevents, and a weight sensor does not get to make that call."""
    responses = {decide(t, v, ON).response for t in Trigger for v in (0, 50, 10_000)}
    assert responses <= {Response.LOG, Response.NUDGE, Response.HOLD, Response.SUPERVISE}
    assert len(list(Response)) == 4, "a new response tier needs its own ethics argument"


# ------------------------------------------------------------- value at risk

def test_a_swap_risks_one_item_not_the_whole_trolley():
    """Twenty packets of crisps are not a bigger threat than one bottle of
    spirits, and a policy that says otherwise escalates in the wrong places."""
    assert value_at_risk_for_swap([20.0, 22.0, 18.0]) == 22.0
    assert value_at_risk_for_swap([]) == 0.0
    trolley = value_at_risk_for_swap([15.0] * 20)
    bottle = value_at_risk_for_swap([600.0])
    assert bottle > trolley


def test_a_walk_away_risks_everything_that_was_not_paid_for():
    assert value_at_risk_for_walk_away(340.0) == 340.0


@pytest.mark.parametrize("bad", [-1.0, -999.0])
def test_a_negative_exposure_is_treated_as_none(bad):
    assert value_at_risk_for_walk_away(bad) == 0.0
    assert decide(Trigger.WALK_AWAY, bad, ON).value_at_risk == 0.0


def test_the_reason_says_what_happened_in_words_a_shopkeeper_can_read():
    e = decide(Trigger.WALK_AWAY, 250.0, ON)
    assert "unpaid" in e.reason and "250" in e.reason
    assert isinstance(e, Escalation) and "walk_away" in str(e)
