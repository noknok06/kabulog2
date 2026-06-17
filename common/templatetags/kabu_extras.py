"""Small presentation helpers shared across templates."""
from django import template

register = template.Library()


@register.filter
def years_ago(value, as_of):
    """Whole years between a date and the given 'today'. Used for '◯年前の今日'."""
    if not value or not as_of:
        return 0
    years = as_of.year - value.year
    if (as_of.month, as_of.day) < (value.month, value.day):
        years -= 1
    return max(years, 0)


@register.filter
def confidence_label(value):
    """Map a 0-100 confidence to a quiet, non-judgemental band label."""
    if value is None:
        return ""
    if value >= 80:
        return "強い確信"
    if value >= 60:
        return "やや確信"
    if value >= 40:
        return "五分五分"
    if value >= 20:
        return "弱い確信"
    return "ほぼ直感"
