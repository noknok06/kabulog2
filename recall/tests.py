"""
Recall engine tests: determinism, the '1年前の今日' hook, stateful repeat
avoidance, and owner isolation of the candidate pool.
"""
from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model

from journal.models import Entry
from recall.models import RecallShownLog
from recall.services.engine import get_recall_cards, record_shown

User = get_user_model()
AS_OF = date(2026, 6, 17)


@pytest.fixture
def user(db):
    return User.objects.create_user(email="u@example.com", password="pw")


def _pub(owner, **kw):
    kw.setdefault("status", Entry.Status.PUBLISHED)
    return Entry.objects.create(owner=owner, **kw)


def test_anniversary_card_surfaces_and_leads(user):
    _pub(user, body="フジクラ", occurred_at=AS_OF.replace(year=2025),
         hypothesis="AI需要は続く", confidence=70)
    cards = get_recall_cards(user, AS_OF)
    assert cards, "anniversary entry should surface"
    assert cards[0].source == "anniversary"
    assert cards[0].reason == "1年前の今日"


def test_engine_is_deterministic(user):
    for i in range(6):
        _pub(user, body=f"old note {i}", occurred_at=AS_OF - timedelta(days=200 + i))
    _pub(user, body="anniv", occurred_at=AS_OF.replace(year=2024), hypothesis="h")
    first = [(c.entry.pk, c.source) for c in get_recall_cards(user, AS_OF)]
    second = [(c.entry.pk, c.source) for c in get_recall_cards(user, AS_OF)]
    assert first == second


def test_unverified_hypothesis_surfaces_for_scoring(user):
    e = _pub(user, body="海運", occurred_at=AS_OF - timedelta(days=120),
             hypothesis="運賃は反転する", confidence=45, verdict=Entry.Verdict.UNVERIFIED)
    sources = {c.source: c for c in get_recall_cards(user, AS_OF)}
    assert "unverified" in sources
    assert sources["unverified"].entry.pk == e.pk


def test_prior_day_show_is_suppressed_but_same_day_is_stable(user):
    e = _pub(user, body="anniv", occurred_at=AS_OF.replace(year=2025), hypothesis="h")
    # Shown yesterday -> rests (rotation).
    RecallShownLog.objects.create(owner=user, entry=e, source="anniversary",
                                  shown_on=AS_OF - timedelta(days=1),
                                  action=RecallShownLog.Action.SHOWN)
    assert all(c.entry.pk != e.pk for c in get_recall_cards(user, AS_OF))

    # Shown TODAY -> still visible today (same-day reload is stable).
    e2 = _pub(user, body="anniv2", occurred_at=AS_OF.replace(year=2024), hypothesis="h2")
    RecallShownLog.objects.create(owner=user, entry=e2, source="anniversary",
                                  shown_on=AS_OF, action=RecallShownLog.Action.SHOWN)
    assert any(c.entry.pk == e2.pk for c in get_recall_cards(user, AS_OF))


def test_dismiss_suppresses_within_window(user):
    e = _pub(user, body="anniv", occurred_at=AS_OF.replace(year=2025), hypothesis="h")
    RecallShownLog.objects.create(owner=user, entry=e, source="anniversary",
                                  shown_on=AS_OF, action=RecallShownLog.Action.DISMISSED)
    assert all(c.entry.pk != e.pk for c in get_recall_cards(user, AS_OF))


def test_candidate_pool_is_owner_scoped(user, db):
    other = User.objects.create_user(email="other@example.com", password="pw")
    _pub(other, body="not yours", occurred_at=AS_OF.replace(year=2025), hypothesis="secret")
    assert get_recall_cards(user, AS_OF) == []


def test_record_shown_is_idempotent_per_day(user):
    e = _pub(user, body="anniv", occurred_at=AS_OF.replace(year=2025), hypothesis="h")
    cards = get_recall_cards(user, AS_OF)
    record_shown(user, cards, AS_OF)
    record_shown(user, cards, AS_OF)
    assert RecallShownLog.objects.filter(entry=e, shown_on=AS_OF).count() == 1
