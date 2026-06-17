"""
Data-isolation tests — the security spine. If any of these fail, the product's
core promise (no one sees another user's records) is broken.
"""
import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse

from journal.models import Entry

User = get_user_model()


@pytest.fixture
def alice(db):
    return User.objects.create_user(email="alice@example.com", password="pw")


@pytest.fixture
def bob(db):
    return User.objects.create_user(email="bob@example.com", password="pw")


@pytest.fixture
def alice_entry(alice):
    return Entry.objects.create(
        owner=alice, body="alice_private_thesis_marker", status=Entry.Status.PUBLISHED,
        hypothesis="円安は続く", confidence=60,
    )


def test_for_owner_scopes_queryset(alice, bob, alice_entry):
    assert Entry.objects.for_owner(alice).count() == 1
    assert Entry.objects.for_owner(bob).count() == 0


def test_detail_404_for_non_owner(client, bob, alice_entry):
    client.force_login(bob)
    resp = client.get(reverse("journal:detail", args=[alice_entry.pk]))
    assert resp.status_code == 404  # IDOR is structurally impossible, not a 403 leak


def test_owner_sees_own_detail(client, alice, alice_entry):
    client.force_login(alice)
    resp = client.get(reverse("journal:detail", args=[alice_entry.pk]))
    assert resp.status_code == 200
    assert "alice_private_thesis_marker" in resp.content.decode()


def test_edit_and_score_404_for_non_owner(client, bob, alice_entry):
    client.force_login(bob)
    assert client.get(reverse("journal:edit", args=[alice_entry.pk])).status_code == 404
    assert client.get(reverse("journal:score", args=[alice_entry.pk])).status_code == 404
    assert client.post(reverse("journal:result", args=[alice_entry.pk])).status_code == 404


def test_owner_set_from_request_not_post(client, alice, bob):
    """Even if a forged owner id is posted, the entry belongs to the logged-in user."""
    client.force_login(alice)
    client.post(
        reverse("journal:publish"),
        {"body": "mine", "occurred_at": "2026-01-01", "action": "note", "owner": bob.pk},
    )
    entry = Entry.objects.latest("created_at")
    assert entry.owner == alice


def test_publish_requires_body(client, alice):
    client.force_login(alice)
    resp = client.post(reverse("journal:publish"), {"body": "  ", "occurred_at": "2026-01-01", "action": "note"})
    assert resp.status_code == 200  # re-rendered with error, not created
    assert not Entry.objects.filter(status=Entry.Status.PUBLISHED).exists()


def test_autosave_creates_single_draft_then_updates(client, alice):
    client.force_login(alice)
    url = reverse("journal:autosave")
    r1 = client.post(url, {"body": "draft v1", "occurred_at": "2026-01-01", "action": "note", "entry_id": ""})
    assert r1.status_code == 200
    assert "draftSaved" in r1.headers.get("HX-Trigger", "")
    entry = Entry.objects.get(owner=alice)
    # Second autosave targeting the same id must NOT create a new row.
    client.post(url, {"body": "draft v2", "occurred_at": "2026-01-01", "action": "note", "entry_id": entry.pk})
    assert Entry.objects.filter(owner=alice).count() == 1
    entry.refresh_from_db()
    assert entry.body == "draft v2"
    assert entry.status == Entry.Status.DRAFT


def test_scoring_writes_quality_not_result(client, alice, alice_entry):
    """Scoring sets verdict/learning and verified_at — it never touches P&L."""
    client.force_login(alice)
    client.post(
        reverse("journal:score", args=[alice_entry.pk]),
        {"verdict": Entry.Verdict.HIT, "learning": "仮説は当たった"},
    )
    alice_entry.refresh_from_db()
    assert alice_entry.verdict == Entry.Verdict.HIT
    assert alice_entry.learning == "仮説は当たった"
    assert alice_entry.verified_at is not None
    assert not hasattr(alice_entry, "result") or alice_entry.result is None
