# kabu-log（カブログ）

投資家の成長OS。**投資管理アプリではなく**、投資判断の「記憶」を蓄積する場所
（投資家版 Day One + Readwise + Obsidian）。

> North Star：10年後の自分が、今日の自分の投資判断を正確に理解できる。

設計の全体像は [`DESIGN.md`](./DESIGN.md) を参照。

## コアループ（このMVPの範囲）

```
書く（仮説・確信度・反証条件を事前登録）
  → 想起エンジンが再浮上（1年前の今日／検証待ちの仮説）
  → 採点・内省（学びを記録。損益とは別系統）
```

## クイックスタート

```bash
cp .env.example .env
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
docker compose up -d db          # Postgres (pgvector/pg16) を host:5433 で起動
python manage.py migrate
python manage.py seed_demo --email you@example.com   # 「1年前の今日」を投入
python manage.py runserver
# → http://127.0.0.1:8000/accounts/dev-login/ でログイン、/ で想起フィード
pytest
```

> 開発DBは PostgreSQL（dev/prod parity のため SQLite は使わない）。
> ローカルは Docker で隔離した専用 Postgres を使う。

## 技術スタック

Django 5.2 / Django Templates / HTMX + 極小 vanilla JS / PostgreSQL（pgvector・日本語全文検索は拡張時に追加）/ django-allauth（dev-login → Google OIDC は設定追加のみ）。

## アプリ構成

| app | 役割 |
|---|---|
| `common` | owner スコープの安全基盤（`OwnedModel`）・共通ユーティリティ |
| `accounts` | カスタム User・allauth・dev-login |
| `journal` | `Entry`（記録＝主資産）・事前登録・検証/学び・`TradeResult`（結果＝別系統） |
| `recall` | 想起エンジン（決定的・ステートフル）・ホーム・`seed_demo` |

セキュリティ：全クエリを `owner=request.user` でスコープし、IDOR を構造的に封鎖。
