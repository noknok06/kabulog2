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


def test_library_lists_only_owner_published(client, alice, alice_entry):
    """Library shows PUBLISHED records; drafts stay in the compose workspace."""
    Entry.objects.create(owner=alice, body="alice_draft_marker", status=Entry.Status.DRAFT)
    client.force_login(alice)
    body = client.get(reverse("journal:library")).content.decode()
    assert "alice_private_thesis_marker" in body
    assert "alice_draft_marker" not in body


def test_library_excludes_other_users_entries(client, alice, bob):
    """The list version of IDOR: bob's records never appear in alice's library."""
    Entry.objects.create(owner=bob, body="bob_private_marker", status=Entry.Status.PUBLISHED)
    client.force_login(alice)
    body = client.get(reverse("journal:library")).content.decode()
    assert "bob_private_marker" not in body


def test_library_keyword_search(client, alice):
    client.force_login(alice)
    Entry.objects.create(owner=alice, body="円安についての考察", status=Entry.Status.PUBLISHED)
    Entry.objects.create(owner=alice, body="半導体の需要動向", status=Entry.Status.PUBLISHED)
    body = client.get(reverse("journal:library"), {"q": "円安"}).content.decode()
    assert "円安についての考察" in body
    assert "半導体の需要動向" not in body


def test_library_filter_by_action_and_verdict(client, alice):
    client.force_login(alice)
    Entry.objects.create(owner=alice, body="buy_marker", status=Entry.Status.PUBLISHED, action=Entry.Action.BUY)
    Entry.objects.create(owner=alice, body="watch_marker", status=Entry.Status.PUBLISHED, action=Entry.Action.WATCH)
    Entry.objects.create(owner=alice, body="hit_marker", status=Entry.Status.PUBLISHED, verdict=Entry.Verdict.HIT)

    by_action = client.get(reverse("journal:library"), {"action": "buy"}).content.decode()
    assert "buy_marker" in by_action and "watch_marker" not in by_action

    by_verdict = client.get(reverse("journal:library"), {"verdict": "hit"}).content.decode()
    assert "hit_marker" in by_verdict and "buy_marker" not in by_verdict

    # An invalid filter value is ignored rather than erroring or hiding everything.
    ignored = client.get(reverse("journal:library"), {"action": "bogus"}).content.decode()
    assert "buy_marker" in ignored and "watch_marker" in ignored


def test_library_htmx_returns_partial(client, alice, alice_entry):
    """An htmx request gets just the results fragment, not the full chrome."""
    client.force_login(alice)
    resp = client.get(reverse("journal:library"), HTTP_HX_REQUEST="true")
    content = resp.content.decode()
    assert "件の記録" in content          # the results fragment rendered
    assert "<!doctype html>" not in content  # but not the full base.html page


# --- Semantic search (runs on the deterministic fallback embedder) ----------
def test_embedder_fallback_is_deterministic_and_normalized():
    from common.embeddings import EMBEDDING_DIM, embed_documents, embed_query

    v1 = embed_query("円安は続く")
    v2 = embed_query("円安は続く")
    assert v1 == v2                       # deterministic
    assert len(v1) == EMBEDDING_DIM       # matches the column dimension
    assert abs(sum(x * x for x in v1) ** 0.5 - 1.0) < 1e-6  # L2-normalized
    # Different texts give different vectors; batch order is preserved.
    docs = embed_documents(["円安", "半導体"])
    assert docs[0] != docs[1]
    assert embed_documents(["円安"])[0] == docs[0]


def test_publish_sets_embedding(client, alice):
    client.force_login(alice)
    client.post(
        reverse("journal:publish"),
        {"body": "半導体の需要は強い", "occurred_at": "2026-01-01", "action": "note"},
    )
    entry = Entry.objects.for_owner(alice).get()
    assert entry.embedding is not None
    assert len(entry.embedding) == 768


def test_embed_entries_command_backfills(alice):
    from django.core.management import call_command

    Entry.objects.create(owner=alice, body="埋め込み待ちの記録", status=Entry.Status.PUBLISHED)
    assert Entry.all_objects.filter(embedding__isnull=True).count() == 1
    call_command("embed_entries")
    assert Entry.all_objects.filter(embedding__isnull=True).count() == 0


def test_library_semantic_orders_by_similarity(client, alice):
    """Semantic mode ranks the lexically/semantically closer entry first."""
    client.force_login(alice)
    from journal.services.embeddings import embed_entry

    near = Entry.objects.create(owner=alice, body="円安と為替の見通し", status=Entry.Status.PUBLISHED)
    far = Entry.objects.create(owner=alice, body="半導体の設備投資", status=Entry.Status.PUBLISHED)
    embed_entry(near)
    embed_entry(far)

    resp = client.get(reverse("journal:library"), {"q": "円安 為替", "mode": "semantic"})
    body = resp.content.decode()
    assert "意味の近い順" in body
    assert body.index("円安と為替の見通し") < body.index("半導体の設備投資")


def test_library_semantic_is_owner_scoped(client, alice, bob):
    from journal.services.embeddings import embed_entry

    bob_entry = Entry.objects.create(owner=bob, body="bob_semantic_marker 円安", status=Entry.Status.PUBLISHED)
    embed_entry(bob_entry)
    client.force_login(alice)
    body = client.get(reverse("journal:library"), {"q": "円安", "mode": "semantic"}).content.decode()
    assert "bob_semantic_marker" not in body


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
