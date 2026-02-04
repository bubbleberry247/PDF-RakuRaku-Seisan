// api.gs

// Global serializer: convert Date objects to ISO strings for google.script.run
function toSerializable_(obj) {
  if (obj === null || obj === undefined) return obj;
  if (obj instanceof Date) return obj.toISOString();
  if (Array.isArray(obj)) return obj.map(toSerializable_);
  if (typeof obj === 'object') {
    var result = {};
    for (var k in obj) {
      if (obj.hasOwnProperty(k)) {
        result[k] = toSerializable_(obj[k]);
      }
    }
    return result;
  }
  return obj;
}

function apiGetHome(clientUserKey) {
  __clientUserKey = clientUserKey || '';
  try {
    var config = getConfigMap_();
    var tz = getConfigValue_(config, 'TIMEZONE', 'Asia/Tokyo');
    var userCtx = getUserContext_();

    // If no identification, signal client to show registration screen
    if (userCtx.authMethod === 'none') {
      return { needsRegistration: true, config: config };
    }

    var access = requireActiveUser_(userCtx);
    var user = ensureUser_(userCtx.userKey, userCtx.email, userCtx.displayName);

    var startDate = getConfigValue_(config, 'PROGRAM_START_DATE', '2026-04-01');
    var weeks = weeksSinceStart_(startDate, tz);
    var plans = getTestPlanRows_();

    var unlocked = [];
    var next = null;
    plans.forEach(function(p){
      var uw = parseUnlockWeek_(p.unlockWeek);
      var isThisWeek = isThisWeeksTest_(p, weeks);
      var qPer = Number(p.questionsPerTest || getConfigValue_(config, 'QUESTIONS_PER_TEST', 20));
      unlocked.push({ testIndex: p.testIndex, label: p.label, targetSegments: String(p.targetSegments || ''), questionsPerTest: qPer, unlockWeek: uw, recommended: isThisWeek });
      if (!isThisWeek && uw > weeks && (!next || uw < Number(next.unlockWeek))) {
        next = { testIndex: p.testIndex, label: p.label, unlockWeek: uw };
      }
    });

    // OPTIMIZATION: Read heavy sheets once and reuse
    var allAttempts = readRecords_(getSheet_(SHEETS.Attempts));
    var allTagStats = [];
    try { var tsSh = getDb_().getSheetByName(SHEETS.TagStats); if (tsSh) allTagStats = readRecords_(tsSh); } catch(e){}
    var questionBank = readQuestionBank_();

    var attempts = allAttempts.filter(function(r){ return r.userKey === user.userKey; });
    var userTagStats = allTagStats.filter(function(r){ return r.userKey === user.userKey; });

    attempts.sort(function(a,b){ return String(b.startedAt).localeCompare(String(a.startedAt)); });
    var recent = attempts.slice(0, 3).map(function(a){
      var score = a.scoreTotal;
      if (score === '' || score === null || score === undefined) {
        score = null;
      } else {
        score = Number(score);
      }
      return {
        testIndex: a.testIndex,
        mode: a.mode,
        scoreTotal: score,
        status: a.status,
        submittedAt: a.submittedAt
      };
    });

    var submittedTests = attempts.filter(function(a){
      return a.status === 'submitted' && a.mode === 'test';
    });
    var submittedMap = {};
    submittedTests.forEach(function(a){
      if (a.testIndex !== '' && a.testIndex !== null && a.testIndex !== undefined) {
        var k = String(a.testIndex);
        submittedMap[k] = (submittedMap[k] || 0) + 1;
      }
    });
    var now = getNow_();
    var startedMap = {};
    attempts.forEach(function(a){
      if (a.status === 'started' && a.mode === 'test') {
        var endsAt = a.endsAt ? new Date(a.endsAt) : null;
        if (!endsAt || now <= endsAt) {
          startedMap[String(a.testIndex)] = true;
        }
      }
    });
    unlocked.forEach(function(t){
      var key = String(t.testIndex);
      if (startedMap[key]) t.status = 'started';
      else if (submittedMap[key]) t.status = 'submitted';
      else t.status = 'new';
      t.submitCount = submittedMap[key] || 0;
    });
    var submittedUniqueCount = Object.keys(submittedMap).length;
    var avgScore = 0;
    if (submittedTests.length > 0) {
      var sum = 0;
      submittedTests.forEach(function(a){ sum += Number(a.scoreTotal || 0); });
      avgScore = sum / submittedTests.length;
    }
    var progress = buildProgress_(attempts, plans.length, tz, 8);

    var team = [];
    if (access.role === 'manager' || access.role === 'admin') {
      // Use email or userKey for manager lookup (non-Workspace users have no email)
      var managerLookup = userCtx.email || userCtx.userKey;
      var directRefs = getDirectReports_(managerLookup);
      var userRows = readRecords_(getSheet_(SHEETS.Users));
      // Build lookup maps: support both email and userKey as identifiers
      var refToKeys = {};
      var refToName = {};
      userRows.forEach(function(r){
        var em = String(r.email || '');
        var uk = String(r.userKey || '');
        // Map by email if available
        if (em) {
          if (!refToKeys[em]) refToKeys[em] = [];
          refToKeys[em].push(uk);
          if (!refToName[em]) refToName[em] = r.displayName || em.split('@')[0];
        }
        // Also map by userKey (for non-Workspace users)
        if (uk) {
          if (!refToKeys[uk]) refToKeys[uk] = [];
          refToKeys[uk].push(uk);
          if (!refToName[uk]) refToName[uk] = r.displayName || uk;
        }
      });
      directRefs.forEach(function(ref){
        var keys = refToKeys[ref] || [];
        var userAttempts = allAttempts.filter(function(a){ return keys.indexOf(String(a.userKey || '')) >= 0; });
        var summary = buildProgress_(userAttempts, plans.length, tz, 8);
        team.push({
          email: ref,
          displayName: refToName[ref] || ref,
          progress: summary
        });
      });
    }

    // Use optimized functions with pre-read data
    var weakTags = computeTopWeakTagsFromRows_(userTagStats, 3);
    var lawCards = readLawCards_(false).slice(0, 20);
    var nextAction = computeNextAction_(unlocked, submittedMap, weakTags, next);
    var fieldStats = [];
    try { fieldStats = computeFieldStatsFromRows_(userTagStats, questionBank); } catch (fsErr) { Logger.log('fieldStats error: ' + fsErr.message); }
    var scoreHistory = getRecentScoresFromRows_(attempts, 10);

    return toSerializable_({
      config: config,
      user: user,
      unlocked: unlocked,
      next: next,
      nextAction: nextAction,
      recent: recent,
      weakTags: weakTags,
      lawCards: lawCards,
      progress: progress,
      scoreHistory: scoreHistory,
      auth: access,
      team: team,
      fieldStats: fieldStats
    });
  } catch (e) {
    return {
      _error: true,
      message: e.message,
      unlocked: [],
      config: {},
      recent: [],
      weakTags: []
    };
  }
}

function apiStartTest(testIndex, forceNew, clientUserKey) {
  __clientUserKey = clientUserKey || '';
  try {
    var config = getConfigMap_();
    var tz = getConfigValue_(config, 'TIMEZONE', 'Asia/Tokyo');
    var weeks = weeksSinceStart_(getConfigValue_(config, 'PROGRAM_START_DATE', '2026-04-01'), tz);
    var plan = getTestPlanByIndex_(testIndex);
    if (!plan) return { _error: true, message: 'テストプラン(testIndex=' + testIndex + ')が見つかりません' };

    var userCtx = getUserContext_();
    requireActiveUser_(userCtx);
    var user = ensureUser_(userCtx.userKey, userCtx.email, userCtx.displayName);

    // Always abandon stale attempts, then create fresh
    var existing = findActiveAttempt_(user.userKey, testIndex);
    if (existing) {
      if (forceNew) {
        updateAttempt_(existing.index, { status: 'abandoned' });
      } else {
        var endsAt = existing.row.endsAt ? new Date(existing.row.endsAt) : null;
        if (!endsAt || getNow_() <= endsAt) {
          var qIds = getTestSet_(testIndex, plan, config);
          var questions = getQuestionsByIds_(qIds).map(toQuestionForClient_);
          if (questions.length > 0) {
            return {
              attemptId: String(existing.row.attemptId),
              testIndex: testIndex,
              endsAt: String(existing.row.endsAt || ''),
              serverNow: formatDateTime_(getNow_(), tz),
              questions: questions
            };
          }
          // Questions missing (stale cache) — abandon and create new
          updateAttempt_(existing.index, { status: 'abandoned' });
        } else {
          updateAttempt_(existing.index, { status: 'expired' });
        }
      }
    }

    var qIds = getTestSet_(testIndex, plan, config);
    if (!qIds || qIds.length === 0) {
      return { _error: true, message: 'テスト問題が生成できませんでした (testIndex=' + testIndex + ', plan.targetSegments=' + (plan.targetSegments || '') + ')' };
    }
    var now = getNow_();
    var endsAtDate = new Date(now.getTime() + 30 * 60000);
    var startedAt = formatDateTime_(now, tz);
    var endsAtStr = formatDateTime_(endsAtDate, tz);

    var attemptId = Utilities.getUuid();
    appendRows_(getSheet_(SHEETS.Attempts), [[
      attemptId, user.userKey, testIndex, 'test',
      startedAt, endsAtStr, '', '', '', 'started', qIds.length
    ]]);

    var questions = getQuestionsByIds_(qIds).map(toQuestionForClient_);

    return {
      attemptId: String(attemptId),
      testIndex: testIndex,
      endsAt: endsAtStr,
      serverNow: formatDateTime_(now, tz),
      questions: questions
    };
  } catch (e) {
    return { _error: true, message: '開始エラー: ' + String(e.message || e) };
  }
}

function startCustomTest_(mode, qIds, timeLimitMinutes, clientUserKey) {
  return startCustomTestWithBank_(mode, qIds, timeLimitMinutes, clientUserKey, null);
}

// Optimized: accepts pre-read QuestionBank to avoid double-read
function startCustomTestWithBank_(mode, qIds, timeLimitMinutes, clientUserKey, questionBank) {
  if (clientUserKey) __clientUserKey = clientUserKey;
  var config = getConfigMap_();
  var tz = getConfigValue_(config, 'TIMEZONE', 'Asia/Tokyo');
  var userCtx = getUserContext_();
  requireActiveUser_(userCtx);
  var user = ensureUser_(userCtx.userKey, userCtx.email, userCtx.displayName);

  var now = getNow_();
  var endsAt = '';
  if (timeLimitMinutes && Number(timeLimitMinutes) > 0) {
    var endsAtDate = new Date(now.getTime() + Number(timeLimitMinutes) * 60000);
    endsAt = formatDateTime_(endsAtDate, tz);
  }
  var attemptId = Utilities.getUuid();
  appendRows_(getSheet_(SHEETS.Attempts), [[
    attemptId, user.userKey, '', mode,
    formatDateTime_(now, tz), endsAt, '', '', '', 'started', qIds.length
  ]]);

  var qb = questionBank || readQuestionBank_();
  var questions = getQuestionsByIdsFromBank_(qIds, qb).map(toQuestionForClient_);
  return {
    attemptId: attemptId,
    mode: mode,
    endsAt: endsAt,
    serverNow: formatDateTime_(now, tz),
    questions: questions
  };
}

function apiStartMiniTest(clientUserKey) {
  __clientUserKey = clientUserKey || '';
  var config = getConfigMap_();
  var limit = Number(getConfigValue_(config, 'MINI_TIME_LIMIT_MINUTES', 30));
  var qIds = generateMiniTestSet_(config);
  return startCustomTest_('mini', qIds, limit);
}

function apiStartTrainingTest(clientUserKey) {
  __clientUserKey = clientUserKey || '';
  var config = getConfigMap_();
  var userCtx = getUserContext_();
  requireActiveUser_(userCtx);
  var user = ensureUser_(userCtx.userKey, userCtx.email, userCtx.displayName);
  var limit = Number(getConfigValue_(config, 'TRAIN_TIME_LIMIT_MINUTES', 10));
  var qIds = generateTrainingTestSet_(user.userKey, config);
  return startCustomTest_('training', qIds, limit);
}

function apiStartMockExam(year, part, resume, clientUserKey) {
  __clientUserKey = clientUserKey || '';
  var validYears = ['R5', 'R6', 'R7'];
  var validParts = ['AM', 'PM'];
  year = String(year || '').toUpperCase();
  part = String(part || '').toUpperCase();
  if (validYears.indexOf(year) < 0 || validParts.indexOf(part) < 0) {
    throw new Error('年度またはパートが無効です');
  }

  var config = getConfigMap_();
  var tz = getConfigValue_(config, 'TIMEZONE', 'Asia/Tokyo');
  var userCtx = getUserContext_();
  requireActiveUser_(userCtx);
  var user = ensureUser_(userCtx.userKey, userCtx.email, userCtx.displayName);

  var existing = findActiveMockAttempt_(user.userKey, year, part);
  if (existing) {
    if (resume) {
      // Resume existing mock attempt
      var endsAt = existing.row.endsAt ? new Date(existing.row.endsAt) : null;
      if (endsAt && getNow_() > endsAt) {
        // Expired — abandon and fall through to create new
        updateAttempt_(existing.index, { status: 'expired' });
      } else {
        var qIds = getMockExamQuestions_(year, part);
        var questions = getQuestionsByIds_(qIds).map(toQuestionForClient_);
        var rules = getExamSectionRules_(year, part);
        return {
          attemptId: existing.row.attemptId,
          year: year,
          part: part,
          endsAt: existing.row.endsAt,
          serverNow: formatDateTime_(getNow_(), tz),
          questions: questions,
          sectionRules: rules
        };
      }
    } else {
      updateAttempt_(existing.index, { status: 'abandoned' });
    }
  }

  var qIds = getMockExamQuestions_(year, part);
  if (qIds.length === 0) {
    throw new Error(year + ' ' + (part === 'AM' ? '午前' : '午後') + 'の問題がまだ登録されていません');
  }

  var timeLimitMinutes = (part === 'AM') ? 150 : 120;
  var now = getNow_();
  var endsAtDate = new Date(now.getTime() + timeLimitMinutes * 60000);
  var startedAt = formatDateTime_(now, tz);
  var endsAt = formatDateTime_(endsAtDate, tz);
  var testIndex = year + '-' + part;

  var attemptId = Utilities.getUuid();
  appendRows_(getSheet_(SHEETS.Attempts), [[
    attemptId, user.userKey, testIndex, 'mock',
    startedAt, endsAt, '', '', '', 'started', qIds.length
  ]]);

  var questions = getQuestionsByIds_(qIds).map(toQuestionForClient_);
  var rules = getExamSectionRules_(year, part);

  return {
    attemptId: attemptId,
    year: year,
    part: part,
    endsAt: endsAt,
    serverNow: formatDateTime_(now, tz),
    questions: questions,
    sectionRules: rules
  };
}

function apiCheckActiveMockAttempt(year, part, clientUserKey) {
  __clientUserKey = clientUserKey || '';
  year = String(year || '').toUpperCase();
  part = String(part || '').toUpperCase();
  var userCtx = getUserContext_();
  requireActiveUser_(userCtx);
  var existing = findActiveMockAttempt_(userCtx.userKey, year, part);
  if (existing) {
    var endsAt = existing.row.endsAt ? new Date(existing.row.endsAt) : null;
    if (!endsAt || getNow_() <= endsAt) {
      return { hasActive: true, attemptId: existing.row.attemptId, startedAt: String(existing.row.startedAt || '') };
    }
  }
  return { hasActive: false };
}

function getTestSet_(testIndex, plan, config) {
  var shared = String(getConfigValue_(config, 'SHARED_TESTSET_MODE', 'ON')).toUpperCase() === 'ON';
  if (!shared) {
    return generateTestSet_(plan, config);
  }
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var sh = getSheet_(SHEETS.TestSets);
    var rows = readRecords_(sh);
    for (var i = 0; i < rows.length; i++) {
      if (String(rows[i].testIndex) === String(testIndex)) {
        var cached = String(rows[i].questionIds).split(',').filter(Boolean);
        // Validate ALL cached qIds exist in current QuestionBank
        var resolved = getQuestionsByIds_(cached);
        if (resolved.length === cached.length) {
          return cached;
        }
        // Stale cache: delete row and regenerate
        sh.deleteRow(i + 2); // +2: header=1, 0-indexed→1-indexed
        break;
      }
    }
    var qIds = generateTestSet_(plan, config);
    appendRows_(sh, [[testIndex, formatDateTime_(getNow_(), 'Asia/Tokyo'), qIds.join(',')]]);
    return qIds;
  } finally {
    lock.releaseLock();
  }
}

function apiSubmitTest(payload) {
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var attemptId = payload.attemptId;
    var answers = payload.answers || [];

    var attemptInfo = findAttemptById_(attemptId);
    if (!attemptInfo) throw new Error('Attemptが見つかりません');

    var attempt = attemptInfo.row;
    if (attempt.status !== 'started') throw new Error('この試験は開始済みではありません');

    var now = getNow_();
    var endsAt = attempt.endsAt ? new Date(attempt.endsAt) : null;
    var expired = endsAt && now > endsAt;

    var config = getConfigMap_();
    var tz = getConfigValue_(config, 'TIMEZONE', 'Asia/Tokyo');

    if (expired) {
      updateAttempt_(attemptInfo.index, { status: 'expired', submittedAt: formatDateTime_(now, tz), scoreTotal: 0, scoreAbility: 0 });
      return { status: 'expired', message: '制限時間を過ぎています' };
    }

    var testIndex = attempt.testIndex;
    var qMap = {};
    if (attempt.mode === 'practice' || !testIndex) {
      var ids = answers.map(function(a){ return a.qId; });
      getQuestionsByIds_(ids).forEach(function(q){ qMap[q.qId] = q; });
    } else if (attempt.mode === 'mock') {
      var parts = String(testIndex).split('-');
      var mockQIds = getMockExamQuestions_(parts[0], parts[1]);
      getQuestionsByIds_(mockQIds).forEach(function(q){ qMap[q.qId] = q; });
    } else {
      var plan = getTestPlanByIndex_(testIndex);
      var qIds = getTestSet_(testIndex, plan, config);
      getQuestionsByIds_(qIds).forEach(function(q){ qMap[q.qId] = q; });
    }

    var answerRows = [];
    var wrongList = [];
    var scoreTotal = 0;
    var scoreAbility = 0;
    var answersMap = {};

    answers.forEach(function(a){
      var q = qMap[a.qId];
      if (!q) return;
      var correct = String(q.correct || '').split(',').map(function(s){ return s.trim().toUpperCase(); }).filter(Boolean);
      var chosenRaw = a.chosen;
      var chosenList = Array.isArray(chosenRaw) ? chosenRaw : String(chosenRaw || '').split(',');
      chosenList = chosenList.map(function(s){ return String(s || '').trim().toUpperCase(); }).filter(Boolean);
      var chosen = chosenList.join(',');
      var correctMap = {};
      correct.forEach(function(k){ correctMap[k] = true; });
      var isCorrect = (chosenList.length === correct.length) && chosenList.every(function(k){ return correctMap[k]; });
      if (isCorrect) scoreTotal += 1;
      if (q.type === 'ability' && isCorrect) scoreAbility += 1;
      answersMap[q.qId] = { chosenList: chosenList, isCorrect: isCorrect };

      answerRows.push({
        attemptId: attemptId,
        qId: q.qId,
        chosen: chosen,
        isCorrect: isCorrect,
        answeredAt: formatDateTime_(now, tz),
        timeSpentSec: a.timeSpentSec || '',
        tag1: q.tag1, tag2: q.tag2, tag3: q.tag3
      });

      if (!isCorrect) {
        var explainChoice = '';
        if (chosenList.length === 1) {
          var keyMap = { A: 'explainA', B: 'explainB', C: 'explainC', D: 'explainD', E: 'explainE' };
          var k = keyMap[chosenList[0]] || '';
          explainChoice = k ? (q[k] || '') : '';
        }
        var qClient = toQuestionForClient_(q);
        wrongList.push({
          qId: qClient.qId,
          stem: qClient.stem,
          chosen: chosen,
          correct: qClient.correct,
          explainShort: qClient.explainShort,
          explainLong: qClient.explainLong,
          explainChoice: explainChoice,
          choices: qClient.choices,
          explainA: qClient.explainA,
          explainB: qClient.explainB,
          explainC: qClient.explainC,
          explainD: qClient.explainD,
          explainE: qClient.explainE
        });
      }
    });

    // write answers
    var shAns = getSheet_(SHEETS.AttemptAnswers);
    var rows = answerRows.map(function(a){
      return [a.attemptId, a.qId, a.chosen, a.isCorrect, a.answeredAt, a.timeSpentSec, a.tag1, a.tag2, a.tag3];
    });
    appendRows_(shAns, rows);

    var qList = Object.keys(qMap).map(function(k){ return qMap[k]; });
    var sectionResult = null;
    var penaltyTotal = 0;
    if (attempt.mode === 'mock') {
      sectionResult = buildExamSectionScores_(qList, answersMap);
      penaltyTotal = Number(sectionResult.penaltyTotal || 0);
    }
    var finalScoreTotal = Math.max(0, scoreTotal - penaltyTotal);

    updateAttempt_(attemptInfo.index, {
      submittedAt: formatDateTime_(now, tz),
      scoreTotal: finalScoreTotal,
      scoreAbility: scoreAbility,
      status: 'submitted'
    });

    updateTagStats_(attempt.userKey, answerRows);

    var weakTags = computeTopWeakTags_(attempt.userKey, 3);
    var conceptCards = getConceptCardsForTags_(weakTags.map(function(t){ return t.tag; }));
    var scoreHistory = getRecentScores_(attempt.userKey, 5);
    var wrongRanking = getWrongAnswerRanking_(attempt.userKey, 10);

    // Gemini AI study advice with historical data (best-effort)
    var advice = '';
    try {
      var fieldStats = [];
      try { fieldStats = computeFieldStats_(attempt.userKey); } catch (fe) {}
      var adviceResult = generateStudyAdvice_({
        scoreTotal: finalScoreTotal,
        totalQuestions: qList.length,
        weakTags: weakTags,
        sectionScores: sectionResult ? (sectionResult.sectionScores || []) : [],
        wrongCount: wrongList.length,
        scoreHistory: scoreHistory,
        wrongRanking: wrongRanking,
        fieldStats: fieldStats
      });
      advice = adviceResult.text || '';
    } catch (e) {
      Logger.log('Advice generation failed: ' + e);
    }

    return toSerializable_({
      status: 'submitted',
      scoreTotal: finalScoreTotal,
      scoreAbility: scoreAbility,
      wrongList: wrongList,
      weakTags: weakTags,
      conceptCards: conceptCards,
      scoreHistory: scoreHistory,
      sectionScores: sectionResult ? (sectionResult.sectionScores || []) : [],
      penaltyTotal: penaltyTotal,
      wrongRanking: wrongRanking,
      advice: advice
    });

  } catch (e) {
    console.error('apiSubmitTest error: ' + e.message + '\n' + e.stack);
    return { _error: true, status: 'error', message: e.message };
  } finally {
    lock.releaseLock();
  }
}

function updateAttempt_(rowIndex, fields) {
  var sh = getSheet_(SHEETS.Attempts);
  var headers = HEADERS[SHEETS.Attempts];
  var row = sh.getRange(rowIndex, 1, 1, headers.length).getValues()[0];
  for (var i = 0; i < headers.length; i++) {
    if (fields.hasOwnProperty(headers[i])) row[i] = fields[headers[i]];
  }
  sh.getRange(rowIndex, 1, 1, headers.length).setValues([row]);
}

function getConceptCardsForTags_(tags) {
  if (!tags || tags.length === 0) return [];
  var cards = readRecords_(getSheet_(SHEETS.ConceptCards)).filter(function(c){
    return c.status === 'published' && tags.indexOf(c.tag) >= 0;
  });
  return cards;
}

function apiStartFieldTest(tag1, requestedLimit, clientUserKey) {
  __clientUserKey = clientUserKey || '';
  var userCtx = getUserContext_();
  requireActiveUser_(userCtx);
  var user = ensureUser_(userCtx.userKey, userCtx.email, userCtx.displayName);

  // Read QuestionBank once and reuse
  var allQb = readQuestionBank_();
  var qb = allQb.filter(function(q) {
    return q.status === 'published' && isValidChoiceQuestion_(q)
      && String(q.tag1) === String(tag1);
  });

  if (qb.length === 0) {
    return { _error: true, message: 'この分野の問題がありません: ' + tag1 };
  }

  var maxQ = (requestedLimit && Number(requestedLimit) > 0) ? Number(requestedLimit) : 10;
  var limit = Math.min(maxQ, qb.length);
  var usedVariant = {};
  var picked = pickQuestions_(qb, limit, usedVariant);
  var qIds = picked.map(function(q) { return q.qId; });

  // Pass pre-read QuestionBank to avoid re-read in startCustomTest
  return startCustomTestWithBank_('field', qIds, Math.ceil(limit * 3), null, allQb);
}

function apiStartPractice(tags, limit, clientUserKey) {
  __clientUserKey = clientUserKey || '';
  var userCtx = getUserContext_();
  requireActiveUser_(userCtx);
  var user = ensureUser_(userCtx.userKey, userCtx.email, userCtx.displayName);
  var qb = readQuestionBank_().filter(function(q){
    return q.status === 'published' && q.type === 'knowledge' && isValidChoiceQuestion_(q);
  });
  var tagSet = {};
  (tags || []).forEach(function(t){ tagSet[t] = true; });

  var pool = qb.filter(function(q){
    return tagSet[q.tag1] || tagSet[q.tag2] || tagSet[q.tag3];
  });
  var usedVariant = {};
  var picked = pickQuestions_(pool, Number(limit || 10), usedVariant);

  var attemptId = Utilities.getUuid();
  var now = formatDateTime_(getNow_(), 'Asia/Tokyo');
  appendRows_(getSheet_(SHEETS.Attempts), [[
    attemptId, user.userKey, '', 'practice', now, '', '', '', '', 'started'
  ]]);

  return { attemptId: attemptId, questions: picked.map(toQuestionForClient_) };
}

function apiSubmitPractice(payload) {
  // reuse submit logic (no endsAt)
  return apiSubmitTest(payload);
}

// --- Registration & Recovery ---

function apiRegisterWithName(displayName) {
  try {
    var name = String(displayName || '').trim();
    if (!name) return { _error: true, message: '氏名を入力してください' };
    if (name.length > 50) return { _error: true, message: '氏名は50文字以内で入力してください' };

    // Check if Google-logged-in — if so, auto-register without code
    var email = getActiveEmail_();
    if (email) {
      var profile = getDirectoryProfile_(email);
      var user = ensureUser_(email, profile.email, profile.displayName || name);
      return { userKey: email, recoveryCode: '', authMethod: 'google', displayName: user.displayName };
    }

    // Non-Google user: create new user with recovery code
    var newUser = registerNewUser_(name);
    return {
      userKey: newUser.userKey,
      recoveryCode: newUser.recoveryCode,
      authMethod: 'code',
      displayName: newUser.displayName
    };
  } catch (e) {
    return { _error: true, message: '登録エラー: ' + e.message };
  }
}

function apiRestoreByCode(code) {
  try {
    var c = String(code || '').trim().toUpperCase();
    if (!c) return { _error: true, message: '復元コードを入力してください' };

    var user = findUserByRecoveryCode_(c);
    if (!user) return { _error: true, message: 'このコードに該当するユーザーが見つかりません' };

    return {
      userKey: user.userKey,
      displayName: user.displayName,
      authMethod: 'code'
    };
  } catch (e) {
    return { _error: true, message: '復元エラー: ' + e.message };
  }
}

function apiImportExplanations(csvText) {
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var sheet = getSheet_(SHEETS.QuestionBank);
    var headers = HEADERS[SHEETS.QuestionBank];
    var qIdCol = headers.indexOf('qId');
    var explainKeys = ['explainA', 'explainB', 'explainC', 'explainD', 'explainE'];
    var explainCols = {};
    explainKeys.forEach(function(k) { explainCols[k] = headers.indexOf(k); });
    var data = sheet.getDataRange().getValues();
    var qIdMap = {};
    for (var r = 1; r < data.length; r++) {
      qIdMap[String(data[r][qIdCol]).trim()] = r;
    }
    var lines = csvText.split(/\r?\n/);
    if (lines.length < 2) return { ok: false, message: 'No data rows' };
    var csvHeaders = lines[0].replace(/^\uFEFF/, '').split(',');
    var colMap = {};
    csvHeaders.forEach(function(h, i) { colMap[h.trim()] = i; });
    if (colMap.qId === undefined) return { ok: false, message: 'Missing qId column' };
    var updated = 0;
    var notFound = [];
    for (var i = 1; i < lines.length; i++) {
      var line = lines[i].trim();
      if (!line) continue;
      var fields = parseCsvLine_(line);
      var qId = fields[colMap.qId] ? fields[colMap.qId].trim() : '';
      if (!qId) continue;
      var rowIdx = qIdMap[qId];
      if (rowIdx === undefined) { notFound.push(qId); continue; }
      var changed = false;
      explainKeys.forEach(function(key) {
        if (colMap[key] !== undefined && explainCols[key] >= 0) {
          var val = fields[colMap[key]] || '';
          if (val) {
            data[rowIdx][explainCols[key]] = val;
            changed = true;
          }
        }
      });
      if (changed) updated++;
    }
    if (updated > 0) {
      sheet.getRange(1, 1, data.length, data[0].length).setValues(data);
    }
    return { ok: true, updated: updated, notFound: notFound };
  } finally {
    lock.releaseLock();
  }
}

function parseCsvLine_(line) {
  var result = [];
  var current = '';
  var inQuotes = false;
  for (var i = 0; i < line.length; i++) {
    var c = line[i];
    if (inQuotes) {
      if (c === '"') {
        if (i + 1 < line.length && line[i + 1] === '"') {
          current += '"';
          i++;
        } else {
          inQuotes = false;
        }
      } else {
        current += c;
      }
    } else {
      if (c === '"') {
        inQuotes = true;
      } else if (c === ',') {
        result.push(current);
        current = '';
      } else {
        current += c;
      }
    }
  }
  result.push(current);
  return result;
}

function apiAdminImportCsv(sheetName, csvText) {
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    if (sheetName === SHEETS.QuestionBank) {
      var mig = migrateQuestionBankSchema_();
      if (mig.status === 'manual') {
        return { ok: false, errorCount: 1, errors: [{ row: 1, field: 'header', message: mig.message }] };
      }
    }
    var result = validateCsvForSheet_(sheetName, csvText);
    if (!result.ok) return result;
    if (result.rows.length === 0) return { ok: false, errorCount: 1, errors: [{ row: 1, field: 'csv', message: 'No data rows' }] };
    appendRows_(getSheet_(sheetName), result.rows);
    result.inserted = result.rows.length;
    return result;
  } finally {
    lock.releaseLock();
  }
}

function apiAdminDryRunCsv(sheetName, csvText) {
  if (sheetName === SHEETS.QuestionBank) {
    var mig = migrateQuestionBankSchema_();
    if (mig.status === 'manual') {
      return { ok: false, errorCount: 1, errors: [{ row: 1, field: 'header', message: mig.message }] };
    }
  }
  return validateCsvForSheet_(sheetName, csvText);
}

function adminE2EBootstrap() {
  var lock = LockService.getScriptLock();
  lock.waitLock(30000);
  try {
    var tz = 'Asia/Tokyo';
    var now = getNow_();
    var today = formatDate_(now, tz);

    setConfigValue_('PROGRAM_START_DATE', today);
    setConfigValue_('TIMEZONE', tz);
    setConfigValue_('QUESTIONS_PER_TEST', '3');
    setConfigValue_('ABILITY_PER_TEST', '1');
    setConfigValue_('TIME_LIMIT_MINUTES', '1');
    setConfigValue_('SHARED_TESTSET_MODE', 'ON');

    updateTestPlanRow_(1, {
      targetSegments: 'R7_AM_IROHA',
      questionsPerTest: 3,
      abilityCount: 1,
      revisionMinCount: 0,
      unlockWeek: 0
    });

    var nowStr = formatDateTime_(now, tz);
    var concept = {
      conceptId: 'C012',
      tag: '安全管理',
      title: '安全管理の基本',
      summary: '安全管理のポイントを簡潔にまとめる。',
      checklist: '手順確認|記録|ダブルチェック',
      pitfalls: '確認漏れ・記録忘れ',
      relatedConcepts: '',
      updatedAt: nowStr,
      status: 'published'
    };

    var q1 = {
      qId: 'QC012-001',
      segmentId: 'R7_AM_IROHA',
      type: 'knowledge',
      difficulty: 2,
      tag1: '安全管理',
      tag2: '',
      tag3: '',
      lawTag: '',
      revisionFlag: 0,
      conceptId: 'C012',
      variantGroupId: 'C012',
      source_ref: 'C012-ORIG-01',
      stem: '安全管理で正しいものはどれか。',
      choiceA: 'A',
      choiceB: 'B',
      choiceC: 'C',
      choiceD: 'D',
      choiceE: '',
      explainA: '',
      explainB: '',
      explainC: '',
      explainD: '',
      explainE: '',
      correct: 'B',
      explainShort: '正解はB。',
      explainLong: '安全管理の基本に基づく。',
      status: 'published',
      updatedAt: nowStr
    };

    var q2 = {
      qId: 'QC012-002',
      segmentId: 'R7_AM_IROHA',
      type: 'knowledge',
      difficulty: 2,
      tag1: '安全管理',
      tag2: '',
      tag3: '',
      lawTag: '',
      revisionFlag: 0,
      conceptId: 'C012',
      variantGroupId: 'C012',
      source_ref: 'C012-ORIG-02',
      stem: '安全管理の注意点として適切なものはどれか。',
      choiceA: 'A',
      choiceB: 'B',
      choiceC: 'C',
      choiceD: 'D',
      choiceE: '',
      explainA: '',
      explainB: '',
      explainC: '',
      explainD: '',
      explainE: '',
      correct: 'C',
      explainShort: '正解はC。',
      explainLong: '注意点はC。',
      status: 'published',
      updatedAt: nowStr
    };

    var q3 = {
      qId: 'QC012-003',
      segmentId: 'R7_AM_IROHA',
      type: 'ability',
      difficulty: 3,
      tag1: '安全管理',
      tag2: '',
      tag3: '',
      lawTag: '',
      revisionFlag: 0,
      conceptId: 'C012',
      variantGroupId: 'C012',
      source_ref: 'C012-ORIG-03',
      stem: '安全管理の実務で最も適切なものはどれか。',
      choiceA: 'A',
      choiceB: 'B',
      choiceC: 'C',
      choiceD: 'D',
      choiceE: '',
      explainA: '',
      explainB: '',
      explainC: '',
      explainD: '',
      explainE: '',
      correct: 'C',
      explainShort: '正解はC。',
      explainLong: '実務上はCが最適。',
      status: 'published',
      updatedAt: nowStr
    };

    var ccStatus = upsertByKey_(SHEETS.ConceptCards, 'conceptId', concept);
    var q1Status = upsertByKey_(SHEETS.QuestionBank, 'qId', q1);
    var q2Status = upsertByKey_(SHEETS.QuestionBank, 'qId', q2);
    var q3Status = upsertByKey_(SHEETS.QuestionBank, 'qId', q3);

    return {
      status: 'ok',
      message: 'E2E bootstrap completed',
      today: today,
      concept: ccStatus,
      questions: [q1Status, q2Status, q3Status]
    };
  } finally {
    lock.releaseLock();
  }
}

function adminGenerateAllTestSets() {
  var config = getConfigMap_();
  var plans = getTestPlanRows_();
  var sh = getSheet_(SHEETS.TestSets);
  setHeaders_(sh, HEADERS[SHEETS.TestSets]);
  var rows = [];
  plans.forEach(function(p){
    var ids = generateTestSet_(p, config);
    rows.push([p.testIndex, formatDateTime_(getNow_(), 'Asia/Tokyo'), ids.join(',')]);
  });
  appendRows_(sh, rows);
  return { status: 'ok', count: rows.length };
}

function adminRebuildTagFrequency() {
  var qb = readQuestionBank_().filter(function(q){ return q.status === 'published'; });
  var counts = {};
  qb.forEach(function(q){
    ['tag1','tag2','tag3'].forEach(function(k){
      var t = q[k];
      if (!t) return;
      counts[t] = (counts[t] || 0) + 1;
    });
  });
  return counts;
}

function apiAdminListUserAccess(clientUserKey) {
  __clientUserKey = clientUserKey || '';
  var userCtx = getUserContext_();
  requireAdmin_(userCtx);
  return readRecords_(getUserAccessSheet_());
}

function apiAdminUpsertUserAccess(payload, clientUserKey) {
  __clientUserKey = clientUserKey || '';
  var userCtx = getUserContext_();
  requireAdmin_(userCtx);
  var tz = getConfigValue_(getConfigMap_(), 'TIMEZONE', 'Asia/Tokyo');
  var items = Array.isArray(payload) ? payload : [payload];
  var updated = 0;
  items.forEach(function(item){
    if (!item || !item.email) return;
    var row = {
      email: String(item.email).trim(),
      role: String(item.role || 'user').toLowerCase(),
      managerEmail: String(item.managerEmail || '').trim(),
      active: (item.active === false || String(item.active).toLowerCase() === 'false') ? 'false' : 'true',
      updatedAt: formatDateTime_(getNow_(), tz)
    };
    upsertByKey_(SHEETS.UserAccess, 'email', row);
    updated += 1;
  });
  return { status: 'ok', updated: updated };
}

function apiAdminImportUserAccessCsv(csvText, clientUserKey) {
  __clientUserKey = clientUserKey || '';
  var userCtx = getUserContext_();
  requireAdmin_(userCtx);
  var tz = getConfigValue_(getConfigMap_(), 'TIMEZONE', 'Asia/Tokyo');
  var rows = Utilities.parseCsv(csvText || '');
  if (!rows || rows.length === 0) return { status: 'ok', updated: 0 };

  var startIdx = 0;
  var header = rows[0].map(function(v){ return String(v || '').trim().toLowerCase(); });
  if (header[0] === 'email') startIdx = 1;

  var updated = 0;
  for (var i = startIdx; i < rows.length; i++) {
    var r = rows[i] || [];
    var email = String(r[0] || '').trim();
    if (!email) continue;
    var role = String(r[1] || 'user').trim().toLowerCase();
    var managerEmail = String(r[2] || '').trim();
    var activeRaw = String(r[3] || 'true').trim().toLowerCase();
    var active = (activeRaw === 'false' || activeRaw === '0' || activeRaw === 'no') ? 'false' : 'true';
    var row = {
      email: email,
      role: role,
      managerEmail: managerEmail,
      active: active,
      updatedAt: formatDateTime_(getNow_(), tz)
    };
    upsertByKey_(SHEETS.UserAccess, 'email', row);
    updated += 1;
  }
  return { status: 'ok', updated: updated };
}

function apiAdminMigrateConceptToLawCards(clientUserKey) {
  __clientUserKey = clientUserKey || '';
  var userCtx = getUserContext_();
  requireAdmin_(userCtx);
  getLawCardsSheet_();
  var conceptRows = readRecords_(getSheet_(SHEETS.ConceptCards));
  var updated = 0;
  conceptRows.forEach(function(c){
    if (!c.conceptId) return;
    var row = {
      cardId: String(c.conceptId),
      title: String(c.title || ''),
      dutyHolder: '',
      numberValue: '',
      deadline: '',
      summary: String(c.summary || ''),
      pitfalls: String(c.pitfalls || ''),
      tags: String(c.tag || ''),
      status: String(c.status || 'draft')
    };
    upsertByKey_(SHEETS.LawCards, 'cardId', row);
    updated += 1;
  });
  return { status: 'ok', migrated: updated };
}

function apiAdminMigrateQuestionBankSchema(clientUserKey) {
  __clientUserKey = clientUserKey || '';
  var userCtx = getUserContext_();
  requireAdmin_(userCtx);
  return migrateQuestionBankSchema_();
}

// --- Image Management ---

function apiAdminLinkDriveImages(folderId) {
  var userCtx = getUserContext_();
  requireAdmin_(userCtx);

  var folder = DriveApp.getFolderById(folderId);
  folder.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);

  var files = folder.getFiles();
  var fileMap = {};
  while (files.hasNext()) {
    var f = files.next();
    var name = f.getName().replace(/\.[^.]+$/, '');  // strip extension
    // Convert filename R5_AM_10 -> qId R5-AM-10
    var qId = name.replace(/_/g, '-');
    f.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
    fileMap[qId] = 'https://lh3.googleusercontent.com/d/' + f.getId();
  }

  // Update QuestionBank imageUrl
  var sh = getSheet_(SHEETS.QuestionBank);
  var headers = sh.getRange(1, 1, 1, sh.getLastColumn()).getValues()[0];
  var qIdCol = -1, imgCol = -1;
  for (var c = 0; c < headers.length; c++) {
    var h = String(headers[c]).trim().toLowerCase();
    if (h === 'qid') qIdCol = c;
    if (h === 'imageurl') imgCol = c;
  }
  if (qIdCol < 0 || imgCol < 0) throw new Error('QuestionBank headers not found');

  var data = sh.getDataRange().getValues();
  var updated = 0;
  for (var i = 1; i < data.length; i++) {
    var qId = String(data[i][qIdCol] || '').trim();
    if (fileMap[qId]) {
      sh.getRange(i + 1, imgCol + 1).setValue(fileMap[qId]);
      updated++;
    }
  }

  return { ok: true, filesInFolder: Object.keys(fileMap).length, updated: updated, mapping: fileMap };
}

var IMAGE_FOLDER_NAME_ = 'QuestionBankImages';

function getOrCreateImageFolder_() {
  var folders = DriveApp.getFoldersByName(IMAGE_FOLDER_NAME_);
  if (folders.hasNext()) return folders.next();
  var folder = DriveApp.createFolder(IMAGE_FOLDER_NAME_);
  folder.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
  return folder;
}

function apiAdminUploadImage(fileName, base64Data, clientUserKey) {
  __clientUserKey = clientUserKey || '';
  var userCtx = getUserContext_();
  requireAdmin_(userCtx);

  var folder = getOrCreateImageFolder_();
  var blob = Utilities.newBlob(Utilities.base64Decode(base64Data), 'image/png', fileName);

  // Delete existing file with same name
  var existing = folder.getFilesByName(fileName);
  while (existing.hasNext()) {
    existing.next().setTrashed(true);
  }

  var file = folder.createFile(blob);
  file.setSharing(DriveApp.Access.ANYONE_WITH_LINK, DriveApp.Permission.VIEW);
  return { ok: true, fileId: file.getId(), fileName: fileName };
}

function apiAdminLinkAllDriveImages(clientUserKey) {
  __clientUserKey = clientUserKey || '';
  var userCtx = getUserContext_();
  requireAdmin_(userCtx);

  var folder = getOrCreateImageFolder_();
  return apiAdminLinkDriveImages(folder.getId());
}
