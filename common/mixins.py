"""Reusable view-layer guards for owner scoping."""
from django.contrib.auth.mixins import LoginRequiredMixin


class OwnerQuerysetMixin(LoginRequiredMixin):
    """
    For class-based views over an ``OwnedModel``.

    ``get_queryset`` returns only the current user's rows, so ``get_object``
    (which filters that queryset by pk) raises 404 — never leaks — on someone
    else's row. There is no code path here that can return a foreign object.
    """

    def get_queryset(self):
        return self.model.objects.for_owner(self.request.user)


class OwnerCreateMixin:
    """Set ``owner`` from the authenticated user, never from POST data."""

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)
