"""
The recall engine — the heart of the core loop.

``get_recall_cards(user, as_of)`` is a PURE, DETERMINISTIC function: the same
(user, as_of) always yields the same ranked list, minus cards recently shown.
It has no side effects — the view records the show afterwards. No async.

Candidate sources and intent:
- anniversary     "◯年前の今日"      — the strongest emotional hook (meeting your past self)
- unverified      "検証待ちの仮説"     — closes the pre-register → verify → learn loop
- recent_learning "最近の学び"         — reinforce a lesson just recorded
- freshness       "ふと思い出す"       — gently resurface an old, untouched note

Semantic similarity (embeddings) is a future 5th source: add a candidate
function + a weight, no redesign.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import timedelta

from journal.models import Entry

from recall.models import RecallShownLog

WEIGHTS = {
    "anniversary": 100,
    "unverified": 70,
    "recent_learning": 40,
    "freshness": 20,
}
REPEAT_WINDOW_DAYS = 14    # rotation window: a card shown on a prior day rests this long
UNVERIFIED_HORIZON_DAYS = 30   # only nudge hypotheses old enough to have an answer
FRESHNESS_MIN_AGE_DAYS = 90
FRESHNESS_SAMPLE = 5


@dataclass
class RecallCard:
    entry: Entry
    source: str
    score: float
    reason: str  # human label, e.g. "1年前の今日"


def _candidates(user, as_of) -> list[RecallCard]:
    qs = Entry.objects.for_owner(user).filter(status=Entry.Status.PUBLISHED)
    out: list[RecallCard] = []

    # 1) anniversary: same month/day in a prior year.
    for e in qs.filter(occurred_at__month=as_of.month, occurred_at__day=as_of.day, occurred_at__lt=as_of):
        years = as_of.year - e.occurred_at.year
        out.append(RecallCard(e, "anniversary", WEIGHTS["anniversary"] + years, f"{years}年前の今日"))

    # 2) unverified hypotheses old enough to have a verdict, oldest first.
    horizon = as_of - timedelta(days=UNVERIFIED_HORIZON_DAYS)
    for e in qs.filter(
        verdict=Entry.Verdict.UNVERIFIED, occurred_at__lte=horizon
    ).exclude(hypothesis="").order_by("occurred_at")[:20]:
        age_days = (as_of - e.occurred_at).days
        out.append(RecallCard(e, "unverified", WEIGHTS["unverified"] + min(age_days / 30, 10), "検証待ちの仮説"))

    # 3) recent learnings (verified in the last 7 days) to reinforce.
    for e in qs.filter(verified_at__date__gte=as_of - timedelta(days=7)).exclude(learning=""):
        out.append(RecallCard(e, "recent_learning", WEIGHTS["recent_learning"], "最近の学び"))

    # 4) freshness: old untouched notes. Deterministic sampling seeded by (user, day).
    fresh_pool = list(
        qs.filter(occurred_at__lte=as_of - timedelta(days=FRESHNESS_MIN_AGE_DAYS)).values_list("pk", flat=True)
    )
    if fresh_pool:
        rng = random.Random(f"{user.pk}:{as_of.toordinal()}")
        picked = rng.sample(fresh_pool, min(FRESHNESS_SAMPLE, len(fresh_pool)))
        for e in qs.filter(pk__in=picked):
            out.append(RecallCard(e, "freshness", WEIGHTS["freshness"], "ふと思い出す"))
    return out


def get_recall_cards(user, as_of, limit=5) -> list[RecallCard]:
    candidates = _candidates(user, as_of)

    # One card per memory: an entry surfaces once, via its strongest source.
    best: dict[int, RecallCard] = {}
    for c in candidates:
        cur = best.get(c.entry.pk)
        if cur is None or c.score > cur.score:
            best[c.entry.pk] = c
    cards = list(best.values())

    # Stateful repeat-avoidance, ENTRY-level, within the window:
    #   - DISMISSED ("あとで") on any day  -> the entry rests
    #   - SHOWN on a PRIOR day            -> rotation (same-day reload stays stable)
    recent = RecallShownLog.objects.for_owner(user).filter(
        shown_on__gte=as_of - timedelta(days=REPEAT_WINDOW_DAYS)
    )
    suppressed = set()
    for s in recent:
        if s.action == RecallShownLog.Action.DISMISSED:
            suppressed.add(s.entry_id)
        elif s.action == RecallShownLog.Action.SHOWN and s.shown_on < as_of:
            suppressed.add(s.entry_id)

    cards = [c for c in cards if c.entry.pk not in suppressed]

    # Deterministic ordering: score desc, then most-recent decision, then id desc.
    cards.sort(key=lambda c: (-c.score, -c.entry.occurred_at.toordinal(), -c.entry.pk))
    return cards[:limit]


def record_shown(user, cards, as_of):
    """Side effect, called by the view after render: log what was surfaced.
    Idempotent per day so reloading home does not pile up duplicate rows."""
    if not cards:
        return
    existing = set(
        RecallShownLog.objects.for_owner(user)
        .filter(shown_on=as_of, entry_id__in=[c.entry.pk for c in cards])
        .values_list("entry_id", "source")
    )
    to_create = [
        RecallShownLog(owner=user, entry=c.entry, source=c.source, shown_on=as_of,
                       action=RecallShownLog.Action.SHOWN)
        for c in cards
        if (c.entry.pk, c.source) not in existing
    ]
    RecallShownLog.objects.bulk_create(to_create)
