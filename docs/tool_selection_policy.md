# ブラウザ自動化ツール選択方針

## 基本方針

### Playwright + Python（従来）
- **用途**: 定型RPA処理
- **例**: 楽楽精算登録、PDF処理、フォーム入力の繰り返し
- **理由**: Windows完全対応、既存コード流用可能、実績あり

### agent-browser（Vercel Labs）
- **用途**: AIが判断しながら操作するケース
- **例**:
  - 画面構成が頻繁に変わるサイトの自動化
  - Claude Code で直接ブラウザ操作する対話型タスク
  - 「次に何をすべきか」をAIに判断させる処理
- **特徴**:
  - Rust製高速CLI
  - Accessibility tree + refs でコンテキスト93%削減
  - LLMとの対話ループに最適化
- **リンク**: https://github.com/vercel-labs/agent-browser
- **注意**: Windows非ネイティブ（Node.js fallback）

---

*作成日: 2026-01-12*
