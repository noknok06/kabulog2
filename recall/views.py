"""
Home is the place of RECALL, not a P&L dashboard. Opening it means meeting your
past self. The view asks the engine for ranked cards, renders them, then records
the show (the engine itself stays pure).
"""
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_POST

from common.context_processors import resolve_as_of
from journal.models import Entry

from .models import RecallShownLog
from .services.engine import get_recall_cards, record_shown


@login_required
def home(request):
    as_of = resolve_as_of(request)
    cards = get_recall_cards(request.user, as_of)
    record_shown(request.user, cards, as_of)

    awaiting = (
        Entry.objects.for_owner(request.user)
        .filter(status=Entry.Status.PUBLISHED, verdict=Entry.Verdict.UNVERIFIED)
        .exclude(hypothesis="")
        .count()
    )
    recent = (
        Entry.objects.for_owner(request.user)
        .filter(status=Entry.Status.PUBLISHED)
        .exclude(learning="")
        .order_by("-verified_at")[:5]
    )
    return render(
        request,
        "recall/home.html",
        {"cards": cards, "as_of": as_of, "awaiting_count": awaiting, "recent_learnings": recent},
    )


@require_POST
@login_required
def dismiss(request, pk):
    """'あとで' — log a dismissal so the engine rests this card for the window."""
    entry = get_object_or_404(Entry.objects.for_owner(request.user), pk=pk)
    source = request.POST.get("source", "")
    as_of = resolve_as_of(request)
    RecallShownLog.objects.create(
        owner=request.user, entry=entry, source=source, shown_on=as_of,
        action=RecallShownLog.Action.DISMISSED,
    )
    # Empty 200 → htmx removes the card (hx-swap outerHTML).
    return render(request, "recall/partials/_empty.html")
