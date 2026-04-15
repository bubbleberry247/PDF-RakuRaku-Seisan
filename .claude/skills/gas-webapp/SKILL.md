---
name: gas-webapp
description: Use when working on GAS (Google Apps Script) web apps — clasp push, clasp deploy -i, doGet, HtmlService, google.script.run, Spreadsheet as DB, SPA development and deployment
context: fork
---

# GAS Webapp (SPA) Skill

## Overview
Google Apps Script + HTML single-page application pattern.
Backend: GAS (.gs files) with Spreadsheet as DB.
Frontend: Single `index.html` with inline CSS/JS.
Deploy: `clasp push && clasp deploy -i <deploymentId>`.

Extracted from archi-16w training app (@37 versions, production-proven).

---

## 1. Project Structure

```
project/
├── .clasp.json          # { "scriptId": "...", "rootDir": "src" }
├── src/
│   ├── Code.gs          # doGet/doPost entry point + admin endpoints
│   ├── api.gs           # Public API functions (called by google.script.run)
│   ├── logic.gs         # Business logic (private functions with _ suffix)
│   ├── db.gs            # Sheet names, headers, CRUD helpers
│   └── index.html       # SPA (HTML + CSS + JS all inline)
└── .clasp.json
```

## 2. Architecture Pattern

```
Browser (index.html)
  ↓ google.script.run.apiFunctionName(args, clientUserKey)
GAS Server
  ├── api.gs      → public entry points (set __clientUserKey, call logic)
  ├── logic.gs    → business rules (private _ functions)
  └── db.gs       → Spreadsheet CRUD (SHEETS, HEADERS, readRecords_, appendRows_)
  ↓
Google Spreadsheet (database)
```

### Key Design Decisions
- **Single HTML file**: GAS serves one `index.html` via `HtmlService.createHtmlOutputFromFile('index')`
- **No frameworks**: Vanilla JS only (GAS has strict CSP, no CDN imports)
- **Spreadsheet as DB**: Each "table" = one sheet. Headers defined in `db.gs`
- **State in localStorage**: Client-side state persistence (interrupted tests, user key)

## 3. Code.gs Pattern (Entry Point)

```javascript
function doGet(e) {
  var action = (e && e.parameter && e.parameter.action) ? e.parameter.action : '';

  // Admin/diagnostic endpoints (URL parameter-based)
  if (action === 'setupDb') {
    // ... return JSON
  }

  // Default: serve SPA
  return HtmlService.createHtmlOutputFromFile('index')
    .setTitle('App Title')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}
```

**Admin endpoints**: Use `?action=xxx` URL parameters for diagnostic/setup tasks.
These are accessible without UI, useful for debugging.

## 4. db.gs Pattern (Data Layer)

```javascript
var SHEETS = {
  Config: 'Config',
  Users: 'Users',
  // ... add sheets as needed
};

var HEADERS = {};
HEADERS[SHEETS.Config] = ['key', 'value'];
HEADERS[SHEETS.Users] = ['userKey', 'email', 'displayName', 'createdAt', 'recoveryCode'];
```

### Essential Helper Functions
- `getDb_()` — Get spreadsheet by stored ID
- `getSheet_(name)` — Get or create sheet, ensure headers
- `readRecords_(sheet)` — Read all rows as objects (header-keyed)
- `appendRows_(sheet, rows)` — Append 2D array
- `updateAttempt_(index, updates)` — Update specific row by index
- `upsertByKey_(sheetName, keyField, rowObj)` — Insert or update by key

### DB ID Storage
```javascript
function setDbId_(id) {
  PropertiesService.getScriptProperties().setProperty('DB_SPREADSHEET_ID', id);
}
function getDbId_() {
  return PropertiesService.getScriptProperties().getProperty('DB_SPREADSHEET_ID');
}
```
First-time setup: `?action=setupDb&dbId=SPREADSHEET_ID`

## 5. api.gs Pattern (Public API)

### Convention
- Function names: `apiXxx(arg1, arg2, clientUserKey)` — last arg is always clientUserKey
- Set global: `__clientUserKey = clientUserKey || '';`
- Return object: `{ field1: ..., field2: ... }` on success
- Return error: `{ _error: true, message: '...' }` on failure
- Wrap in try/catch

```javascript
function apiStartSomething(param1, clientUserKey) {
  __clientUserKey = clientUserKey || '';
  try {
    var userCtx = getUserContext_();
    requireActiveUser_(userCtx);
    var user = ensureUser_(userCtx.userKey, userCtx.email, userCtx.displayName);

    // ... business logic ...

    return { success: true, data: result };
  } catch (e) {
    return { _error: true, message: 'Error: ' + String(e.message || e) };
  }
}
```

### Date Serialization (CRITICAL)
GAS `google.script.run` cannot serialize Date objects. Use global serializer:

```javascript
function toSerializable_(obj) {
  if (obj === null || obj === undefined) return obj;
  if (obj instanceof Date) return obj.toISOString();
  if (Array.isArray(obj)) return obj.map(toSerializable_);
  if (typeof obj === 'object') {
    var result = {};
    for (var k in obj) {
      if (obj.hasOwnProperty(k)) result[k] = toSerializable_(obj[k]);
    }
    return result;
  }
  return obj;
}
```

Wrap return values: `return toSerializable_(result);`

## 6. Hybrid Auth Pattern (Google-optional)

```
Access
├── Google email available → auto-login (userKey = email)
├── localStorage has key   → auto-login (userKey = UUID)
└── Neither (new user)
    ├── Name input only → server generates recovery code (6-digit)
    ├── localStorage save → auto-login after
    └── Other device: enter recovery code → link as same user
```

### Server-side (logic.gs)
```javascript
var __clientUserKey = '';  // Global, set per request (GAS is single-threaded)

function getUserContext_() {
  var email = getActiveEmail_();
  if (email) return { userKey: email, authMethod: 'google', ... };

  var cuk = __clientUserKey || '';
  if (cuk) {
    var existing = findUserByKey_(cuk);
    if (existing) return { userKey: existing.userKey, authMethod: 'code', ... };
  }

  return { userKey: '', authMethod: 'none' };
}
```

### Client-side (index.html)
```javascript
var USER_KEY = localStorage.getItem('userKey') || '';

function callApi(funcName, args) {
  args.push(USER_KEY);  // Always append clientUserKey as last arg
  return new Promise(function(resolve, reject) {
    google.script.run
      .withSuccessHandler(resolve)
      .withFailureHandler(reject)
      [funcName].apply(null, args);
  });
}
```

### Recovery Code
- Characters: `ABCDEFGHJKLMNPQRSTUVWXYZ23456789` (no I/O/0/1)
- Length: 6 characters
- Uniqueness: check before save (recursive retry)
- Case-insensitive matching

## 7. Frontend SPA Pattern (index.html)

### State Management
```javascript
var state = {
  screen: 'home',       // Current screen
  questions: [],         // Current test questions
  currentIndex: 0,       // Current question index
  answers: {},           // { qId: 'A' }
  selected: {},          // { qId: 'B' } (in-progress selection)
  answered: {},          // { qId: true }
  timerId: null,         // Timer interval ID
};
```

### Screen Routing
```javascript
function showScreen(name) {
  state.screen = name;
  render();
}

function render() {
  switch (state.screen) {
    case 'home': renderHome(); break;
    case 'test': renderTest(); break;
    case 'result': renderResult(); break;
  }
}
```

### Interrupt/Resume (localStorage)
```javascript
function saveToStorage() {
  var data = { answers: state.answers, currentIndex: state.currentIndex, ... };
  localStorage.setItem('interrupted_' + mode + '_' + key, JSON.stringify(data));
}

function checkInterrupted(mode, key) {
  return !!localStorage.getItem('interrupted_' + mode + '_' + key);
}

function clearInterrupted(mode, key) {
  localStorage.removeItem('interrupted_' + mode + '_' + key);
}
```

## 8. Deployment

### clasp Setup
```bash
# Login
clasp login

# Clone existing project
clasp clone <scriptId> --rootDir src

# Push changes
clasp push

# Deploy (MUST use -i to update existing URL)
clasp deploy -i <deploymentId>
```

### CRITICAL: Always use `-i` flag
```bash
# CORRECT (updates existing URL)
clasp deploy -i AKfycbx...

# WRONG (creates NEW deployment = NEW URL)
clasp deploy
```

### Config via URL
```
?action=updateConfig&key=TIME_LIMIT_MINUTES&value=60
```

## 9. Project Cloning

### When to Clone
Clone an existing GAS webapp when creating a similar app with structural changes:
- Different data schema (e.g., TestPlan16 → TestPlan14)
- Different curriculum structure (e.g., 16 weeks → 14 weeks)
- Domain-specific customization (e.g., 建築 → 土木)

### Cloning Procedure

**Step 1: Directory Copy**
```bash
cp -r "/path/to/source-project" "/path/to/new-project"
cd "/path/to/new-project"
```

**Step 2: Schema Migration (db.gs)**

Identify schema changes needed:
- Sheet name changes (e.g., `TestPlan16` → `TestPlan14`)
- Field additions/removals
- Database naming (e.g., `Archi16W_DB_` → `Doboku14W_DB_`)

```javascript
// Before
var SHEETS = {
  TestPlan16: 'TestPlan16',
};
HEADERS[SHEETS.TestPlan16] = ['testIndex', 'label', 'unlockWeek'];

// After
var SHEETS = {
  TestPlan14: 'TestPlan14',
};
HEADERS[SHEETS.TestPlan14] = ['testIndex', 'label', 'testType', 'unlockWeek'];
```

**Step 3: Code Updates**

Batch replace references using sed:
```bash
# Update sheet references
sed -i 's/TestPlan16/TestPlan14/g' src/*.gs

# Update database name prefix
sed -i 's/Archi16W_DB_/Doboku14W_DB_/g' src/db.gs

# Update project-specific strings
sed -i 's/建築施工管理技士/土木施工管理技士/g' src/index.html
```

**Step 4: Create New GAS Project**
```bash
# Remove old .clasp.json (avoid conflicts)
rm .clasp.json

# Create new GAS project
npx clasp create --title "new-project-name" --type standalone --rootDir src
```

This generates `.clasp.json` with new `scriptId`:
```json
{"scriptId":"1giv21Jbc8lSmC8fQ3TDJ6gNP7-nH2m2KnPAYebhd0rK8B65gc0mvFzKS","rootDir":"src"}
```

**Step 5: Push Code (Auto-confirm)**
```bash
# Auto-confirm manifest changes
echo "y" | npx clasp push
```

**Step 6: Run setup() via Apps Script Editor**

Browser-based setup (recommended for first-time):

1. Open GAS editor: `https://script.google.com/home/projects/<scriptId>/edit`
2. Locate function dropdown:
   - Top toolbar: `apiGetHome ▼` (or any visible function)
   - Click dropdown → Search for `setup`
   - Or use Ctrl+F in left sidebar to find `setup` function
3. Select `setup` from dropdown
4. Click **Run** button (▶️ icon)
5. Authorize if prompted
6. Check execution log (Ctrl+Enter or View → Logs)
   - Look for: `Database created: Doboku14W_DB_YYYYMMDD`

**Step 7: Deploy Web App**

1. In GAS editor: **Deploy** → **New deployment**
2. Type: **Web app**
3. Execute as: **Me**
4. Who has access: **Anyone** (or specific domain)
5. Click **Deploy**
6. Copy deployment URL (format: `https://script.google.com/macros/s/<deploymentId>/exec`)

**Step 8: Verify Deployment**
```bash
# Test with curl
curl "https://script.google.com/macros/s/<deploymentId>/exec"

# Should return HTML content (index.html)
```

### Common Cloning Pitfalls

| Issue | Cause | Fix |
|-------|-------|-----|
| clasp push interactive prompt | Manifest change requires confirmation | Use `echo "y" \| npx clasp push` |
| Database name not updated | Hardcoded string in db.gs | `sed -i "s/OldName_DB_/NewName_DB_/g" db.gs` |
| .clasp.json deleted too early | Removed before clasp create | Manually create with scriptId from clasp output |
| setup() not visible in editor | Function not loaded after push | Press F5 to reload editor |
| checkDatabase() not appearing | New function needs refresh | Reload editor, or re-run setup() |
| Schema references missed | Not all files updated | Use sed for batch replacement across `*.gs` files |

### Apps Script Editor Tips (for Beginners)

**Finding Functions:**
- **Function dropdown**: Top toolbar shows current function (e.g., `apiGetHome ▼`)
- **Dropdown search**: Click dropdown → type function name → select from list
- **Sidebar search**: Ctrl+F in left file tree to find function definitions
- **After push**: Always reload (F5) to see new functions

**Running Functions:**
- Select function from dropdown → Click **Run** (▶️) button
- First run requires authorization (click **Review permissions**)
- Check **Execution log** (Ctrl+Enter) for output and errors

**Deployment:**
- **New deployment**: Creates new URL (use for new projects)
- **Manage deployments**: Update existing URL (use `-i` flag with clasp)
- **Test deployments**: Use `?action=xxx` URL parameters for diagnostics

## 10. Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| Date serialization failure | Use `toSerializable_()` wrapper |
| `clasp deploy` without `-i` | Always use `-i <deploymentId>` |
| Sheet not found | `ensureSheet_()` with auto-create |
| google.script.run silent failure | Always add `.withFailureHandler()` |
| Success handler gets error object | Check `res._error` in success handler too |
| CSP blocks external scripts | All JS must be inline in index.html |
| 6-minute execution limit | Break long operations, use batch processing |
| Python/headless script redirected to Google login | `"access": "ANYONE"` = Googleサインイン必須。匿名アクセスには `"access": "ANYONE_ANONYMOUS"` を使う |

## 11. Testing / Diagnostics

### Admin Endpoints (via URL parameters)
- `?action=setupDb&dbId=xxx` — Link spreadsheet
- `?action=updateConfig&key=xxx&value=yyy` — Update config
- `?action=clearTestSets` — Clear cached data
- `?action=diagTestGen&testIndex=1` — Diagnostic info

### Quick Verification Checklist
1. Open deploy URL → SPA loads
2. Registration flow works (name → recovery code)
3. Core feature works (create/read/update cycle)
4. Interrupt → resume works (close tab → reopen)
5. Admin endpoints return JSON

## References
- Production app: `C:\ProgramData\Generative AI\Github\archi-16w-training\src\`
- Deploy URL pattern: `https://script.google.com/macros/s/<deploymentId>/exec`
- Spreadsheet as DB: Each sheet = one table, row 1 = headers
- Cloning example: doboku-14w-training (cloned from archi-16w-training, 2026-02-14)

---

## Gotchas
- `clasp deploy`（-iなし）→ 新URL生成 = 既存ユーザーアクセス不可。**必ず `-i <deploymentId>`**
- `access: "ANYONE"` は Googleサインイン必須。匿名アクセスには `"ANYONE_ANONYMOUS"` を使う
- Date型は `google.script.run` でシリアライズ不可 → 返り値は必ず `toSerializable_()` でラップ
- UI要素の表示/非表示を変更する場合、**全画面・全状態**を列挙してからコードを書く（条件付き非表示は意図しない要素まで巻き込む）
- 新しいAPI呼び出し関数は必ず既存関数（doStartTest等）のエラーハンドリングをコピーしてから書き始める（successハンドラでも `res._error` チェック必須）
