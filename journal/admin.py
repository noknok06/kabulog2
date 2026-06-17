"""Admin is for development/data inspection only — not the user-facing UI."""
from django.contrib import admin

from .models import Entry, EntryTag, ThemeTag, TradeResult


class TradeResultInline(admin.StackedInline):
    model = TradeResult
    extra = 0


@admin.register(Entry)
class EntryAdmin(admin.ModelAdmin):
    list_display = ("__str__", "owner", "occurred_at", "action", "verdict", "status")
    list_filter = ("status", "verdict", "action")
    search_fields = ("title", "body", "hypothesis", "learning", "ticker")
    date_hierarchy = "occurred_at"
    inlines = [TradeResultInline]


@admin.register(ThemeTag)
class ThemeTagAdmin(admin.ModelAdmin):
    list_display = ("name", "owner", "slug")
    search_fields = ("name",)


admin.site.register(EntryTag)
admin.site.register(TradeResult)
