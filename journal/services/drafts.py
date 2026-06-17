"""
Thin draft helpers. Kept separate so the recovery policy has one home if it
grows (e.g. pruning stale empty drafts). MVP keeps it minimal.
"""
from journal.models import Entry


def latest_draft(user):
    return (
        Entry.objects.for_owner(user)
        .filter(status=Entry.Status.DRAFT)
        .order_by("-updated_at")
        .first()
    )


def open_drafts(user):
    return (
        Entry.objects.for_owner(user)
        .filter(status=Entry.Status.DRAFT)
        .order_by("-updated_at")
    )
