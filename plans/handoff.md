# handoff.md（短く・上書き前提）

## Current focus
- MDファイル整理 Phase 1 実装完了

## Done
- AGENTS.md 新規作成（正本・Source of Truth）
- CLAUDE.md を入口版に縮退（192行→37行）
- SessionStart hook で decisions + handoff 自動注入設定

## Next (top 3)
1. plans/decisions.md タグ定義追加
2. sessionstart_load_decisions.ps1 更新（handoff注入追加）
3. statusline.ps1 新規作成（ctx>=70%警告）

## Risks / blockers
- なし

## Verification commands
```bash
# メモリロード確認
/memory

# AGENTS.md がロードされているか確認
```

## Relevant files (full paths)
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\AGENTS.md`
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\CLAUDE.md`
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\plans\decisions.md`
- `C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\.claude\settings.local.json`

## Next change (if current approach fails)
- @AGENTS.md のimportが効かない場合、CLAUDE.mdに直接内容を戻す
