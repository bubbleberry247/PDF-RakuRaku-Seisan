# Video2PDD Decisions Log

## 2026-02-07

### [CODE] Video2PDD v3: Gemini Video Pipeline E2E Success

**What**: Video file as direct input (no PSR/Robin) with Gemini multimodal analysis.
Pipeline: Video -> Phase 1 (Gemini) -> Phase 2-3 (Normalize/Describe) -> Phase 3 (Excel) -> Phase 4 (Python codegen).

**Key implementation decisions**:
- **google-genai SDK v1.62.0** (not Gemini CLI subprocess) for video upload + multimodal prompting
- **Model**: `gemini-2.5-flash` for cost-effective video analysis
- **File upload**: Uses Gemini Files API with wait-until-ACTIVE polling (not wait-while-PROCESSING)
- **Prompt**: Structured JSON output with steps, flow_phases, ambiguities
- **Code generation**: Playwright (web) + pywinauto (desktop) templates with TODO markers
- **API key**: `GEMINI_API_KEY` env var (or `GOOGLE_API_KEY` fallback)

**Files created/modified**:
- `tools/video2pdd/phase1_video.py` - Gemini video analysis + gap flags
- `tools/video2pdd/phase4_codegen.py` - Python automation code generation
- `tools/video2pdd/prompts/video_analysis.txt` - Gemini prompt for structured JSON
- `tools/video2pdd/prompts/video_analysis_audio.txt` - Audio-aware variant
- `tools/video2pdd/event_log.py` - v3 schema extensions (video pipeline fields)
- `tools/video2pdd/main.py` - --video CLI option + video pipeline runner
- `tools/video2pdd/phase2_describe.py` - VIDEO_ACTION_JA templates added

**Bug fixed**: FAILED_PRECONDITION (File not in ACTIVE state)
- Root cause: `str(uploaded.state) == "PROCESSING"` didn't match SDK enum representation
- Fix: Changed to `"ACTIVE" not in str(uploaded.state).upper()` pattern
- Confirmed working by user E2E test

**Verification**: User ran full pipeline from terminal, confirmed "OK" for all 4 phases.

### [CONFIG] Gemini API Key Management

- API key regenerated (previous key exposed in screenshot during debugging session)
- archi-16w training app key updated in Spreadsheet Config sheet
- Key stored via `setx GEMINI_API_KEY` for permanent Windows registry storage
- Claude Code Bash tool spawns new shells, so `set` (temporary) is not sufficient

### [DESIGN] Video Pipeline vs Robin Pipeline Coexistence

- Both pipelines coexist in the same codebase under `tools/video2pdd/`
- CLI uses mutually exclusive group: `--video` vs `--robin-file` vs `--resume`
- `--resume` auto-detects pipeline type from event_log metadata
- event_log v3 schema supports both with `pipeline_type` field
