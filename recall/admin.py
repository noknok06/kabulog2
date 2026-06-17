from django.contrib import admin

from .models import RecallShownLog


@admin.register(RecallShownLog)
class RecallShownLogAdmin(admin.ModelAdmin):
    list_display = ("owner", "entry", "source", "shown_on", "action")
    list_filter = ("source", "action")
    date_hierarchy = "shown_on"
