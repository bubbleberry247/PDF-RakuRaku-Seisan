# My Claude Skills

Claude Code用のカスタムスキル集

## スキル一覧

### rk10-scenario
KEYENCE RK-10 RPAシナリオ作成のための標準手順

**使用方法:**
```
/rk10-scenario
```

**対象業務:**
- 楽楽精算からのデータ抽出
- Excel転記処理
- RK10 UI操作

## セットアップ

### Mac
```bash
cd ~/Documents
git clone https://github.com/bubbleberry247/my-claude-skills.git

# Claude Code設定（VSCode settings.json）
{
  "claude.skills.paths": [
    "~/Documents/my-claude-skills"
  ]
}
```

### Windows
```powershell
cd C:\Users\okamac\Documents
git clone https://github.com/bubbleberry247/my-claude-skills.git

# Claude Code設定（VSCode settings.json）
{
  "claude.skills.paths": [
    "C:\\Users\\okamac\\Documents\\my-claude-skills"
  ]
}
```

## 更新方法

```bash
cd ~/Documents/my-claude-skills  # Mac
# cd C:\Users\okamac\Documents\my-claude-skills  # Windows
git pull
```

## ディレクトリ構造

```
my-claude-skills/
├── rk10-scenario/          # RK10シナリオ作成スキル
│   ├── skill.md            # スキル定義
│   ├── templates/          # テンプレート
│   └── examples/           # サンプル
└── README.md               # このファイル
```
