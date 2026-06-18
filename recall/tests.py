"""
Recall engine tests: determinism, the '1年前の今日' hook, stateful repeat
avoidance, and owner isolation of the candidate pool.
"""
from datetime import date, timedelta

import pytest
from django.contrib.auth import get_user_model

from journal.models import Entry
from journal.services.embeddings import embed_entry
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


# --- Semantic source (runs on the deterministic fallback embedder) ----------
def test_semantic_surfaces_similar_past_thinking(user):
    """The most recent entry anchors a search for older, similar past thinking."""
    anchor = _pub(user, body="円安が続くと考え、輸出関連株に強気。トヨタを買う。", occurred_at=AS_OF)
    similar = _pub(user, body="円安が続くと考え、輸出関連株に注目。トヨタに強気。",
                   occurred_at=AS_OF - timedelta(days=60))
    unrelated = _pub(user, body="半導体の設備投資サイクルのメモ。配当利回りの罠。",
                     occurred_at=AS_OF - timedelta(days=70))
    for e in (anchor, similar, unrelated):
        embed_entry(e)

    cards = {c.entry.pk: c for c in get_recall_cards(user, AS_OF)}
    assert cards[similar.pk].source == "semantic"
    assert cards[similar.pk].reason == "以前も似たことを考えていた"
    # The nearer entry outranks the unrelated one within the semantic source.
    assert cards[unrelated.pk].source == "semantic"
    assert cards[similar.pk].score > cards[unrelated.pk].score
    # The anchor itself is not resurfaced.
    assert anchor.pk not in cards


def test_semantic_skips_too_recent_and_unembedded(user):
    anchor = _pub(user, body="円安と輸出株に強気", occurred_at=AS_OF)
    valid_old = _pub(user, body="円安と輸出株に強気のメモ", occurred_at=AS_OF - timedelta(days=60))
    too_recent = _pub(user, body="円安と輸出株に強気の続き", occurred_at=AS_OF - timedelta(days=5))
    no_embedding = _pub(user, body="円安と輸出株だが未埋め込み", occurred_at=AS_OF - timedelta(days=60))
    for e in (anchor, valid_old, too_recent):
        embed_entry(e)  # no_embedding intentionally left without a vector

    cards = {c.entry.pk: c for c in get_recall_cards(user, AS_OF)}
    assert cards[valid_old.pk].source == "semantic"
    assert too_recent.pk not in cards     # within SEMANTIC_MIN_AGE_DAYS
    assert no_embedding.pk not in cards    # has no embedding


def test_semantic_source_is_owner_scoped(user, db):
    other = User.objects.create_user(email="other2@example.com", password="pw")
    o_anchor = _pub(other, body="円安と輸出株", occurred_at=AS_OF)
    o_old = _pub(other, body="円安と輸出株のメモ", occurred_at=AS_OF - timedelta(days=60))
    a = _pub(user, body="円安と輸出株", occurred_at=AS_OF)
    old = _pub(user, body="円安と輸出株のメモ", occurred_at=AS_OF - timedelta(days=60))
    for e in (o_anchor, o_old, a, old):
        embed_entry(e)

    pks = {c.entry.pk for c in get_recall_cards(user, AS_OF)}
    assert old.pk in pks
    assert o_old.pk not in pks and o_anchor.pk not in pks


def test_record_shown_is_idempotent_per_day(user):
    e = _pub(user, body="anniv", occurred_at=AS_OF.replace(year=2025), hypothesis="h")
    cards = get_recall_cards(user, AS_OF)
    record_shown(user, cards, AS_OF)
    record_shown(user, cards, AS_OF)
    assert RecallShownLog.objects.filter(entry=e, shown_on=AS_OF).count() == 1
