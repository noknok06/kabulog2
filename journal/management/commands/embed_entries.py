"""
Backfill embeddings for PUBLISHED entries (e.g. after enabling semantic search
or importing data).

    python manage.py embed_entries          # only entries missing an embedding
    python manage.py embed_entries --all    # recompute every published entry
"""
from django.core.management.base import BaseCommand

from common.embeddings import embed_documents

from journal.models import Entry
from journal.services.embeddings import entry_document


class Command(BaseCommand):
    help = "Compute and store embeddings for published entries."

    def add_arguments(self, parser):
        parser.add_argument("--all", action="store_true", help="Recompute all, not just missing.")
        parser.add_argument("--batch", type=int, default=64, help="Embedding batch size.")

    def handle(self, *args, **opts):
        qs = Entry.all_objects.filter(status=Entry.Status.PUBLISHED)
        if not opts["all"]:
            qs = qs.filter(embedding__isnull=True)
        qs = qs.order_by("pk")

        total = qs.count()
        if not total:
            self.stdout.write("Nothing to embed.")
            return

        done = 0
        batch = opts["batch"]
        ids = list(qs.values_list("pk", flat=True))
        for start in range(0, len(ids), batch):
            chunk = list(Entry.all_objects.filter(pk__in=ids[start : start + batch]))
            vectors = embed_documents([entry_document(e) for e in chunk])
            for entry, vector in zip(chunk, vectors):
                Entry.all_objects.filter(pk=entry.pk).update(embedding=vector)
            done += len(chunk)
            self.stdout.write(f"  embedded {done}/{total}")

        self.stdout.write(self.style.SUCCESS(f"Embedded {done} entries."))
