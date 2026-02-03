# Plan: archi-16w @53 — UI改善3点 + Gemini AI学習アドバイス

## タスク一覧

| # | タスク | ファイル |
|---|--------|---------|
| 1 | テスト中のタブナビ非表示 | index.html |
| 2 | 設問移動時にページ最上部へスクロール | index.html |
| 3 | Result画面にGemini AI学習アドバイス表示 | index.html, logic.gs, api.gs, db.gs |

---

## タスク1: テスト中のタブナビ非表示

**現状**: admin/managerユーザーはテスト中もHome/管理タブが見える
**変更**: テスト画面表示時にタブナビを非表示、Home/Result復帰時に復元

### 変更箇所

**index.html `startExam()` (L1755付近)**:
```javascript
show('view-test', true);
show('main-tab-nav', false);  // ← 追加
```

**index.html `renderResult()` (L2570付近)**:
```javascript
show('view-result', true);
// main-tab-navの復元はgoHome()→loadHome()で行われるため不要
```

**index.html `goHome()` (L2824)**:
- 既にloadHome()を呼び、loadHome()内でshow('main-tab-nav', isAdmin)が実行されるため変更不要

---

## タスク2: 設問移動時にページ最上部スクロール

**現状**: `scrollToQuestion()` は `#exam-question` 要素の位置にスクロール（ページ途中になることがある）
**変更**: 常に `window.scrollTo(0, 0)` でページ最上部へ

### 変更箇所

**index.html `scrollToQuestion()` (L2119-2127)**:
```javascript
function scrollToQuestion() {
  window.scrollTo(0, 0);
}
```

---

## タスク3: Result画面にGemini AI学習アドバイス

**方式**: B案（Gemini API）を採用。サーバーサイドでGemini APIを呼び出し、結果を返す。

### 3.1 db.gs — Config HEADERS確認（変更なし）
- Configシートに `GEMINI_API_KEY` を手動登録（`?action=updateConfig&key=GEMINI_API_KEY&value=xxx`）

### 3.2 logic.gs — `generateStudyAdvice_()` 新規関数

```javascript
function generateStudyAdvice_(scoreData) {
  var config = getConfigMap_();
  var apiKey = getConfigValue_(config, 'GEMINI_API_KEY', '');
  if (!apiKey) return '';

  var prompt = buildAdvicePrompt_(scoreData);

  var url = 'https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=' + apiKey;
  var payload = {
    contents: [{ parts: [{ text: prompt }] }],
    generationConfig: { maxOutputTokens: 500, temperature: 0.7 }
  };

  var options = {
    method: 'post',
    contentType: 'application/json',
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };

  try {
    var response = UrlFetchApp.fetch(url, options);
    var json = JSON.parse(response.getContentText());
    return json.candidates[0].content.parts[0].text || '';
  } catch (e) {
    Logger.log('Gemini API error: ' + e.message);
    return '';
  }
}
```

**`buildAdvicePrompt_(scoreData)`**: スコア、弱点タグ、セクション別成績、誤答パターンからプロンプトを構築。日本語で3-5行の具体的な学習アドバイスを要求。

### 3.3 api.gs — `apiSubmitTest()` に追加

スコア計算完了後、Gemini APIを呼び出して結果オブジェクトにadviceフィールドを追加:

```javascript
// apiSubmitTest 内、return直前
var advice = '';
try {
  advice = generateStudyAdvice_({
    scoreTotal: scoreTotal,
    totalQuestions: totalQuestions,
    weakTags: weakTags,
    sectionScores: sectionScores,
    wrongCount: wrongList.length
  });
} catch(e) {
  Logger.log('Advice generation failed: ' + e);
}
result.advice = advice;
```

### 3.4 index.html — Result画面にアドバイスセクション追加

**HTML (L537付近)**:
```html
<div id="result-advice"></div>  <!-- result-wrongの後に追加 -->
```

**renderResult() (L2757付近)**:
```javascript
// Gemini AIアドバイス表示
var adviceHtml = '';
if (res.advice) {
  adviceHtml = '<div class="card" style="background:#e8f5e9;margin-top:12px;padding:12px">'
    + '<div style="font-weight:bold;margin-bottom:6px">💡 AI学習アドバイス</div>'
    + '<div>' + escapeHtml(res.advice).replace(/\n/g, '<br>') + '</div>'
    + '</div>';
}
setHtml('result-advice', adviceHtml);
```

**エラー時/非表示時**: advice が空文字の場合はセクション非表示（setHtml で空文字）

---

## デプロイ順序

1. タスク1+2（UIのみ、リスク低）→ @53でデプロイ・検証
2. タスク3（Gemini API）→ APIキー登録後に @54でデプロイ・検証
   - または全て@53に含めてもよい（adviceが空なら何も表示されないため安全）

## 検証

### タスク1検証
- adminユーザーでログイン → Home画面でタブナビ表示確認
- ミニテスト開始 → タブナビが非表示になることを確認
- テスト完了 or 中断 → Homeに戻りタブナビが復元されることを確認

### タスク2検証
- テスト中に設問間を移動（次へ/前へ/番号クリック）→ 常にページ最上部から表示されることを確認

### タスク3検証
- `?action=updateConfig&key=GEMINI_API_KEY&value=<APIキー>` でキー登録
- テスト送信 → Result画面に「AI学習アドバイス」セクションが表示されることを確認
- APIキーなしの場合 → アドバイスセクションが表示されないことを確認
