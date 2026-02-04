// db.gs
var SHEETS = {
  Config: 'Config',
  Users: 'Users',
  QuestionBank: 'QuestionBank',
  ConceptCards: 'ConceptCards',
  LawCards: 'LawCards',
  UserAccess: 'UserAccess',
  TestPlan16: 'TestPlan16',
  TestSets: 'TestSets',
  Attempts: 'Attempts',
  AttemptAnswers: 'AttemptAnswers',
  TagStats: 'TagStats'
};

var HEADERS = {};
HEADERS[SHEETS.Config] = ['key', 'value'];
HEADERS[SHEETS.Users] = ['userKey', 'email', 'displayName', 'createdAt', 'recoveryCode'];
HEADERS[SHEETS.QuestionBank] = [
  'qId', 'segmentId', 'type', 'difficulty',
  'tag1', 'tag2', 'tag3', 'lawTag',
  'revisionFlag', 'conceptId', 'variantGroupId', 'source_ref',
  'imageUrl',
  'stem', 'choiceA', 'choiceB', 'choiceC', 'choiceD', 'choiceE',
  'explainA', 'explainB', 'explainC', 'explainD', 'explainE',
  'correct', 'explainShort', 'explainLong', 'status', 'updatedAt'
];
HEADERS[SHEETS.ConceptCards] = [
  'conceptId', 'tag', 'title', 'summary', 'checklist', 'pitfalls',
  'relatedConcepts', 'updatedAt', 'status'
];
HEADERS[SHEETS.LawCards] = [
  'cardId', 'title', 'dutyHolder', 'numberValue', 'deadline',
  'summary', 'pitfalls', 'tags', 'status'
];
HEADERS[SHEETS.UserAccess] = ['email', 'role', 'managerEmail', 'active', 'updatedAt'];
HEADERS[SHEETS.TestPlan16] = [
  'testIndex', 'label', 'targetSegments', 'questionsPerTest',
  'abilityCount', 'revisionMinCount', 'unlockWeek', 'notes'
];
HEADERS[SHEETS.TestSets] = ['testIndex', 'generatedAt', 'questionIds'];
HEADERS[SHEETS.Attempts] = [
  'attemptId', 'userKey', 'testIndex', 'mode',
  'startedAt', 'endsAt', 'submittedAt',
  'scoreTotal', 'scoreAbility', 'status', 'totalQuestions'
];
HEADERS[SHEETS.AttemptAnswers] = [
  'attemptId', 'qId', 'chosen', 'isCorrect', 'answeredAt',
  'timeSpentSec', 'tag1', 'tag2', 'tag3'
];
HEADERS[SHEETS.TagStats] = ['userKey', 'tag', 'answeredCount', 'correctCount', 'updatedAt'];

function migrateQuestionBankSchema_() {
  var sh = getSheet_(SHEETS.QuestionBank);
  var expected = HEADERS[SHEETS.QuestionBank];
  var lastCol = Math.max(1, sh.getLastColumn());
  var header = sh.getRange(1, 1, 1, lastCol).getValues()[0]
    .map(function(h, i){ return normalizeHeader_(h, i); });

  function sameArray(a, b) {
    if (a.length !== b.length) return false;
    for (var i = 0; i < a.length; i++) if (a[i] !== b[i]) return false;
    return true;
  }

  if (sameArray(header, expected)) {
    return { status: 'ok', updated: false };
  }

  var prev = [
    'qId', 'segmentId', 'type', 'difficulty',
    'tag1', 'tag2', 'tag3', 'lawTag',
    'revisionFlag', 'conceptId', 'variantGroupId', 'source_ref',
    'stem', 'choiceA', 'choiceB', 'choiceC', 'choiceD', 'choiceE',
    'explainA', 'explainB', 'explainC', 'explainD', 'explainE',
    'correct', 'explainShort', 'explainLong', 'status', 'updatedAt'
  ];

  var old = [
    'qId', 'segmentId', 'type', 'difficulty',
    'tag1', 'tag2', 'tag3', 'lawTag',
    'revisionFlag', 'conceptId', 'variantGroupId', 'source_ref',
    'stem', 'choiceA', 'choiceB', 'choiceC', 'choiceD', 'choiceE',
    'correct', 'explainShort', 'explainLong', 'status', 'updatedAt'
  ];

  if (sameArray(header, prev)) {
    // Insert imageUrl before stem to preserve existing data alignment
    var insertImgAt = prev.indexOf('stem') + 1; // 1-based
    sh.insertColumns(insertImgAt, 1);
    sh.getRange(1, 1, 1, expected.length).setValues([expected]);
    return { status: 'ok', updated: true, insertedColumns: 1 };
  }

  if (sameArray(header, old)) {
    // Insert explainA~E before correct, then imageUrl before stem
    var insertExplainAt = old.indexOf('correct') + 1; // 1-based
    sh.insertColumns(insertExplainAt, 5);
    var insertImageAt = old.indexOf('stem') + 1; // 1-based
    sh.insertColumns(insertImageAt, 1);
    sh.getRange(1, 1, 1, expected.length).setValues([expected]);
    return { status: 'ok', updated: true, insertedColumns: 6 };
  }

  return { status: 'manual', message: 'QuestionBank header mismatch. Manual review required.', header: header };
}

function getScriptProps_() {
  return PropertiesService.getScriptProperties();
}

var FALLBACK_DB_ID_ = '1tesaYYXP7hsZFbq03irX_MNGvb_TZyeG609QNOvU6WU';

function getDbId_() {
  return getScriptProps_().getProperty('DB_SPREADSHEET_ID') || FALLBACK_DB_ID_;
}

function setDbId_(id) {
  getScriptProps_().setProperty('DB_SPREADSHEET_ID', id);
}

function getDb_() {
  var id = getDbId_();
  if (!id) {
    throw new Error('DBが未設定です。setup()を実行してください。');
  }
  return SpreadsheetApp.openById(id);
}

function getSheet_(name) {
  var ss = getDb_();
  var sh = ss.getSheetByName(name);
  if (!sh) {
    throw new Error('シートが見つかりません: ' + name);
  }
  return sh;
}

function ensureSheet_(ss, name) {
  var sh = ss.getSheetByName(name);
  if (!sh) sh = ss.insertSheet(name);
  return sh;
}

function setHeaders_(sheet, headers) {
  sheet.clear();
  sheet.getRange(1, 1, 1, headers.length).setValues([headers]);
  sheet.setFrozenRows(1);
}

function readRecords_(sheet) {
  var values = sheet.getDataRange().getValues();
  if (values.length <= 1) return [];
  // Normalize headers to avoid BOM/whitespace mismatches from CSV imports
  var headers = values[0].map(function(h, i){ return normalizeHeader_(h, i); });
  var rows = [];
  for (var i = 1; i < values.length; i++) {
    var row = values[i];
    var obj = {};
    for (var c = 0; c < headers.length; c++) {
      obj[headers[c]] = row[c];
    }
    rows.push(obj);
  }
  return rows;
}

// Remove sample/template rows from QuestionBank (qId like "Q1" or source_ref starts with "SAMPLE-")
function adminDeleteSampleQuestions(dryRun) {
  var sh = getSheet_(SHEETS.QuestionBank);
  var values = sh.getDataRange().getValues();
  if (values.length <= 1) return { deleted: 0, rows: [] };
  var headers = values[0].map(function(h, i){ return normalizeHeader_(h, i); });
  var qIdx = headers.indexOf('qId');
  var srcIdx = headers.indexOf('source_ref');
  if (qIdx < 0) throw new Error('qId header not found');
  if (srcIdx < 0) srcIdx = -1;

  var toDelete = [];
  var qIds = [];
  for (var i = 1; i < values.length; i++) {
    var qId = String(values[i][qIdx] || '').trim();
    var src = srcIdx >= 0 ? String(values[i][srcIdx] || '').trim() : '';
    var isSampleId = /^Q\d+$/.test(qId);
    var isSampleSrc = src.toUpperCase().indexOf('SAMPLE-') === 0;
    if (isSampleId || isSampleSrc) {
      toDelete.push(i + 1); // sheet row number
      qIds.push(qId);
    }
  }

  if (!dryRun) {
    for (var j = toDelete.length - 1; j >= 0; j--) {
      sh.deleteRow(toDelete[j]);
    }
  }

  return { deleted: toDelete.length, qIds: qIds, dryRun: !!dryRun };
}

function appendRows_(sheet, rows) {
  if (!rows || rows.length === 0) return;
  sheet.getRange(sheet.getLastRow() + 1, 1, rows.length, rows[0].length).setValues(rows);
}

function setup(force) {
  if (!force && getDbId_()) {
    return { status: 'exists', id: getDbId_() };
  }
  var today = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyyMMdd');
  var ss = SpreadsheetApp.create('Archi16W_DB_' + today);
  setDbId_(ss.getId());

  // create sheets and headers
  for (var key in SHEETS) {
    var name = SHEETS[key];
    var sh = ensureSheet_(ss, name);
    setHeaders_(sh, HEADERS[name]);
  }

  initConfig_();
  initTestPlan_();
  initSampleData_();

  return { status: 'created', id: ss.getId(), url: ss.getUrl() };
}

function initConfig_() {
  var sh = getSheet_(SHEETS.Config);
  var rows = [
    ['PROGRAM_START_DATE', '2026-04-01'],
    ['EXAM_DATE', '2026-07-20'],
    ['TIME_LIMIT_MINUTES', '30'],
    ['QUESTIONS_PER_TEST', '20'],
    ['ABILITY_PER_TEST', '4'],
    ['MINI_TIME_LIMIT_MINUTES', '30'],
    ['MINI_QUESTIONS_PER_TEST', '10'],
    ['MINI_ABILITY_PER_TEST', '2'],
    ['TRAIN_TIME_LIMIT_MINUTES', '10'],
    ['TRAIN_QUESTIONS_PER_TEST', '10'],
    ['TRAIN_ABILITY_PER_TEST', '0'],
    ['REVISION_RATIO', '0.2'],
    ['SHARED_TESTSET_MODE', 'ON'],
    ['TIMEZONE', 'Asia/Tokyo']
  ];
  appendRows_(sh, rows);
}

function initTestPlan_() {
  var sh = getSheet_(SHEETS.TestPlan16);
  var plan = [
    [1, '第1回 R7 午前(いろは)', 'R7-AM-IROHA', 20, 4, 2, 0, ''],
    [2, '第2回 R7 午前(にほへ)', 'R7-AM-NIHOHE', 20, 4, 2, 1, ''],
    [3, '第3回 R7 午後(いろは)', 'R7-PM-IROHA', 20, 4, 2, 2, ''],
    [4, '第4回 R6 午前(いろは)', 'R6-AM-IROHA', 20, 4, 2, 3, ''],
    [5, '第5回 R6 午前(にほへ)', 'R6-AM-NIHOHE', 20, 4, 2, 4, ''],
    [6, '第6回 R6 午後(いろは)', 'R6-PM-IROHA', 20, 4, 2, 5, ''],
    [7, '第7回 R5 午前(いろは)', 'R5-AM-IROHA', 20, 4, 2, 6, ''],
    [8, '第8回 R5 午前(にほ)', 'R5-AM-NIHO', 20, 4, 2, 7, ''],
    [9, '第9回 R5 午後(いろは)', 'R5-PM-IROHA', 20, 4, 2, 8, ''],
    [10, '第10回 R7 午前(いろは)', 'R7-AM-IROHA', 20, 4, 2, 9, ''],
    [11, '第11回 R7 午前(にほへ)', 'R7-AM-NIHOHE', 20, 4, 2, 10, ''],
    [12, '第12回 R7 午後(いろは)', 'R7-PM-IROHA', 20, 4, 2, 11, ''],
    [13, '第13回 R6 午前(いろは)', 'R6-AM-IROHA', 20, 4, 2, 12, ''],
    [14, '第14回 R6 午前(にほへ)', 'R6-AM-NIHOHE', 20, 4, 2, 13, ''],
    [15, '第15回 R6 午後(いろは)', 'R6-PM-IROHA', 20, 4, 2, 14, ''],
    [16, '第16回 R5 午後(いろは)', 'R5-PM-IROHA', 20, 4, 2, 15, '']
  ];
  appendRows_(sh, plan);
}

function initSampleData_() {
  var qb = getSheet_(SHEETS.QuestionBank);
  var cc = getSheet_(SHEETS.ConceptCards);

  var tags = [
    '構造', '施工', '法規', '環境', '設備',
    '計画', '材料', '力学', '防災', '都市計画',
    '建築史', '意匠', '構法', '積算', '品質管理',
    '建築基準法', '耐火', '省エネ', 'バリアフリー', '工事監理'
  ];

  var now = Utilities.formatDate(new Date(), 'Asia/Tokyo', 'yyyy-MM-dd HH:mm:ss');

  // ConceptCards (sample)
  var conceptRows = [];
  for (var i = 0; i < 5; i++) {
    conceptRows.push([
      'C' + (i + 1), tags[i],
      'コンセプト: ' + tags[i],
      '要点を1〜3行でまとめる',
      'チェック1|チェック2|チェック3',
      'よくあるミス: 典型例',
      '',
      now,
      'published'
    ]);
  }
  appendRows_(cc, conceptRows);

  // QuestionBank (sample)
  var segments = ['R7-AM-IROHA','R7-AM-NIHOHE','R7-PM-IROHA','R6-AM-IROHA','R6-AM-NIHOHE','R6-PM-IROHA','R5-AM-IROHA','R5-AM-NIHO','R5-PM-IROHA'];
  var qRows = [];
  var qId = 1;
  for (var s = 0; s < segments.length; s++) {
    for (var k = 0; k < 4; k++) {
      var t1 = tags[(s + k) % tags.length];
      var t2 = tags[(s + k + 1) % tags.length];
      var t3 = tags[(s + k + 2) % tags.length];
      qRows.push([
        'Q' + (qId++),
        segments[s],
        'knowledge',
        2,
        t1, t2, t3,
        '',
        (k % 3 === 0) ? 1 : 0,
        'C' + ((k % 5) + 1),
        'VG-' + segments[s] + '-' + k,
        'SAMPLE-' + segments[s] + '-' + k,
        '',
        '次のうち正しい記述はどれか（' + t1 + '）',
        '選択肢A', '選択肢B', '選択肢C', '選択肢D', '選択肢E',
        '', '', '', '', '',
        'A',
        '解説（要点）',
        '解説（詳細）',
        'published',
        now
      ]);
    }
  }

  // ability questions
  for (var a = 0; a < 6; a++) {
    var tA = tags[(10 + a) % tags.length];
    qRows.push([
      'QA' + (a + 1),
      'ABILITY',
      'ability',
      3,
      tA, '', '',
      '',
      0,
      'C1',
      'VG-ABILITY-' + a,
      'SAMPLE-ABILITY-' + a,
      '',
      '次のうち最も適切なものはどれか（' + tA + '）',
      '選択肢A', '選択肢B', '選択肢C', '選択肢D', '選択肢E',
      '', '', '', '', '',
      'B',
      '解説（要点）',
      '解説（詳細）',
      'published',
      now
    ]);
  }

  appendRows_(qb, qRows);
}

// === CacheService Helpers ===
var CACHE_TTL_CONFIG = 300;      // 5 minutes
var CACHE_TTL_TESTPLAN = 300;    // 5 minutes
var CACHE_TTL_QUESTIONS = 600;   // 10 minutes

function getCache_() {
  return CacheService.getScriptCache();
}

function getCachedConfig_() {
  var cache = getCache_();
  var cached = cache.get('config_map');
  if (cached) {
    try { return JSON.parse(cached); } catch(e) {}
  }
  var sh = getSheet_(SHEETS.Config);
  var values = sh.getDataRange().getValues();
  var map = {};
  if (values.length > 1) {
    for (var i = 1; i < values.length; i++) {
      var key = normalizeHeader_(values[i][0], 0);
      if (key) map[key] = values[i][1];
    }
  }
  cache.put('config_map', JSON.stringify(map), CACHE_TTL_CONFIG);
  return map;
}

function getCachedTestPlan_() {
  var cache = getCache_();
  var cached = cache.get('testplan_rows');
  if (cached) {
    try { return JSON.parse(cached); } catch(e) {}
  }
  var sh = getSheet_(SHEETS.TestPlan16);
  var values = sh.getDataRange().getValues();
  var headers = HEADERS[SHEETS.TestPlan16];
  var rows = [];
  if (values.length > 1) {
    for (var i = 1; i < values.length; i++) {
      var rowVals = values[i];
      if (String(rowVals[0] || '').trim() === '') continue;
      var obj = {};
      for (var c = 0; c < headers.length; c++) obj[headers[c]] = rowVals[c];
      rows.push(obj);
    }
  }
  cache.put('testplan_rows', JSON.stringify(rows), CACHE_TTL_TESTPLAN);
  return rows;
}

function getCachedQuestions_() {
  var cache = getCache_();
  var cached = cache.get('questions_list');
  if (cached) {
    try { return JSON.parse(cached); } catch(e) {}
  }
  var sh = getSheet_(SHEETS.QuestionBank);
  var values = sh.getDataRange().getValues();
  if (values.length <= 1) { cache.put('questions_list', '[]', CACHE_TTL_QUESTIONS); return []; }
  var headers = values[0].map(function(h, i){ return normalizeHeader_(h, i); });
  var rows = [];
  for (var i = 1; i < values.length; i++) {
    var row = values[i];
    var obj = {};
    for (var c = 0; c < headers.length; c++) obj[headers[c]] = row[c];
    if (obj.status !== 'published') continue;
    rows.push(obj);
  }
  try { cache.put('questions_list', JSON.stringify(rows), CACHE_TTL_QUESTIONS); } catch(e) {}
  return rows;
}

function clearAllCache_() {
  var cache = getCache_();
  cache.removeAll(['config_map', 'testplan_rows', 'questions_list']);
}

