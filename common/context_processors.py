"""
``as_of`` lets us simulate "today" in development so the "1年前の今日" recall
experience is testable without waiting a year. It only honours the override
when DEBUG is on; in production it is always the real local date.
"""
from datetime import date

from django.conf import settings
from django.utils import timezone


def resolve_as_of(request):
    """Return the effective 'today', honouring ?as_of=YYYY-MM-DD only in DEBUG."""
    if settings.DEBUG:
        raw = request.GET.get("as_of")
        if raw:
            try:
                return date.fromisoformat(raw)
            except ValueError:
                pass
    return timezone.localdate()


def as_of_date(request):
    return {"as_of": resolve_as_of(request), "DEBUG": settings.DEBUG}
