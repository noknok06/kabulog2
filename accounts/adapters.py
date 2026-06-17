"""
Adapter stubs. Today they are thin; they exist so signup gating / OIDC claim
mapping can be added later without touching call sites.
"""
from allauth.account.adapter import DefaultAccountAdapter
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter


class AccountAdapter(DefaultAccountAdapter):
    """Local account flows. Extend here to gate signups, map fields, etc."""


class SocialAccountAdapter(DefaultSocialAccountAdapter):
    """Social (Google OIDC, later) flows. Map provider claims to the User here."""
