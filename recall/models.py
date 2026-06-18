"""
Recall is STATEFUL. ``RecallShownLog`` records which entry was surfaced as which
kind of card, and on what day, so the engine can avoid repeating the same card
daily and can decay re-shows. This is the only state the recall engine has and
it is plain ORM — no async, no cache layer.
"""
from django.db import models

from common.models import OwnedModel


class RecallShownLog(OwnedModel):
    class Action(models.TextChoices):
        SHOWN = "shown", "表示"
        OPENED = "opened", "開いた"
        DISMISSED = "dismissed", "あとで"
        ACTED = "acted", "対応済"

    entry = models.ForeignKey("journal.Entry", on_delete=models.CASCADE, related_name="recall_shows")
    source = models.CharField(max_length=24)  # anniversary|unverified|semantic|recent_learning|freshness
    shown_on = models.DateField(db_index=True)
    action = models.CharField(max_length=10, choices=Action.choices, default=Action.SHOWN)

    class Meta:
        indexes = [models.Index(fields=["owner", "entry", "source", "shown_on"])]

    def __str__(self):
        return f"{self.source} · entry {self.entry_id} · {self.shown_on}"
