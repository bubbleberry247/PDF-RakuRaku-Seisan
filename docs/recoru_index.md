# レコル（RecoRu）ドキュメント インデックス

## このファイルの目的
レコル関連ドキュメントへのナビゲーション（入口）

## 対象読者
- 全員（レコル関連ドキュメントを探す人）

## 更新ルール
- 新規ディレクトリ/ファイル追加時にこのインデックスも更新

---

## ドキュメント構造

```
docs/
├── recoru_index.md          # ← このファイル（入口）
│
├── domain/recoru/           # 業務ドメイン知識（★正本）
│   ├── README.md            # 目次
│   ├── 00_overview.md       # 概要・用語集
│   ├── 10_kbn_dictionary.md # 勤務区分辞書（最重要）
│   ├── 20_reports_guide.md  # 帳票の見方ガイド
│   ├── 30_application_howto.md # 申請手順ガイド
│   └── 40_edge_cases.md     # 例外ケース集
│
├── runbooks/recoru/         # 運用手順（シナリオ別）
│   └── README.md            # 目次・テンプレート
│
└── assets/recoru/           # 画像・帳票見本
    ├── README.md            # 命名規則・注意事項
    ├── screenshots/         # スクリーンショット
    └── report_samples/      # 帳票見本
```

---

## クイックリンク

### 業務ドメイン知識（最初に読む）

| ドキュメント | 内容 | 優先度 |
|-------------|------|--------|
| [domain/recoru/README.md](./domain/recoru/README.md) | ドメイン知識の目次 | ★★★ |
| [domain/recoru/00_overview.md](./domain/recoru/00_overview.md) | 概要・用語集 | ★★★ |
| [domain/recoru/10_kbn_dictionary.md](./domain/recoru/10_kbn_dictionary.md) | **勤務区分辞書**（最重要） | ★★★ |
| [domain/recoru/20_reports_guide.md](./domain/recoru/20_reports_guide.md) | 帳票の見方 | ★★ |
| [domain/recoru/30_application_howto.md](./domain/recoru/30_application_howto.md) | 申請手順 | ★★ |
| [domain/recoru/40_edge_cases.md](./domain/recoru/40_edge_cases.md) | 例外ケース | ★★ |

### 運用手順（Runbook）

| ドキュメント | 内容 |
|-------------|------|
| [runbooks/recoru/README.md](./runbooks/recoru/README.md) | Runbook目次・テンプレート |
| TBD | S37 レコル公休・有休登録 |
| TBD | S43 TBD |
| TBD | S47 出退勤確認 |

### アセット

| ドキュメント | 内容 |
|-------------|------|
| [assets/recoru/README.md](./assets/recoru/README.md) | 命名規則・注意事項 |
| [assets/recoru/screenshots/](./assets/recoru/screenshots/) | スクリーンショット |
| [assets/recoru/report_samples/](./assets/recoru/report_samples/) | 帳票見本 |

---

## ドメインとRunbookの違い

| 種別 | 書く内容 | 場所 |
|------|---------|------|
| **Domain** | 業務ルール・用語定義・判断基準 | `docs/domain/recoru/` |
| **Runbook** | 操作手順・起動方法・障害対応 | `docs/runbooks/recoru/` |

**ポイント**: 業務ルールはDomainに1箇所だけ書き、RunbookではDomainを参照する

---

## 関連マスタデータ

| マスタ | 正本パス | 用途 |
|--------|---------|------|
| 従業員マスタ | `C:\ProgramData\RK10\Robots\47出退勤確認\config\employee_master.csv` | 従業員情報 |
| 勤務区分マスタ | `C:\ProgramData\RK10\Robots\47出退勤確認\config\kbn_master.csv` | 勤務区分定義 |

---

## 次に埋めるべき項目
1. [ ] Domainドキュメントの内容充実（TBD埋め）
2. [ ] Runbookの作成（シナリオ単位）
3. [ ] アセット（スクリーンショット・帳票見本）の配置
