"""
The learning-centred, deliberately FLAT data model.

Design soul:
- ``Entry`` (free prose) is the only required, durable asset.
- Pre-registration (hypothesis / confidence / falsification) lives INLINE on the
  Entry because the write moment must be one form, one save, one owner check.
- Decision QUALITY (``verdict`` / ``learning``) and RESULT (``TradeResult`` P&L)
  are PHYSICALLY SEPARATE. A hypothesis can be right while the price fell. The
  scoring screen writes only the Entry's learning fields; the result panel writes
  only ``TradeResult``. No code path writes both in one statement.
- ``ticker`` is free text, not an FK to a securities master — we resist the
  gravity of becoming a portfolio manager.
"""
from django.db import models
from django.urls import reverse
from django.utils import timezone

from common.models import OwnedModel


class Entry(OwnedModel):
    class Action(models.TextChoices):
        BUY = "buy", "買い"
        SELL = "sell", "売り"
        HOLD = "hold", "ホールド"
        WATCH = "watch", "ウォッチ"
        NOTE = "note", "メモ"

    class Verdict(models.TextChoices):
        UNVERIFIED = "unverified", "未検証"
        HIT = "hit", "当たった"
        MISS = "miss", "外れた"
        PARTIAL = "partial", "部分的"

    class Status(models.TextChoices):
        DRAFT = "draft", "下書き"
        PUBLISHED = "published", "記録済み"

    # --- The durable asset: free prose. Body is the soul. ---
    title = models.CharField(max_length=200, blank=True)
    body = models.TextField(blank=True)
    # The decision date the user is writing ABOUT (may differ from created_at).
    # Recall keys off THIS, not created_at, so backdated records surface correctly.
    occurred_at = models.DateField(default=timezone.localdate, db_index=True)

    # --- Decision (pre-registration), captured inline at write-time ---
    action = models.CharField(max_length=8, choices=Action.choices, default=Action.NOTE)
    ticker = models.CharField(max_length=20, blank=True)
    instrument_name = models.CharField(max_length=120, blank=True)
    hypothesis = models.TextField("仮説", blank=True)
    confidence = models.PositiveSmallIntegerField("確信度", null=True, blank=True)  # 0-100
    falsification = models.TextField("反証条件", blank=True)

    # --- Verification + learning (decision QUALITY) — separate from RESULT ---
    verdict = models.CharField(
        max_length=12, choices=Verdict.choices, default=Verdict.UNVERIFIED, db_index=True
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    learning = models.TextField("学び", blank=True)
    learning_confidence_calibration = models.SmallIntegerField(null=True, blank=True)

    # --- Lifecycle ---
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True
    )

    tags = models.ManyToManyField("ThemeTag", through="EntryTag", related_name="entries", blank=True)

    # --- Deferred room for semantic search ---
    # from pgvector.django import VectorField
    # embedding = VectorField(dimensions=768, null=True, blank=True)

    class Meta:
        ordering = ("-occurred_at", "-created_at")
        verbose_name = "記録"
        verbose_name_plural = "記録"
        indexes = [
            models.Index(fields=["owner", "occurred_at"]),
            models.Index(fields=["owner", "verdict", "status"]),
        ]

    def __str__(self):
        return self.title or (self.body[:30] if self.body else f"Entry #{self.pk}")

    def get_absolute_url(self):
        return reverse("journal:detail", args=[self.pk])

    @property
    def is_pre_registered(self):
        return bool(self.hypothesis)

    @property
    def awaits_scoring(self):
        return (
            self.status == self.Status.PUBLISHED
            and bool(self.hypothesis)
            and self.verdict == self.Verdict.UNVERIFIED
        )

    @property
    def display_name(self):
        if self.instrument_name and self.ticker:
            return f"{self.instrument_name}（{self.ticker}）"
        return self.instrument_name or self.ticker or ""


class ThemeTag(OwnedModel):
    """A crossing axis for learnings/hypotheses. Owner-scoped."""

    name = models.CharField(max_length=50)
    slug = models.SlugField(max_length=60)

    class Meta:
        ordering = ("name",)
        constraints = [
            models.UniqueConstraint(fields=["owner", "slug"], name="uniq_owner_tag_slug")
        ]

    def __str__(self):
        return self.name


class EntryTag(models.Model):
    """Explicit through table — leaves room for weight / auto-tagging later."""

    entry = models.ForeignKey(Entry, on_delete=models.CASCADE)
    tag = models.ForeignKey(ThemeTag, on_delete=models.CASCADE)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["entry", "tag"], name="uniq_entry_tag")
        ]


class TradeResult(OwnedModel):
    """
    SEPARATE LINEAGE: the result / P&L. Deliberately decoupled from verdict and
    learning so that 'right call, price fell' is representable and visible.
    User-entered numbers — there is no portfolio engine computing them.
    """

    entry = models.OneToOneField(Entry, on_delete=models.CASCADE, related_name="result")
    realized = models.BooleanField(default=False)
    entry_price = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    exit_price = models.DecimalField(max_digits=14, decimal_places=4, null=True, blank=True)
    quantity = models.DecimalField(max_digits=16, decimal_places=4, null=True, blank=True)
    pnl_amount = models.DecimalField(max_digits=16, decimal_places=2, null=True, blank=True)
    pnl_pct = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    note = models.CharField(max_length=200, blank=True)

    class Meta:
        verbose_name = "結果"
        verbose_name_plural = "結果"

    def __str__(self):
        return f"Result for {self.entry_id}"
