"""
Seed backdated demo data so the "1年前の今日" recall experience is real TODAY,
without waiting a year. Idempotent-ish: pass --reset to wipe the user's entries
first.

    python manage.py seed_demo --email n-honda@nippon-access.co.jp
"""
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

from journal.models import Entry, TradeResult

User = get_user_model()


class Command(BaseCommand):
    help = "Seed backdated demo entries for the core-loop walkthrough."

    def add_arguments(self, parser):
        parser.add_argument("--email", default=None, help="Owner email (defaults to settings.DEV_LOGIN_EMAIL).")
        parser.add_argument("--reset", action="store_true", help="Delete the user's existing entries first.")

    def handle(self, *args, **opts):
        from django.conf import settings

        email = opts["email"] or getattr(settings, "DEV_LOGIN_EMAIL", "dev@example.com")
        user, created = User.objects.get_or_create(
            email=email, defaults={"is_staff": True, "is_superuser": True}
        )
        if created:
            self.stdout.write(f"Created user {email}")

        if opts["reset"]:
            n, _ = Entry.all_objects.filter(owner=user).delete()
            self.stdout.write(f"Deleted {n} existing rows for {email}")

        today = timezone.localdate()

        # 1) The anniversary card: exactly one year ago today, with full pre-registration,
        #    still UNVERIFIED so it also nudges scoring.
        one_year_ago = today.replace(year=today.year - 1)
        anniv = Entry.all_objects.create(
            owner=user,
            title="フジクラを購入",
            body=(
                "生成AI需要は10年以上続くと考え、データセンター向け光ファイバの伸びに賭ける。\n"
                "今日の決断を1年後の自分はどう見るだろうか。"
            ),
            occurred_at=one_year_ago,
            action=Entry.Action.BUY,
            ticker="5803",
            instrument_name="フジクラ",
            hypothesis="生成AI需要は10年以上続き、光ファイバ需要を押し上げる",
            confidence=70,
            falsification="データセンター投資が鈍化し、受注が2四半期連続で減少したら間違い",
            verdict=Entry.Verdict.UNVERIFIED,
            status=Entry.Status.PUBLISHED,
        )

        # 2) Older unverified hypotheses (past the 30-day horizon) to populate "検証待ち".
        Entry.all_objects.create(
            owner=user,
            title="海運株を打診買い",
            body="運賃指数の底打ちを根拠に打診買い。需給は読みにくい。",
            occurred_at=today - timedelta(days=120),
            action=Entry.Action.BUY,
            ticker="9101",
            instrument_name="日本郵船",
            hypothesis="運賃指数は底を打ち、半年で反転する",
            confidence=45,
            falsification="運賃指数がさらに10%下落したら仮説は否定",
            verdict=Entry.Verdict.UNVERIFIED,
            status=Entry.Status.PUBLISHED,
        )

        # 3) A recently-verified entry with a learning + a CONTRADICTORY result
        #    (right call, price fell) to demonstrate the two separate lineages.
        verified = Entry.all_objects.create(
            owner=user,
            title="値上げ期待で食品株",
            body="値上げ浸透で利益率改善を見込む。",
            occurred_at=today - timedelta(days=200),
            action=Entry.Action.BUY,
            ticker="2802",
            instrument_name="味の素",
            hypothesis="値上げが浸透し利益率が改善する",
            confidence=60,
            falsification="競合の安値攻勢でシェアを失ったら否定",
            verdict=Entry.Verdict.HIT,
            verified_at=timezone.now() - timedelta(days=2),
            learning="仮説（利益率改善）は当たった。ただし地合いで株価は下落。意思決定は良くても結果は別物だと再確認。",
            status=Entry.Status.PUBLISHED,
        )
        TradeResult.all_objects.update_or_create(
            entry=verified,
            defaults={
                "owner": user,
                "realized": True,
                "pnl_pct": -8,  # price fell even though the hypothesis was right
                "note": "仮説は当たったが地合いで下落",
            },
        )

        # 4) An old untouched note for the "freshness" source.
        Entry.all_objects.create(
            owner=user,
            title="高配当株のメモ",
            body="配当利回りだけで買うのは危険、という自戒。",
            occurred_at=today - timedelta(days=400),
            action=Entry.Action.NOTE,
            verdict=Entry.Verdict.UNVERIFIED,
            status=Entry.Status.PUBLISHED,
        )

        self.stdout.write(self.style.SUCCESS(
            f"Seeded demo data for {email}. Anniversary entry on {one_year_ago} (=1年前の今日)."
        ))
        self.stdout.write(f"Visit /accounts/dev-login/ then / to see the recall feed (entry #{anniv.pk}).")
