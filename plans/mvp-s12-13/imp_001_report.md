# IMP-001 Report: MVP Scope Verification

- Task ID: IMP-001
- Status: Done
- Summary: Verified all three target files (outlook_save_pdf_and_batch_print.py, tool_config_prod.json, tool_config_test.json) against the MVP fixed scope specification. All settings and code logic match the specification. No code changes were required.
- Changed Files: (none -- all files already conform to the MVP specification)
- Evidence:
  - py_compile: PASSED (no syntax errors in outlook_save_pdf_and_batch_print.py)
  - JSON validation (prod): PASSED (valid JSON, 12 top-level keys, UTF-8 BOM handled via utf-8-sig)
  - JSON validation (test): PASSED (valid JSON, 12 top-level keys, UTF-8 BOM handled via utf-8-sig)
- Risks:
  - JSON config files contain UTF-8 BOM; code already handles this via `utf-8-sig` encoding (line 1800), so no issue at runtime.
  - Code defaults (`enable_zip_processing=True`, `enable_pdf_decryption=True`, `fail_on_url_only_mail=True`) differ from MVP spec, but config files override these to `false` correctly. If config loading fails, the defaults would enable features that should be disabled per MVP scope.
- Next Action: T3 QA can proceed with integration/regression testing. Key test scenarios:
  1. FlagStatus=0 filtering and FlagStatus=2 marking after success
  2. `要確認_` prefix generation when OCR/filename extraction fails
  3. Routing to モビテック/中村/その他 subdirectories
  4. ZIP attachments are skipped (not processed)
  5. Encrypted PDFs are skipped (not decrypted)
  6. URL-only mails are skipped (not treated as errors)

---

## Detailed Verification Matrix

| Spec Item | Config (prod) | Code | Status |
|---|---|---|---|
| save_dir = `\\192.168.1.251\TIC-mainSV\経理\請求書【現場】` | Line 3: exact match | Line 3082: `_resolve_save_dir_with_fallback()` with bracket fallback | MATCH |
| FlagStatus=0 filter | `use_flag_status: true` | Line 3159-3170: filters `flag_status == 0` | MATCH |
| Flag 0->2 on success | `mark_flag_on_success: true` | Line 3452-3460: `it.FlagStatus = 2` | MATCH |
| Print: pdf_copy only | `method: "pdf_copy"` | Code respects `cfg.print.method` | MATCH |
| Naming: `{vendor}_{issue_date}_{amount_comma}_{project}.pdf` | `file_name_template` matches | Line 2692: `_render_template(cfg.rename.file_name_template, values)` | MATCH |
| Naming failure: `要確認_` prefix | N/A (code logic) | Line 695: `_build_review_filename()` produces `要確認_{vendor}_{issue_date}_{amount}_{project}.pdf`; called at line 2722 | MATCH |
| filename_first extraction | `filename_first: true` | Lines 2635-2645: tries filename first, then PDF text | MATCH |
| Routing: モビテック/中村/その他 | Rules defined in config | Lines 503-545: keyword matching with fallback_subdir | MATCH |
| merge disabled | `enabled: false` | Line 3477: `cfg.merge.enabled` guards merge | MATCH |
| ZIP disabled | `enable_zip_processing: false` | Line 3266: skips with `[MVP-SKIP]` log | MATCH |
| Decrypt disabled | `enable_pdf_decryption: false` | Line 2579: skips with `[MVP-SKIP]` log | MATCH |
| URL-only: skip | `fail_on_url_only_mail: false` | Line 3507: only adds to unresolved when `True` | MATCH |
| BOM handling | Files have UTF-8 BOM | Line 1800: `json.loads(path.read_text(encoding="utf-8-sig"))` | MATCH |
