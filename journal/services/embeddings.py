"""
Turn an Entry into a vector and persist it.

The embedding is computed from the entry's prose (title / body / hypothesis /
learning) — the semantic content, not the bookkeeping fields. We write it with a
queryset ``update`` so saving the vector never re-triggers a model ``save`` (and
never re-enters this path).
"""
from __future__ import annotations

from common.embeddings import embed_documents

from journal.models import Entry


def entry_document(entry: Entry) -> str:
    parts = [entry.title, entry.body, entry.hypothesis, entry.learning]
    return "\n".join(p for p in parts if p).strip()


def embed_entry(entry: Entry) -> None:
    """Compute and store ``entry.embedding`` from its current prose."""
    vector = embed_documents([entry_document(entry)])[0]
    Entry.all_objects.filter(pk=entry.pk).update(embedding=vector)
    entry.embedding = vector
