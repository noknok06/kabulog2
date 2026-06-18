# kabu-log（カブログ）設計書

> 投資家の成長OS。**投資管理アプリではない。** 投資家版 Day One + Readwise + Obsidian。
> North Star：**10年後の自分が、今日の自分の投資判断を正確に理解できる。**

これは「動くコアループMVP」と一対一で読める簡潔な設計書である。完全な24セクション仕様書は意図的に作らない（ブリーフ：*美しい24枚の仕様書を作ってコアループが一度も気持ちよくならないのが最悪の失敗*）。

---

## 1. プロダクト定義

証券会社は損益を記録する。しかし**思考・感情・仮説・判断・学び**は記録しない。kabu-log は**投資判断の記憶を蓄積する場所**。ユーザーが蓄積するのは銘柄ではなく**学び**。覚えているのは「7203」ではなく「円安恩恵株で失敗した」——この非対称性をデータモデルと情報設計の中心に置く。

## 2. 中核となる思想：結果 ≠ 意思決定の質

- 仮説は正しかったが株価は下落した／仮説は間違っていたが偶然利益が出た——これは日常的に存在する。
- ゆえに**結果（損益）と意思決定の質（学び）を物理的に別フィールドに分離**する。
  - 意思決定の質 → `Entry.verdict` / `Entry.learning` / `Entry.verified_at`（`journal/models.py`）
  - 結果 → 別テーブル `TradeResult`（損益。`Entry`に0..1、別系統）
  - **採点画面は学びフィールドのみ、結果パネルは`TradeResult`のみを書く。同一処理で両方を書かない。**

## 3. キラー機能：判断時点の事前登録

後から書く学びは後知恵バイアスで歪む。だから**買う／売るその瞬間**に軽量・インラインで残す：
- `hypothesis`（反証可能な主張）／`confidence`（0-100, ワンドラッグ）／`falsification`（何が起きたら間違いか）
- すべて `Entry` のインラインフィールド（独立テーブルの銀河にしない）。執筆は1フォーム・1自動保存・1 ownerチェック。

## 4. コアループ（予想 → 結果 → 検証 → 学び）

```
書く（＋事前登録）  →  想起エンジンが再浮上（1年前の今日／検証待ち）  →  採点・内省（学びの記録）
   journal              recall/services/engine.py                       journal score + TradeResult
```
このループが端から端まで気持ちよく動くことを最優先で実装した。

## 5. 情報設計：4モードと「ホーム＝想起」

ホーム＝**想起**（検索の入口ではない）／ライブラリ＝検索・整理／詳細＝学習（投資判断カルテ）／関連グラフ＝探索。
「ホーム→検索→詳細」という管理アプリ導線は作らない。**MVPはホーム（想起）と記録と詳細のみ**。

## 6. データモデル（フラット・学び中心）

| エンティティ | 役割 | 系統 |
|---|---|---|
| `Entry` | 自由なプロセ本文（唯一の必須・耐久資産）＋事前登録＋検証/学び | 主 |
| `ThemeTag`/`EntryTag` | 横断軸（薄いthrough、将来の重み用に席） | 横断 |
| `TradeResult` | 損益（ユーザー入力、自動計算しない） | **結果（別系統）** |
| `RecallShownLog` | 想起の表示済みログ（反復回避の状態） | 想起状態 |

`Entry`に意味検索用の `embedding = VectorField(768)` をコメントで予約（pgvector）。

## 7. 想起エンジン（`recall/services/engine.py`）

- **決定的**：同じ (user, as_of) は同じ並びを返す（freshnessはシード付きRNG、`order_by("?")`不使用）。
- **ステートフル**：`RecallShownLog` で反復回避。前日表示・「あとで」はエントリ単位で休ませ、当日リロードは安定。
- 候補ソースと重み：anniversary(100+年) / unverified(70+経過) / recent_learning(40) / freshness(20)。**1記憶＝1カード**（最強ソースで1回）。
- 再浮上した仮説は**採点（当たった/外れた/未検証）**へ自然に接続し、事前登録→検証→学びのループを閉じる。
- 意味的類似（埋め込み）は**第5の候補ソースとして後付け可能**な形（重み辞書とdataclassが拡張可能）。

## 8. セキュリティとデータ分離（前提条件）

- **owner スコープの徹底**：全ユーザーデータは `common/models.OwnedModel` を継承。通常クエリは `objects.for_owner(user)` を必ず通す。`all_objects` はadmin/migration/test専用。
- **IDOR を構造的に封鎖**：ビューは `get_object_or_404(Model.objects.for_owner(request.user), pk=...)`。他人pkは404（テストで保証）。
- `owner` は `editable=False`、`request.user` から設定（POSTから取らない）。
- 横断機能（想起の候補母集合）も owner スコープ（`recall/services/engine.py` はすべて `for_owner`）。

## 9. 認証

`django-allauth` 導入。email識別のカスタム`User`（`accounts/models.py`）。**今は DEBUG限定の dev-login**（Googleシークレット不要）。`openid_connect` プロバイダは登録済み・未設定で、**Google OIDC は後から `prod.py` の設定ブロックを埋めるだけ**（モデル・ビュー変更なし）。

## 10. デザイン／喜びの原則

知的・静か・落ち着き・長文が読みやすい。セリフ本文、心地よい行長・行間、本物のダークモード（`static/css/app.css`）。
**採用する喜び**：HTMX部分更新・静かな自動保存・下書き復元・View Transitions・確信度ワンドラッグ。
**採用しないダークパターン**：紙吹雪/バッジ/ポイント/ランキング、通知でせっつく、無限スクロール、「連続◯日途切れる」式の喪失不安。ストリークは「最近よく考えていますね」の穏当版のみ。

## 11. 技術スタック

Django 5.2 + DTL（Jinja不採用）+ HTMX/極小vanilla JS（SPA化しない）+ PostgreSQL（Docker, dev/prod parity）。
参照アーキテクチャ5層：プレゼン（views+DTL+HTMX）/ アプリ（想起・カルテ・検索）/ ドメイン（学び中心モデル）/ データ（PG+pgvector+日本語FTS）/ ポータビリティ（Markdown/JSONエクスポート＝真実の源）。

---

## 12. 実装済み（このMVP）

- `accounts`（カスタムUser・dev-login・allauth土台）/ `common`（owner背骨）/ `journal`（Entry・TradeResult・compose/autosave/publish/detail/score/result）/ `recall`（想起エンジン・home・dismiss・seed_demo）。
- テスト15件（owner/IDOR分離・想起の決定性と反復回避）すべてパス。
- `seed_demo` がバックデート投入し「1年前の今日」を待たずに検証可能。

## 13. 後回し（モデルに残した席）

| 項目 | 残した席 |
|---|---|
| 意味検索（埋め込み） | pgvector image＋`VectorField`コメント＋想起の第5ソース枠 |
| ライブラリ（検索/整理） | `Entry` の tags/verdict/status/index 済み、一覧は加算的 |
| 詳細の作り込み・投資家カルテ | 既存フィールド上の読み取りサービスで新テーブル不要（銘柄カルテ実装済み: `journal/services/karte.py`。意思決定の質と結果の乖離を中心に） |
| 継続利用（月次/年次レビュー・Wrapped） | サーバーレンダリング＋必要ならChart.jsアイランド |
| 関連グラフ | JSアイランド（d3/cytoscape）として独立 |
| メディア（画像） | 認可付き配信ビュー＋`Attachment(OwnedModel)`。owner背骨が対応済み |
| マネタイズ（AdSense） | 神聖な面（記録/想起/詳細）には出さない。周縁のみ。疎結合で外せる構造 |
| デプロイ（ConoHa VPS） | `prod.py`・gunicorn/whitenoise ピン・Docker開発→本番 |
| エクスポート（真実の源） | フラットなモデルゆえ直列化容易。`export_journal` 管理コマンドを追加予定 |

---

## 開発・検証手順

```bash
cp .env.example .env                      # ローカル設定（gitignored）
python3 -m venv .venv && . .venv/bin/activate
pip install -r requirements-dev.txt
docker compose up -d db                   # Postgres(pgvector/pg16) host:5433
python manage.py migrate
python manage.py seed_demo --email <you>  # 「1年前の今日」をバックデート投入
python manage.py runserver                # /accounts/dev-login/ → / で想起フィード
pytest                                     # owner/IDOR・想起の決定性
```
