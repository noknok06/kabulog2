"""
Forms deliberately split along the product's core seam:

- ``EntryForm``      → the write moment (prose + inline pre-registration).
- ``ScoreForm``      → decision QUALITY only (verdict, learning, calibration).
- ``TradeResultForm``→ RESULT only (P&L). Never submitted with ScoreForm.
"""
from django import forms

from .models import Entry, TradeResult


class EntryForm(forms.ModelForm):
    class Meta:
        model = Entry
        fields = [
            "title",
            "body",
            "occurred_at",
            "action",
            "ticker",
            "instrument_name",
            "hypothesis",
            "confidence",
            "falsification",
        ]
        widgets = {
            "occurred_at": forms.DateInput(attrs={"type": "date"}),
            "body": forms.Textarea(attrs={"class": "compose-body", "rows": 16}),
            "confidence": forms.NumberInput(attrs={"type": "range", "min": 0, "max": 100, "step": 5}),
            "hypothesis": forms.Textarea(attrs={"rows": 2}),
            "falsification": forms.Textarea(attrs={"rows": 2}),
        }


class ScoreForm(forms.ModelForm):
    """Decision quality. Writes ONLY learning-side fields — never the P&L."""

    class Meta:
        model = Entry
        fields = ["verdict", "learning", "learning_confidence_calibration"]
        widgets = {
            "verdict": forms.RadioSelect,
            "learning": forms.Textarea(attrs={"rows": 4}),
        }


class TradeResultForm(forms.ModelForm):
    class Meta:
        model = TradeResult
        fields = [
            "realized",
            "entry_price",
            "exit_price",
            "quantity",
            "pnl_amount",
            "pnl_pct",
            "note",
        ]
