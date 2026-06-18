"""
銘柄カルテ — per-instrument aggregation over a user's PUBLISHED entries.

A READ-ONLY service: no new tables. It collects every published Entry for one
ticker and computes decision-QUALITY signals — deliberately NOT a P&L
scoreboard. The soul is the DIVERGENCE between decision quality (verdict) and
result (P&L): a hypothesis can be right while the price fell, and that gap is
what we surface.

Owner scoping is structural: every query funnels through
``Entry.objects.for_owner(user)``. A ticker the user has never written about
yields ``None`` (the view turns that into 404), so another user's instruments
are unreachable.
"""
from collections import Counter

from django.db.models import Count, Max, Q

from journal.models import Entry

# Confidence gap (in points) before we whisper a calibration note.
_CALIBRATION_MARGIN = 10


def _published(user):
    return Entry.objects.for_owner(user).filter(status=Entry.Status.PUBLISHED)


def instrument_index(user):
    """Every instrument (keyed by ticker) the user has published about, newest first.

    Returns a list of dicts: ``ticker``, ``name`` (latest non-empty
    ``instrument_name``), ``count``, ``last`` (most recent ``occurred_at``),
    ``awaiting`` (unverified-with-hypothesis count).
    """
    qs = _published(user).exclude(ticker="")
    rows = list(
        qs.values("ticker")
        .annotate(
            count=Count("id"),
            last=Max("occurred_at"),
            awaiting=Count(
                "id",
                filter=Q(verdict=Entry.Verdict.UNVERIFIED) & ~Q(hypothesis=""),
            ),
        )
        .order_by("-last")
    )
    # Latest non-empty display name per ticker: iterate oldest→newest so the most
    # recent name wins.
    name_by_ticker = {}
    for ticker, name in qs.order_by("occurred_at").values_list("ticker", "instrument_name"):
        if name:
            name_by_ticker[ticker] = name
    for row in rows:
        row["name"] = name_by_ticker.get(row["ticker"], "")
    return rows


def _pnl_sign(result):
    """Sign of a result's P&L: amount first, then pct. None when unknown."""
    if result is None:
        return None
    for value in (result.pnl_amount, result.pnl_pct):
        if value is not None:
            if value > 0:
                return 1
            if value < 0:
                return -1
            return 0
    return None


def _avg_confidence(entries):
    vals = [e.confidence for e in entries if e.confidence is not None]
    return (sum(vals) / len(vals)) if vals else None


def _calibration_note(avg_hit, avg_miss):
    """A gentle calibration whisper, only when both groups have confidence data."""
    if avg_hit is None or avg_miss is None:
        return None
    if avg_miss - avg_hit >= _CALIBRATION_MARGIN:
        return "自信過剰の傾向"   # you were more sure on the ones you got wrong
    if avg_hit - avg_miss >= _CALIBRATION_MARGIN:
        return "自信過小の傾向"   # you were less sure on the ones you got right
    return "おおむね較正できている"


def instrument_karte(user, ticker):
    """Aggregate one instrument's published entries into a karte dict, or ``None``.

    ``None`` when the user has no published entries for that ticker — which also
    makes another user's ticker unreachable (owner scoping → 404 in the view).
    """
    entries = list(
        _published(user)
        .filter(ticker=ticker)
        .select_related("result")
        .order_by("-occurred_at", "-created_at")
    )
    if not entries:
        return None

    verdict_counts = Counter(e.verdict for e in entries)
    verified = [e for e in entries if e.verdict != Entry.Verdict.UNVERIFIED]
    hits = [e for e in entries if e.verdict == Entry.Verdict.HIT]
    misses = [e for e in entries if e.verdict == Entry.Verdict.MISS]
    hit_rate = (len(hits) / len(verified)) if verified else None

    awaiting = sum(
        1 for e in entries
        if e.verdict == Entry.Verdict.UNVERIFIED and e.hypothesis
    )

    avg_conf_hit = _avg_confidence(hits)
    avg_conf_miss = _avg_confidence(misses)

    # The soul: where decision quality and result diverged.
    divergence = []
    for e in entries:
        sign = _pnl_sign(getattr(e, "result", None))
        if sign is None:
            continue
        if e.verdict == Entry.Verdict.HIT and sign < 0:
            divergence.append({"entry": e, "label": "当たったが損", "kind": "right_call_wrong_result"})
        elif e.verdict == Entry.Verdict.MISS and sign > 0:
            divergence.append({"entry": e, "label": "外したが得", "kind": "wrong_call_right_result"})

    # Realized P&L — kept deliberately subordinate (a quiet reference line, never
    # the headline). ``None`` when nothing realized so the template can omit it.
    realized_amounts = [
        e.result.pnl_amount
        for e in entries
        if getattr(e, "result", None) and e.result.realized and e.result.pnl_amount is not None
    ]
    realized_pnl = sum(realized_amounts) if realized_amounts else None

    names = [e.instrument_name for e in entries if e.instrument_name]
    occurred = [e.occurred_at for e in entries]
    return {
        "ticker": ticker,
        "name": names[0] if names else "",  # entries are newest-first → latest name wins
        "entries": entries,
        "count": len(entries),
        "first_date": min(occurred),
        "last_date": max(occurred),
        "verdict_counts": verdict_counts,
        "hit_count": len(hits),
        "miss_count": len(misses),
        "partial_count": verdict_counts.get(Entry.Verdict.PARTIAL, 0),
        "unverified_count": verdict_counts.get(Entry.Verdict.UNVERIFIED, 0),
        "verified_count": len(verified),
        "hit_rate": hit_rate,
        "hit_rate_pct": round(hit_rate * 100) if hit_rate is not None else None,
        "awaiting": awaiting,
        "avg_confidence_hit": avg_conf_hit,
        "avg_confidence_miss": avg_conf_miss,
        "calibration_note": _calibration_note(avg_conf_hit, avg_conf_miss),
        "divergence": divergence,
        "divergence_count": len(divergence),
        "realized_pnl": realized_pnl,
        "learnings": [e for e in entries if e.learning],
    }
