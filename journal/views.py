"""
Journal views. Every read funnels through ``Entry.objects.for_owner(request.user)``
so a foreign pk yields 404, never a leak. ``owner`` is always set from
``request.user`` — never from POST data.
"""
import json

from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from common.context_processors import resolve_as_of

from .forms import EntryForm, ScoreForm, TradeResultForm
from .models import Entry, TradeResult

# Never a blank page — offer a question. Deterministic by day so it's stable.
WRITING_PROMPTS = [
    "なぜ買おうと思った？",
    "この仮説は何に基づく？",
    "最悪のケースは何だろう？",
    "半年後に読み返したいことは？",
    "今日、相場で何を感じた？",
    "この判断、1年後の自分はどう見る？",
]


def _todays_prompt(request):
    return WRITING_PROMPTS[resolve_as_of(request).toordinal() % len(WRITING_PROMPTS)]


def _autosave_response(request, entry):
    resp = render(
        request,
        "journal/partials/_autosave_status.html",
        {"saved_at": timezone.localtime()},
    )
    # Tell the client the (possibly new) draft id so the next autosave targets it.
    resp["HX-Trigger"] = json.dumps({"draftSaved": {"id": entry.pk}})
    return resp


@login_required
def compose(request):
    """A fresh writing surface. Surfaces existing drafts for recovery (no auto-load)."""
    drafts = Entry.objects.for_owner(request.user).filter(status=Entry.Status.DRAFT).order_by("-updated_at")
    return render(
        request,
        "journal/compose.html",
        {"form": EntryForm(), "entry": None, "drafts": drafts, "prompt": _todays_prompt(request)},
    )


@login_required
def edit(request, pk):
    entry = get_object_or_404(Entry.objects.for_owner(request.user), pk=pk)
    return render(
        request,
        "journal/compose.html",
        {"form": EntryForm(instance=entry), "entry": entry, "prompt": _todays_prompt(request)},
    )


@require_POST
@login_required
def autosave(request):
    """Quiet auto-save. Creates exactly one draft on first call, then updates it.
    Never publishes."""
    entry_id = request.POST.get("entry_id") or None
    if entry_id:
        instance = get_object_or_404(Entry.objects.for_owner(request.user), pk=entry_id)
    else:
        instance = Entry(owner=request.user, status=Entry.Status.DRAFT)

    form = EntryForm(request.POST, instance=instance)
    if form.is_valid():
        entry = form.save(commit=False)
        entry.owner = request.user
        entry.status = Entry.Status.DRAFT  # autosave is never a publish
        entry.save()
        form.save_m2m()
        return _autosave_response(request, entry)
    return render(request, "journal/partials/_autosave_status.html", {"error": True})


@require_POST
@login_required
def publish(request):
    entry_id = request.POST.get("entry_id") or None
    if entry_id:
        instance = get_object_or_404(Entry.objects.for_owner(request.user), pk=entry_id)
    else:
        instance = Entry(owner=request.user, status=Entry.Status.DRAFT)

    form = EntryForm(request.POST, instance=instance)
    if form.is_valid():
        entry = form.save(commit=False)
        entry.owner = request.user
        if not (entry.body or "").strip():
            form.add_error("body", "本文を書いてから記録してください。")
        else:
            entry.status = Entry.Status.PUBLISHED
            entry.save()
            form.save_m2m()
            return redirect(entry.get_absolute_url())
    drafts = Entry.objects.for_owner(request.user).filter(status=Entry.Status.DRAFT).order_by("-updated_at")
    return render(
        request,
        "journal/compose.html",
        {"form": form, "entry": instance, "drafts": drafts, "prompt": _todays_prompt(request)},
    )


@login_required
def detail(request, pk):
    entry = get_object_or_404(
        Entry.objects.for_owner(request.user).select_related("result"), pk=pk
    )
    return render(
        request,
        "journal/entry_detail.html",
        {"entry": entry, "score_form": ScoreForm(instance=entry), "result_form": TradeResultForm(instance=getattr(entry, "result", None))},
    )


@login_required
def score(request, pk):
    """Decision QUALITY only: verdict + learning. Never touches the P&L."""
    entry = get_object_or_404(Entry.objects.for_owner(request.user), pk=pk)
    if request.method == "POST":
        form = ScoreForm(request.POST, instance=entry)
        if form.is_valid():
            scored = form.save(commit=False)
            if scored.verdict != Entry.Verdict.UNVERIFIED and not scored.verified_at:
                scored.verified_at = timezone.now()
            scored.save()
            if request.htmx:
                resp = render(request, "journal/partials/_score_done.html", {"entry": scored})
                resp["HX-Trigger"] = "recallChanged"
                return resp
            return redirect(entry.get_absolute_url())
    else:
        form = ScoreForm(instance=entry)
    template = "journal/partials/_score_form.html" if request.htmx else "journal/score.html"
    return render(request, template, {"form": form, "entry": entry})


@login_required
def result_edit(request, pk):
    """RESULT only: P&L. Deliberately a separate action from scoring."""
    entry = get_object_or_404(Entry.objects.for_owner(request.user), pk=pk)
    instance = getattr(entry, "result", None) or TradeResult(owner=request.user, entry=entry)
    if request.method == "POST":
        form = TradeResultForm(request.POST, instance=instance)
        if form.is_valid():
            result = form.save(commit=False)
            result.owner = request.user
            result.entry = entry
            result.save()
            if request.htmx:
                return render(
                    request,
                    "journal/partials/_result_panel.html",
                    {"entry": entry, "result": result, "result_form": TradeResultForm(instance=result)},
                )
            return redirect(entry.get_absolute_url())
    else:
        form = TradeResultForm(instance=instance)
    return render(
        request,
        "journal/partials/_result_panel.html",
        {"entry": entry, "result": instance, "result_form": form},
    )
