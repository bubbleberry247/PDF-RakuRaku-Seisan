// Code.gs

// Warm-up function for time-based trigger (keeps GAS instance warm, avoids cold start)
function warmUp() {
  getCachedConfig_();
  getCachedTestPlan_();
  return { ok: true, ts: new Date().toISOString() };
}

function doGet(e) {
  var action = (e && e.parameter && e.parameter.action) ? e.parameter.action : '';

  if (action === 'setupDb') {
    var dbId = (e && e.parameter && e.parameter.dbId) ? e.parameter.dbId : '';
    if (dbId) {
      setDbId_(dbId);
      return ContentService.createTextOutput(JSON.stringify({ ok: true, dbId: dbId }))
        .setMimeType(ContentService.MimeType.JSON);
    }
    return ContentService.createTextOutput(JSON.stringify({ ok: false, error: 'dbId required' }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  if (action === 'diagMock') {
    return ContentService.createTextOutput(JSON.stringify(diagMock_()))
      .setMimeType(ContentService.MimeType.JSON);
  }

  if (action === 'clearStaleAttempts') {
    return ContentService.createTextOutput(JSON.stringify(clearStaleAttempts_()))
      .setMimeType(ContentService.MimeType.JSON);
  }

  if (action === 'autoTag') {
    return ContentService.createTextOutput(JSON.stringify(autoTagQuestions()))
      .setMimeType(ContentService.MimeType.JSON);
  }

  if (action === 'createImageFolder') {
    var folder = DriveApp.createFolder('QuestionBankImages');
    folder.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
    return ContentService.createTextOutput(JSON.stringify({
      ok: true,
      folderId: folder.getId(),
      folderUrl: folder.getUrl()
    })).setMimeType(ContentService.MimeType.JSON);
  }

  if (action === 'diagTestGen') {
    try {
      var ti = Number(e.parameter.testIndex || 1);
      var config = getConfigMap_();
      var plan = getTestPlanByIndex_(ti);
      var qb = readQuestionBank_();
      var published = qb.filter(function(q){ return q.status === 'published'; });
      var valid = published.filter(function(q){ return isValidChoiceQuestion_(q); });
      var segs = plan ? String(plan.targetSegments || '').split(',').map(function(s){ return s.trim(); }).filter(Boolean) : [];
      var segMatch = valid.filter(function(q){ return q.type === 'knowledge' && segs.indexOf(q.segmentId) >= 0; });
      var abilityMatch = valid.filter(function(q){ return q.type === 'ability'; });
      // Type breakdown
      var types = {};
      valid.forEach(function(q){ var t = String(q.type || 'EMPTY'); types[t] = (types[t] || 0) + 1; });
      // SegmentId breakdown
      var segIds = {};
      valid.forEach(function(q){ var s = String(q.segmentId || 'EMPTY'); segIds[s] = (segIds[s] || 0) + 1; });
      // Sample invalid
      var invalidSamples = published.filter(function(q){ return !isValidChoiceQuestion_(q); }).slice(0, 3).map(function(q){
        return { qId: q.qId, correct: q.correct, choiceA: String(q.choiceA||'').substring(0,20), choiceD: String(q.choiceD||'').substring(0,20), choiceE: String(q.choiceE||'').substring(0,20) };
      });
      // TestSets cache
      var tsRows = readRecords_(getSheet_(SHEETS.TestSets));
      var tsForIndex = tsRows.filter(function(r){ return String(r.testIndex) === String(ti); });
      return ContentService.createTextOutput(JSON.stringify({
        ok: true, testIndex: ti,
        plan: plan,
        totalQB: qb.length, published: published.length, valid: valid.length,
        targetSegs: segs, segMatch: segMatch.length, abilityMatch: abilityMatch.length,
        typeBreakdown: types, segIdBreakdown: segIds,
        invalidSamples: invalidSamples,
        testSetsCache: tsForIndex
      })).setMimeType(ContentService.MimeType.JSON);
    } catch (err) {
      return ContentService.createTextOutput(JSON.stringify({ ok: false, error: err.message, stack: err.stack }))
        .setMimeType(ContentService.MimeType.JSON);
    }
  }

  if (action === 'clearTestSets') {
    var sh = getSheet_(SHEETS.TestSets);
    var rows = sh.getDataRange().getValues();
    var cleared = rows.length - 1;
    if (cleared > 0) {
      sh.getRange(2, 1, cleared, sh.getLastColumn()).clearContent();
    }
    clearAllCache_();
    return ContentService.createTextOutput(JSON.stringify({ ok: true, cleared: cleared }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  if (action === 'clearCache') {
    clearAllCache_();
    return ContentService.createTextOutput(JSON.stringify({ ok: true, message: 'Cache cleared' }))
      .setMimeType(ContentService.MimeType.JSON);
  }

  if (action === 'diagWeek') {
    clearAllCache_();
    var config = getConfigMap_();
    var tz = getConfigValue_(config, 'TIMEZONE', 'Asia/Tokyo');
    var startDate = getConfigValue_(config, 'PROGRAM_START_DATE', '2026-04-01');
    var weeks = weeksSinceStart_(startDate, tz);
    var now = new Date();
    var plans = getTestPlanRows_();
    var thisWeekTests = plans.filter(function(p) { return isThisWeeksTest_(p, weeks); });
    return ContentService.createTextOutput(JSON.stringify({
      ok: true,
      now: now.toISOString(),
      startDate: startDate,
      weeksSinceStart: weeks,
      thisWeekTestIndexes: thisWeekTests.map(function(p) { return p.testIndex; }),
      allPlanUnlockWeeks: plans.map(function(p) { return { testIndex: p.testIndex, unlockWeek: p.unlockWeek }; })
    })).setMimeType(ContentService.MimeType.JSON);
  }

  if (action === 'warmUp') {
    var result = warmUp();
    return ContentService.createTextOutput(JSON.stringify(result))
      .setMimeType(ContentService.MimeType.JSON);
  }

  if (action === 'resetTestPlan') {
    try {
      var sh = getSheet_(SHEETS.TestPlan16);
      sh.clear();
      setHeaders_(sh, HEADERS[SHEETS.TestPlan16]);
      initTestPlan_();
      return ContentService.createTextOutput(JSON.stringify({ ok: true, message: 'TestPlan16 reset to defaults (20q/4ability)' }))
        .setMimeType(ContentService.MimeType.JSON);
    } catch (err) {
      return ContentService.createTextOutput(JSON.stringify({ ok: false, error: err.message }))
        .setMimeType(ContentService.MimeType.JSON);
    }
  }

  if (action === 'diagFieldStats') {
    try {
      var plans = getTestPlanRows_();
      var fs = computeFieldStats_('diag');
      return ContentService.createTextOutput(JSON.stringify({ ok: true, plans: plans, fieldStats: fs }))
        .setMimeType(ContentService.MimeType.JSON);
    } catch (err) {
      return ContentService.createTextOutput(JSON.stringify({ ok: false, error: err.message, stack: err.stack }))
        .setMimeType(ContentService.MimeType.JSON);
    }
  }

  if (action === 'linkGitHub') {
    return ContentService.createTextOutput(JSON.stringify(linkGitHubImages()))
      .setMimeType(ContentService.MimeType.JSON);
  }

  // Diagnose weekly chart / last7Days issue
  if (action === 'diagWeekly') {
    try {
      var email = (e && e.parameter && e.parameter.email) ? e.parameter.email : '';
      var config = getConfigMap_();
      var tz = getConfigValue_(config, 'TIMEZONE', 'Asia/Tokyo');
      var allAttempts = readRecords_(getSheet_(SHEETS.Attempts));
      var users = readRecords_(getSheet_(SHEETS.Users));
      var targetUser = email ? users.find(function(u){ return u.email === email; }) : users[0];
      if (!targetUser) {
        return ContentService.createTextOutput(JSON.stringify({ ok: false, error: 'No user found' }))
          .setMimeType(ContentService.MimeType.JSON);
      }
      var userAttempts = allAttempts.filter(function(r){ return r.userKey === targetUser.userKey; });
      var progress = buildProgress_(userAttempts, 16, tz, 8);
      var now = getNow_();
      var cutoff = new Date(now.getTime() - 7 * 24 * 60 * 60 * 1000);
      // Debug: sample attempts with timestamps
      var sampleAttempts = userAttempts.slice(0, 10).map(function(a){
        return {
          status: a.status,
          mode: a.mode,
          startedAt: a.startedAt,
          submittedAt: a.submittedAt
        };
      });
      return ContentService.createTextOutput(JSON.stringify({
        ok: true,
        now: now.toISOString(),
        cutoff: cutoff.toISOString(),
        tz: tz,
        user: { userKey: targetUser.userKey, email: targetUser.email },
        totalAttempts: userAttempts.length,
        submittedCount: userAttempts.filter(function(a){ return a.status === 'submitted'; }).length,
        progress: progress,
        sampleAttempts: sampleAttempts
      })).setMimeType(ContentService.MimeType.JSON);
    } catch (err) {
      return ContentService.createTextOutput(JSON.stringify({ ok: false, error: err.message, stack: err.stack }))
        .setMimeType(ContentService.MimeType.JSON);
    }
  }

  if (action === 'checkUserAccess') {
    var email = (e && e.parameter && e.parameter.email) ? e.parameter.email : '';
    if (!email) {
      return ContentService.createTextOutput(JSON.stringify({ ok: false, error: 'email required' }))
        .setMimeType(ContentService.MimeType.JSON);
    }
    var sh = getSheet_(SHEETS.UserAccess);
    var rows = readRecords_(sh);
    var found = rows.filter(function(r) { return String(r.email || '').toLowerCase() === email.toLowerCase(); });
    return ContentService.createTextOutput(JSON.stringify({
      ok: true,
      email: email,
      found: found.length > 0,
      records: found,
      totalUsers: rows.length
    })).setMimeType(ContentService.MimeType.JSON);
  }

  if (action === 'updateConfig') {
    var key = (e && e.parameter && e.parameter.key) ? e.parameter.key : '';
    var value = (e && e.parameter && e.parameter.value) ? e.parameter.value : '';
    if (!key) {
      return ContentService.createTextOutput(JSON.stringify({ ok: false, error: 'key required' }))
        .setMimeType(ContentService.MimeType.JSON);
    }
    try {
      var sh = getSheet_(SHEETS.Config);
      var data = sh.getDataRange().getValues();
      var updated = false;
      for (var i = 1; i < data.length; i++) {
        if (String(data[i][0]).trim() === key) {
          sh.getRange(i + 1, 2).setValue(value);
          updated = true;
          break;
        }
      }
      if (!updated) {
        appendRows_(sh, [[key, value]]);
        updated = true;
      }
      clearAllCache_();
      return ContentService.createTextOutput(JSON.stringify({ ok: true, key: key, value: value, updated: updated }))
        .setMimeType(ContentService.MimeType.JSON);
    } catch (err) {
      return ContentService.createTextOutput(JSON.stringify({ ok: false, error: err.message }))
        .setMimeType(ContentService.MimeType.JSON);
    }
  }

  if (action === 'diagStem') {
    var doFix = (e && e.parameter && e.parameter.fix === 'true');
    try {
      var result = diagFixQuestionBank(doFix);
      return ContentService.createTextOutput(JSON.stringify(result))
        .setMimeType(ContentService.MimeType.JSON);
    } catch (err) {
      return ContentService.createTextOutput(JSON.stringify({ ok: false, error: err.message }))
        .setMimeType(ContentService.MimeType.JSON);
    }
  }

  if (action === 'linkImages') {
    var folderId = (e && e.parameter && e.parameter.folderId) ? e.parameter.folderId : '';
    if (!folderId) {
      return ContentService.createTextOutput(JSON.stringify({ ok: false, error: 'folderId required' }))
        .setMimeType(ContentService.MimeType.JSON);
    }
    return ContentService.createTextOutput(JSON.stringify(apiAdminLinkDriveImages(folderId)))
      .setMimeType(ContentService.MimeType.JSON);
  }

  return HtmlService.createHtmlOutputFromFile('index')
    .setTitle('1級建設管理技士　第一次演習')
    .setXFrameOptionsMode(HtmlService.XFrameOptionsMode.ALLOWALL)
    .addMetaTag('viewport', 'width=device-width, initial-scale=1');
}

function doPost(e) {
  try {
    var body = JSON.parse(e.postData.contents);
    var action = body.action || '';

    if (action === 'uploadImage') {
      var folderId = body.folderId;
      var fileName = body.fileName;
      var base64Data = body.data;
      var mimeType = body.mimeType || 'image/png';

      var folder = DriveApp.getFolderById(folderId);
      var blob = Utilities.newBlob(Utilities.base64Decode(base64Data), mimeType, fileName);
      var file = folder.createFile(blob);
      file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);

      return ContentService.createTextOutput(JSON.stringify({
        ok: true,
        fileId: file.getId(),
        fileName: fileName,
        url: 'https://lh3.googleusercontent.com/d/' + file.getId()
      })).setMimeType(ContentService.MimeType.JSON);
    }

    return ContentService.createTextOutput(JSON.stringify({ ok: false, error: 'Unknown action' }))
      .setMimeType(ContentService.MimeType.JSON);
  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({ ok: false, error: err.message }))
      .setMimeType(ContentService.MimeType.JSON);
  }
}

function diagMock_() {
  var qb = readRecords_(getSheet_(SHEETS.QuestionBank));
  var attempts = readRecords_(getSheet_(SHEETS.Attempts));

  // Question counts by year/part
  var qCounts = {};
  var validCounts = {};
  qb.forEach(function(q) {
    var qId = String(q.qId || '');
    var match = qId.match(/^(R\d)-(AM|PM)-/);
    if (!match) return;
    var key = match[1] + '-' + match[2];
    qCounts[key] = (qCounts[key] || 0) + 1;
    if (q.status === 'published' && isValidChoiceQuestion_(q)) {
      validCounts[key] = (validCounts[key] || 0) + 1;
    }
  });

  // Sample R7-AM questions for debugging
  var r7amSamples = qb.filter(function(q) {
    return String(q.qId || '').indexOf('R7-AM-') === 0;
  }).slice(0, 3).map(function(q) {
    return {
      qId: q.qId,
      status: q.status,
      correct: q.correct,
      choiceA: String(q.choiceA || '').substring(0, 30),
      choiceB: String(q.choiceB || '').substring(0, 30),
      choiceC: String(q.choiceC || '').substring(0, 30),
      choiceD: String(q.choiceD || '').substring(0, 30),
      isValid: isValidChoiceQuestion_(q)
    };
  });

  // Active attempts (status = 'started')
  var activeAttempts = attempts.filter(function(a) {
    return a.status === 'started';
  }).map(function(a) {
    return {
      attemptId: a.attemptId,
      userKey: a.userKey,
      testIndex: a.testIndex,
      mode: a.mode,
      startedAt: String(a.startedAt || ''),
      endsAt: String(a.endsAt || ''),
      status: a.status,
      endsAtType: typeof a.endsAt
    };
  });

  return {
    questionCounts: qCounts,
    validQuestionCounts: validCounts,
    r7amSamples: r7amSamples,
    activeAttempts: activeAttempts,
    totalQuestions: qb.length,
    totalAttempts: attempts.length
  };
}

function clearStaleAttempts_() {
  var sh = getSheet_(SHEETS.Attempts);
  var rows = readRecords_(sh);
  var now = new Date();
  var cleared = 0;
  for (var i = rows.length - 1; i >= 0; i--) {
    var r = rows[i];
    if (r.status !== 'started') continue;
    var endsAt = r.endsAt ? new Date(r.endsAt) : null;
    if (!endsAt || now > endsAt) {
      // Row index in sheet = i + 2 (1 for header, 1 for 0-based)
      sh.getRange(i + 2, 10).setValue('expired');  // column 10 = status
      cleared++;
    }
  }
  // Also clear any 'started' attempt regardless of time (force reset)
  var remaining = readRecords_(sh).filter(function(r) { return r.status === 'started'; });
  remaining.forEach(function(r) {
    for (var j = 0; j < rows.length; j++) {
      if (rows[j].attemptId === r.attemptId) {
        sh.getRange(j + 2, 10).setValue('abandoned');
        cleared++;
        break;
      }
    }
  });
  return { ok: true, cleared: cleared };
}

// Run from GAS editor or clasp run: update a Config key-value pair
function updateConfigValue(key, value) {
  var sh = getSheet_(SHEETS.Config);
  var data = sh.getDataRange().getValues();
  for (var i = 1; i < data.length; i++) {
    if (String(data[i][0]).trim() === key) {
      sh.getRange(i + 1, 2).setValue(value);
      Logger.log('Updated ' + key + ' = ' + value);
      return { ok: true, key: key, value: value, updated: true };
    }
  }
  Logger.log('Key not found: ' + key);
  return { ok: false, key: key, error: 'Key not found' };
}

// Run from GAS editor or clasp run: ensure TagStats sheet exists
function ensureTagStatsSheet() {
  var ss = getDb_();
  var sh = ensureSheet_(ss, SHEETS.TagStats);
  setHeaders_(sh, HEADERS[SHEETS.TagStats]);
  return { ok: true, sheetName: sh.getName() };
}

// Run from GAS editor to authorize Drive scope and upload images
function setupImageFolder() {
  var folder = getOrCreateImageFolder_();
  Logger.log('Folder ID: ' + folder.getId());
  Logger.log('Folder URL: ' + folder.getUrl());
}

// Run from GAS editor: update QuestionBank imageUrl to GitHub raw URLs
function linkGitHubImages() {
  var BASE = 'https://raw.githubusercontent.com/bubbleberry247/PDF-RakuRaku-Seisan/master/docs/assets/archi-16w/images/';
  var imageFiles = [
    'R5_AM_08', 'R5_AM_09', 'R5_AM_10',
    'R6_AM_02', 'R6_AM_05', 'R6_AM_11', 'R6_AM_12',
    'R7_AM_02', 'R7_AM_05', 'R7_AM_07', 'R7_AM_11', 'R7_AM_12'
  ];

  var fileMap = {};
  imageFiles.forEach(function(name) {
    var qId = name.replace(/_/g, '-');  // R5_AM_08 -> R5-AM-08
    fileMap[qId] = BASE + name + '.png';
  });

  var sh = getSheet_(SHEETS.QuestionBank);
  var headers = sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0];
  var qIdCol = -1, imgCol = -1;
  for (var c = 0; c < headers.length; c++) {
    var h = String(headers[c]).trim().toLowerCase();
    if (h === 'qid') qIdCol = c;
    if (h === 'imageurl') imgCol = c;
  }
  if (qIdCol < 0 || imgCol < 0) { Logger.log('ERROR: headers not found'); return; }

  var data = sh.getDataRange().getValues();
  var updated = 0;
  for (var i = 1; i < data.length; i++) {
    var qId = String(data[i][qIdCol] || '').trim();
    if (fileMap[qId]) {
      sh.getRange(i + 1, imgCol + 1).setValue(fileMap[qId]);
      updated++;
    }
  }
  Logger.log('Updated ' + updated + ' imageUrl entries');
  return { ok: true, updated: updated, mapping: fileMap };
}

// Run from GAS editor or via ?action=diagStem[&fix=true]
// Diagnose: answerCount>1 but stem missing "2つ" / has "1つ" / has "!" OCR errors
// With fix=true: auto-fix stem and choice text
function diagFixQuestionBank(doFix) {
  var sh = getSheet_(SHEETS.QuestionBank);
  var data = sh.getDataRange().getValues();
  var headers = data[0].map(function(h) { return String(h).trim().toLowerCase(); });
  var qIdCol = headers.indexOf('qid');
  var stemCol = headers.indexOf('stem');
  var correctCol = headers.indexOf('correct');
  var choiceACols = { a: headers.indexOf('choicea'), b: headers.indexOf('choiceb'), c: headers.indexOf('choicec'), d: headers.indexOf('choiced'), e: headers.indexOf('choicee') };
  var statusCol = headers.indexOf('status');

  var issues = [];
  var fixed = 0;

  for (var i = 1; i < data.length; i++) {
    if (String(data[i][statusCol]) !== 'published') continue;
    var qId = String(data[i][qIdCol] || '');
    var stem = String(data[i][stemCol] || '');
    var correct = String(data[i][correctCol] || '');
    var answerCount = correct.split(',').map(function(s){ return s.trim(); }).filter(Boolean).length;

    // Check 1: multi-answer but stem says "1つ選べ" or "１つ選べ"
    if (answerCount > 1 && (stem.indexOf('1つ選べ') >= 0 || stem.indexOf('１つ選べ') >= 0)) {
      issues.push({ row: i + 1, qId: qId, type: 'STEM_1つ選べ', answerCount: answerCount, correct: correct, stemSnippet: stem.substring(0, 80) });
      if (doFix) {
        var newStem = stem.replace(/1つ選べ/g, '2つ選べ').replace(/１つ選べ/g, '２つ選べ');
        sh.getRange(i + 1, stemCol + 1).setValue(newStem);
        fixed++;
      }
    }

    // Check 2: multi-answer but stem has no "2つ" anywhere (e.g. "最も不適当なものはどれか" without count)
    if (answerCount > 1 && stem.indexOf('2つ') < 0 && stem.indexOf('２つ') < 0 && stem.indexOf('1つ選べ') < 0 && stem.indexOf('１つ選べ') < 0) {
      issues.push({ row: i + 1, qId: qId, type: 'STEM_NO_COUNT', answerCount: answerCount, correct: correct, stemSnippet: stem.substring(0, 80) });
      // For STEM_NO_COUNT: add "不適当なものを2つ選べ" — needs manual review, no auto-fix
    }

    // Check 3: "!" in stem or choices that looks like OCR error for "1"
    var allText = stem;
    var choiceKeys = ['a','b','c','d','e'];
    choiceKeys.forEach(function(k) {
      if (choiceACols[k] >= 0) allText += ' ' + String(data[i][choiceACols[k]] || '');
    });
    if (allText.match(/!\s*[°℃]/)) {
      issues.push({ row: i + 1, qId: qId, type: 'EXCL_OCR', textSnippet: allText.match(/.{0,20}!\s*[°℃].{0,20}/)[0] });
      if (doFix) {
        // Fix stem
        if (stem.match(/!\s*[°℃]/)) {
          sh.getRange(i + 1, stemCol + 1).setValue(stem.replace(/!/g, '1'));
          fixed++;
        }
        // Fix choices
        choiceKeys.forEach(function(k) {
          if (choiceACols[k] >= 0) {
            var ct = String(data[i][choiceACols[k]] || '');
            if (ct.match(/!\s*[°℃]/)) {
              sh.getRange(i + 1, choiceACols[k] + 1).setValue(ct.replace(/!/g, '1'));
              fixed++;
            }
          }
        });
      }
    }
  }

  Logger.log('Issues found: ' + issues.length + ', fixed: ' + fixed);
  issues.forEach(function(iss) { Logger.log(JSON.stringify(iss)); });
  return { ok: true, issueCount: issues.length, fixedCount: fixed, issues: issues };
}

// Run from GAS editor: fix specific R5-PM-59 issues
function fixR5PM59() {
  var sh = getSheet_(SHEETS.QuestionBank);
  var data = sh.getDataRange().getValues();
  var headers = data[0].map(function(h) { return String(h).trim().toLowerCase(); });
  var qIdCol = headers.indexOf('qid');
  var stemCol = headers.indexOf('stem');
  var choiceACol = headers.indexOf('choicea');
  var fixes = [];

  for (var i = 1; i < data.length; i++) {
    var qId = String(data[i][qIdCol] || '');
    if (qId !== 'R5-PM-59') continue;

    var stem = String(data[i][stemCol] || '');
    var choiceA = String(data[i][choiceACol] || '');

    // Fix stem: "1つ選べ" -> "2つ選べ"
    if (stem.indexOf('1つ選べ') >= 0) {
      var newStem = stem.replace('1つ選べ', '2つ選べ');
      sh.getRange(i + 1, stemCol + 1).setValue(newStem);
      fixes.push({ field: 'stem', old: '1つ選べ', new: '2つ選べ' });
    }

    // Fix choiceA: "!°C" -> "1°C"  or "!℃" -> "1℃"
    if (choiceA.match(/![°℃]/)) {
      var newChoiceA = choiceA.replace(/!([°℃])/g, '1$1');
      sh.getRange(i + 1, choiceACol + 1).setValue(newChoiceA);
      fixes.push({ field: 'choiceA', old: choiceA.substring(0, 60), new: newChoiceA.substring(0, 60) });
    }

    Logger.log('R5-PM-59 fixes: ' + JSON.stringify(fixes));
    return { ok: true, qId: 'R5-PM-59', fixes: fixes };
  }

  return { ok: false, error: 'R5-PM-59 not found' };
}

// Run from GAS editor: auto-assign tag1 based on qId number ranges
function autoTagQuestions() {
  var sh = getSheet_(SHEETS.QuestionBank);
  var data = sh.getDataRange().getValues();
  var headers = data[0].map(function(h) { return String(h).trim().toLowerCase(); });
  var qIdCol = headers.indexOf('qid');
  var tag1Col = headers.indexOf('tag1');
  if (qIdCol < 0 || tag1Col < 0) { return { ok: false, error: 'qid or tag1 header not found' }; }
  var updated = 0;
  for (var i = 1; i < data.length; i++) {
    var qId = String(data[i][qIdCol] || '');
    var match = qId.match(/^R\d-(AM|PM)-(\d+)$/);
    if (!match) continue;
    var part = match[1];
    var num = parseInt(match[2], 10);
    var tag = getTagByNumber_(part, num);
    if (tag && String(data[i][tag1Col]) !== tag) {
      sh.getRange(i + 1, tag1Col + 1).setValue(tag);
      updated++;
    }
  }
  Logger.log('autoTagQuestions: updated ' + updated + ' / ' + (data.length - 1) + ' questions');
  return { ok: true, updated: updated, total: data.length - 1 };
}

function getTagByNumber_(part, num) {
  if (part === 'AM') {
    if (num >= 1 && num <= 14) return '建築学等';
    if (num >= 15 && num <= 20) return '設備等';
    if (num >= 21 && num <= 33) return '躯体';
    if (num >= 34 && num <= 44) return '仕上げ';
  } else {
    if (num >= 45 && num <= 54) return '施工管理';
    if (num >= 55 && num <= 64) return '法規';
    if (num >= 65 && num <= 70) return '施工管理法(応用)';
    if (num >= 71 && num <= 72) return '施工管理法';
  }
  return null;
}

