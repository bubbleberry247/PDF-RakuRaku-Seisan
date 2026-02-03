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

## 9. Common Pitfalls

| Pitfall | Solution |
|---------|----------|
| Date serialization failure | Use `toSerializable_()` wrapper |
| `clasp deploy` without `-i` | Always use `-i <deploymentId>` |
| Sheet not found | `ensureSheet_()` with auto-create |
| google.script.run silent failure | Always add `.withFailureHandler()` |
| Success handler gets error object | Check `res._error` in success handler too |
| CSP blocks external scripts | All JS must be inline in index.html |
| 6-minute execution limit | Break long operations, use batch processing |

## 10. Testing / Diagnostics

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
