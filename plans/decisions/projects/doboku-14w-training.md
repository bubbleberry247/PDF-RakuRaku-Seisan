# doboku-14w-training Project Decisions

## 2026-02-14

### [ARCHITECTURE] Project Overview
- **Source**: Cloned from archi-16w-training (1級建築施工管理技士)
- **Target**: 1級土木施工管理技士 (1st Grade Civil Engineering Management Technician)
- **Exam Date**: 2026年7月5日（日）第一次検定
- **Repository**: `C:\ProgramData\Generative AI\Github\doboku-14w-training`
- **GAS Project ID**: `1giv21Jbc8lSmC8fQ3TDJ6gNP7-nH2m2KnPAYebhd0rK8B65gc0mvFzKS`
- **Deploy URL**: https://script.google.com/macros/s/AKfycbxYGzBsVoGisFV9J8eHglolWSI86UWOWzGRidWKh88bOxNgOMtWkyj_IcKAbj315bj6/exec

### [DATA] Curriculum Structure (TestPlan14)

**Design Decision**: 28 mini-tests, 2-tier structure (main + supplementary)

| Field | Value | Rationale |
|-------|-------|-----------|
| Test count | 28 (14 main + 14 supplementary) | 7 years × 4 segments per year = 28 tests |
| Questions per test | 20 | Total 560 questions ÷ 28 tests = 20q/test |
| Schedule | 14 weeks, 2 tests/week | April 1 → July 5 (exam date) |
| Test ordering | R7 → R1 (newest first) | Latest exam patterns prioritized |

**Schema (TestPlan14)**:
```javascript
HEADERS[SHEETS.TestPlan14] = [
  'testIndex',       // 1〜28
  'label',           // "第1回メイン", "第1回補助"など
  'testType',        // "main" または "supplementary"  ★追加フィールド
  'targetYear',      // "R7", "R6", "R5", "R4", "R3", "R2", "R1"
  'targetSegment',   // "前半" or "後半"
  'questionsPerTest', // 20
  'unlockWeek',      // 1〜14
  'notes'
];
```

**2-Tier Test Structure Rationale**:
- **Main tests**: Core curriculum, must-complete for all users
- **Supplementary tests**: Extra practice for weak areas or advanced learners
- **UI display**: Main tests prioritized on home screen, supplementary shown separately

**Test Ordering (R7→R1)**:
- Week 1: R7前半（main）, R7後半（supplementary）
- Week 2: R6前半（main）, R6後半（supplementary）
- ...
- Week 7: R1前半（main）, R1後半（supplementary）
- Week 8-14: Review cycles (TBD)

### [DATA] Question Bank Structure

**Total Questions**: 560 (7 years × 80 questions/year)

| Year | Questions | Segments | Distribution |
|------|-----------|----------|--------------|
| R7 (2025) | 80 | 前半40 + 後半40 | Week 1 |
| R6 (2024) | 80 | 前半40 + 後半40 | Week 2 |
| R5 (2023) | 80 | 前半40 + 後半40 | Week 3 |
| R4 (2022) | 80 | 前半40 + 後半40 | Week 4 |
| R3 (2021) | 80 | 前半40 + 後半40 | Week 5 |
| R2 (2020) | 80 | 前半40 + 後半40 | Week 6 |
| R1 (2019) | 80 | 前半40 + 後半40 | Week 7 |

**Note**: Each 40-question segment is split into 2 tests of 20 questions each (main + supplementary).

### [PROCESS] Cloning Procedure

**Steps Executed (2026-02-14)**:

1. **Directory copy**:
   ```bash
   cp -r "C:/ProgramData/Generative AI/Github/archi-16w-training" "C:/ProgramData/Generative AI/Github/doboku-14w-training"
   ```

2. **Schema migration** (db.gs):
   - TestPlan16 → TestPlan14
   - Added `testType` field for 2-tier structure
   - Changed database name: `Archi16W_DB_` → `Doboku14W_DB_`

3. **Code updates**:
   - All TestPlan16 references replaced with TestPlan14 (Code.gs, logic.gs, db.gs)
   - Used sed for batch replacement: `sed -i 's/TestPlan16/TestPlan14/g' *.gs`

4. **GAS project creation**:
   ```bash
   cd "C:/ProgramData/Generative AI/Github/doboku-14w-training"
   npx clasp create --title "doboku-14w-training" --type standalone --rootDir src
   ```

5. **clasp push** (auto-confirm):
   ```bash
   echo "y" | npx clasp push
   ```

6. **Manual setup** (via Apps Script editor):
   - Open https://script.google.com/home/projects/1giv21Jbc8lSmC8fQ3TDJ6gNP7-nH2m2KnPAYebhd0rK8B65gc0mvFzKS/edit
   - Function dropdown → "setup" → Run
   - Execution log confirmed: Database created `Doboku14W_DB_20260214`

7. **Web app deployment** (via Apps Script editor):
   - Deploy → New deployment → Web app → Deploy
   - URL confirmed working via curl test

### [ISSUE] Common Pitfalls

| Issue | Cause | Fix |
|-------|-------|-----|
| clasp push interactive prompt | Manifest change requires confirmation | Use `echo "y" | npx clasp push` |
| Database name still shows old project | Hardcoded string not replaced | `sed -i "s/Archi16W_DB_/Doboku14W_DB_/g" db.gs` |
| .clasp.json deleted too early | Removed before clasp create completed | Manually recreate with scriptId from clasp create output |
| setup() function not visible in editor | New functions need browser reload | Press F5, or use search bar to find function |
| checkDatabaseStatus() not appearing | Function pushed but not refreshed | Reload editor (F5), but re-running setup() is safer |

### [TODO] Pending Tasks

- [ ] Populate QuestionBank with R1-R7 past exam data (560 questions)
- [ ] Configure TestPlan14 sheet with 28 test definitions
- [ ] Update UI text: 建築 → 土木 (index.html)
- [ ] Update title and branding (app name, headers)
- [ ] Test main vs supplementary test flow in UI
- [ ] Verify unlock schedule aligns with 14-week timeline

### [REFERENCE] Related Files

- **Source project**: `C:\ProgramData\Generative AI\Github\archi-16w-training`
- **New project**: `C:\ProgramData\Generative AI\Github\doboku-14w-training`
- **Skills**: `.claude/skills/gas-webapp/SKILL.md`
- **Documentation**: `doboku-14w-training/docs/機能紹介.md` (TBD)

### [DATA][CORRECTION] TestPlan14 / QuestionBank Count (Supersedes earlier 28-test draft)

- Supersedes: This file previously mentioned "28 tests" and "560 questions" as a draft.
- Actual implementation: 14 tests (TestPlan14 rows 1-14), 30 questions/test, target segments R7gakkaA .. R1gakkaB.
  - Primary Source: C:\ProgramData\Generative AI\Github\doboku-14w-training\src\db.gs (HEADERS + initTestPlan_())
  - Primary Source: C:\ProgramData\Generative AI\Github\doboku-14w-training\src\Code.gs (action resetTestPlan calls initTestPlan_())
- QuestionBank CSV row count (current data): 682 rows.
  - Primary Source: C:\ProgramData\Generative AI\Github\doboku-14w-training\tools\questionbank_complete.csv

### [DATA][IMAGES] Drive Hosting + Figure-Only Images

- Hosting: Question images are stored in Google Drive (not GitHub), linked by imageUrl using https://lh3.googleusercontent.com/d/{fileId}.
  - Primary Source: C:\ProgramData\Generative AI\Github\doboku-14w-training\src\api.gs (apiAdminUploadImage, apiAdminLinkAllDriveImages, folder name Doboku14W_QuestionBankImages)
- Figure-only crops prepared: 27 PNGs (questions whose stem references "下図")
  - Output dir: C:\ProgramData\Generative AI\Github\PDF-RakuRaku-Seisan\docs\assets\doboku-14w\figures
  - Primary Source: C:\ProgramData\Generative AI\Github\doboku-14w-training\tools\extract_question_figures.py
