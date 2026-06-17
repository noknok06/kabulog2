"""
The security spine.

Every model that holds user data inherits ``OwnedModel``. The DEFAULT manager
(``objects``) is the only one views are allowed to use, and the normal query
path goes through ``.for_owner(user)``. This makes IDOR (reading another user's
row by guessing a pk) structurally hard: views never call ``objects.get(pk=...)``
without scoping, and the ``OwnerQuerysetMixin`` enforces it for class-based views.
"""
from django.conf import settings
from django.db import models


class TimeStampedModel(models.Model):
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class OwnedQuerySet(models.QuerySet):
    def for_owner(self, user):
        """Scope to a single owner. The canonical entry point for every read."""
        return self.filter(owner=user)


class OwnedManager(models.Manager.from_queryset(OwnedQuerySet)):
    """Default manager. Views MUST funnel reads through ``.for_owner(request.user)``."""


class OwnedModel(TimeStampedModel):
    owner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="%(class)ss",
        db_index=True,
        editable=False,  # never set from request data; always from request.user
    )

    objects = OwnedManager()          # the only manager views use
    all_objects = models.Manager()    # admin / migrations / tests ONLY — never in views

    class Meta:
        abstract = True
