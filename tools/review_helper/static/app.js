/**
 * 請求書レビューヘルパー - Frontend
 * Split-pane UI: form (left) + PDF.js preview (right)
 */

// --- PDF.js setup ---
import * as pdfjsLib from './pdfjs/pdf.min.mjs';
pdfjsLib.GlobalWorkerOptions.workerSrc = '/static/pdfjs/pdf.worker.min.mjs';

// --- State ---
let queue = [];
let currentIndex = -1;
let currentItem = null;
let selectedProject = null;
let ocrCandidates = {};  // OCR結果の候補値（自動入力しない）
let pdfDoc = null;
let currentPage = 1;
let pdfScale = 1.2;
let pdfRotation = 0;  // 0, 90, 180, 270
let timerStart = null;
let timerInterval = null;

// --- DOM refs ---
const $ = (sel) => document.querySelector(sel);
const queueCounter = $('#queue-counter');
const paymentMonth = $('#payment-month');
const currentFilename = $('#current-filename');
const senderDisplay = $('#sender-display');
const subjectDisplay = $('#subject-display');
const sourceBadge = $('#source-badge');
const ocrStatus = $('#ocr-status');
const fieldVendor = $('#field-vendor');
const fieldDate = $('#field-date');
const fieldAmount = $('#field-amount');
const fieldProject = $('#field-project');
const fieldKojiban = $('#field-kojiban');
const fieldDest = $('#field-dest');
const projectDropdown = $('#project-dropdown');
const btnConfirm = $('#btn-confirm');
const btnSkip = $('#btn-skip');
const btnExclude = $('#btn-exclude');
const btnPrev = $('#btn-prev');
const btnNext = $('#btn-next');
const timerEl = $('#timer');
const lastAction = $('#last-action');
const pdfCanvas = $('#pdf-canvas');
const pdfPlaceholder = $('#pdf-placeholder');
const pdfPageInfo = $('#pdf-page-info');

// --- API helpers ---
async function api(method, path, body = null) {
  const opts = { method, headers: {} };
  if (body) {
    opts.headers['Content-Type'] = 'application/json';
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(`/api/v1${path}`, opts);
  if (!res.ok) throw new Error(`API ${res.status}: ${await res.text()}`);
  return res.json();
}

// --- Load queue ---
async function loadQueue() {
  try {
    queue = await api('GET', '/queue');
    // Filter to pending items first, then others
    queue.sort((a, b) => {
      const order = { pending: 0, skipped: 1, excluded: 2, confirmed: 3 };
      return (order[a.state] ?? 9) - (order[b.state] ?? 9);
    });
    const pending = queue.filter(i => i.state === 'pending');
    queueCounter.textContent = `${pending.length}/${queue.length} 残り`;

    // Load stats for payment month
    const stats = await api('GET', '/stats');
    paymentMonth.textContent = `処理済: ${stats.confirmed}`;
  } catch (e) {
    console.error('Failed to load queue:', e);
  }
}

// --- Display item ---
async function displayItem(index) {
  if (index < 0 || index >= queue.length) return;
  currentIndex = index;
  currentItem = queue[index];
  selectedProject = null;

  // Update nav
  currentFilename.textContent = currentItem.filename;
  btnPrev.disabled = index === 0;
  btnNext.disabled = index === queue.length - 1;

  // Source badge
  sourceBadge.textContent = currentItem.source_dir;
  sourceBadge.className = 'badge ' +
    (currentItem.source_dir === 'unresolved' ? 'badge-unresolved' : 'badge-review');

  // Email context
  senderDisplay.textContent = currentItem.sender || '--';
  subjectDisplay.textContent = currentItem.subject || '--';

  // Pre-fill from manifest data
  fieldVendor.value = currentItem.vendor || '';
  fieldDate.value = currentItem.issue_date || '';
  fieldAmount.value = currentItem.amount || '';
  fieldProject.value = currentItem.project || '';
  fieldKojiban.textContent = '--';
  fieldDest.textContent = currentItem.route_subdir || '--';

  // Clear OCR candidates
  ocrCandidates = {};
  renderVendorCandidates();
  renderProjectCandidates(currentItem.subject_project_candidates || []);

  // Reset button state
  btnConfirm.disabled = true;
  checkConfirmReady();

  // Start timer
  startTimer();

  // Load PDF
  await loadPdf(currentItem.id);

  // Trigger OCR
  ocrStatus.textContent = 'OCR: 実行中...';
  ocrStatus.className = 'badge badge-neutral';
  const ocrItemId = currentItem.id;  // OCR 発行時の item_id を保存（race condition 防止）
  try {
    const ocr = await api('POST', `/queue/${ocrItemId}/ocr`);
    if (currentItem && currentItem.id === ocrItemId) {
      applyOcr(ocr);
    }
  } catch (e) {
    if (currentItem && currentItem.id === ocrItemId) {
      ocrStatus.textContent = 'OCR: エラー';
      ocrStatus.className = 'badge badge-unresolved';
    }
  }
}

async function applyOcr(ocr) {
  if (ocr.error) {
    ocrStatus.textContent = `OCR: ${ocr.error}`;
    ocrStatus.className = 'badge badge-unresolved';
    return;
  }
  ocrStatus.textContent = `OCR: ${ocr.provider || '完了'}${ocr.cached ? ' (cache)' : ''}`;
  ocrStatus.className = 'badge badge-success';

  // Store candidates (vendor shown as chip, not auto-filled)
  ocrCandidates = {
    vendor: ocr.vendor || null,
    issue_date: ocr.issue_date || null,
    amount: ocr.amount_total || ocr.amount || null,
  };

  // date/amount: fill empty fields as before (not rename-critical)
  if (!fieldDate.value && ocrCandidates.issue_date) fieldDate.value = ocrCandidates.issue_date;
  if (!fieldAmount.value && ocrCandidates.amount) fieldAmount.value = ocrCandidates.amount;

  // vendor: show as selectable chip instead of auto-filling
  renderVendorCandidates();

  // project_hint: OCRがPDFから工事名を抽出できた場合、プロジェクトマスタ検索して候補に追加
  if (ocr.project_hint && !selectedProject) {
    try {
      const results = await api('GET', `/projects?q=${encodeURIComponent(ocr.project_hint)}`);
      const existing = currentItem.subject_project_candidates || [];
      const merged = [...existing];
      for (const r of results) {
        if (!merged.find(e => e.kojiban === r.kojiban)) merged.push(r);
      }
      renderProjectCandidates(merged.slice(0, 5));
    } catch (e) { /* fallback to subject candidates only */ }
  }

  checkConfirmReady();
}

function renderProjectCandidates(candidates) {
  const container = $('#project-candidates');
  if (!candidates || candidates.length === 0) {
    container.classList.add('hidden');
    container.innerHTML = '';
    return;
  }
  container.innerHTML = candidates.map((p, i) =>
    `<span class="candidate-chip${selectedProject && selectedProject.kojiban === p.kojiban ? ' selected' : ''}"
           data-idx="${i}">件名: ${p.kojimei}</span>`
  ).join('');
  container.classList.remove('hidden');
  container.querySelectorAll('.candidate-chip').forEach((el, i) => {
    el.addEventListener('click', () => {
      selectProject(candidates[i]);
      renderProjectCandidates(candidates);  // selected状態を更新
    });
  });
}

function renderVendorCandidates() {
  const container = $('#vendor-candidates');
  if (!ocrCandidates.vendor) {
    container.classList.add('hidden');
    container.innerHTML = '';
    return;
  }
  const isSelected = fieldVendor.value === ocrCandidates.vendor;
  container.innerHTML = `<span class="candidate-chip${isSelected ? ' selected' : ''}" id="chip-vendor">OCR: ${ocrCandidates.vendor}</span>`;
  container.classList.remove('hidden');
  container.querySelector('#chip-vendor').addEventListener('click', () => {
    fieldVendor.value = ocrCandidates.vendor;
    renderVendorCandidates();
    checkConfirmReady();
  });
}

// --- PDF rendering ---
async function loadPdf(itemId) {
  pdfPlaceholder.style.display = 'none';
  pdfCanvas.style.display = 'block';
  $('#pdf-iframe').style.display = 'none';
  currentPage = 1;
  pdfRotation = 0;

  const url = `/api/v1/queue/${itemId}/pdf`;
  try {
    pdfDoc = await pdfjsLib.getDocument(url).promise;
    pdfPageInfo.textContent = `${currentPage} / ${pdfDoc.numPages}`;
    await renderPage(currentPage);
  } catch (e) {
    console.warn('PDF.js load failed, falling back to iframe:', e);
    // Sharp スキャナ等の非標準PDFはブラウザネイティブビューアにフォールバック
    pdfDoc = null;
    pdfCanvas.style.display = 'none';
    const iframe = $('#pdf-iframe');
    iframe.src = url;
    iframe.style.display = 'block';
    pdfPageInfo.textContent = '-- / --';
  }
}

async function renderPage(num) {
  if (!pdfDoc) return;
  const page = await pdfDoc.getPage(num);
  const viewport = page.getViewport({ scale: pdfScale, rotation: pdfRotation });
  pdfCanvas.width = viewport.width;
  pdfCanvas.height = viewport.height;
  const ctx = pdfCanvas.getContext('2d');
  await page.render({ canvasContext: ctx, viewport }).promise;
  pdfPageInfo.textContent = `${num} / ${pdfDoc.numPages}`;
}

// --- Project autocomplete ---
let searchTimeout = null;
let dropdownProjects = [];
let dropdownActiveIndex = -1;

function setDropdownActive(index) {
  dropdownActiveIndex = index;
  const items = projectDropdown.querySelectorAll('.dropdown-item');
  items.forEach((el, i) => el.classList.toggle('active', i === index));
  if (index >= 0 && items[index]) items[index].scrollIntoView({ block: 'nearest' });
}

fieldProject.addEventListener('keydown', (e) => {
  const isOpen = !projectDropdown.classList.contains('hidden');
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    if (isOpen) setDropdownActive(Math.min(dropdownActiveIndex + 1, dropdownProjects.length - 1));
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    if (isOpen) setDropdownActive(Math.max(dropdownActiveIndex - 1, 0));
  } else if ((e.key === 'Enter' || e.key === ' ') && isOpen && dropdownActiveIndex >= 0) {
    e.preventDefault();
    selectProject(dropdownProjects[dropdownActiveIndex]);
  } else if (e.key === 'Escape') {
    projectDropdown.classList.add('hidden');
    dropdownActiveIndex = -1;
  }
});

fieldProject.addEventListener('input', () => {
  clearTimeout(searchTimeout);
  const q = fieldProject.value.trim();
  if (q.length < 1) {
    projectDropdown.classList.add('hidden');
    selectedProject = null;
    fieldKojiban.textContent = '--';
    fieldDest.textContent = '--';
    checkConfirmReady();
    return;
  }
  searchTimeout = setTimeout(async () => {
    try {
      const results = await api('GET', `/projects?q=${encodeURIComponent(q)}`);
      showDropdown(results);
    } catch (e) {
      console.error('Project search error:', e);
    }
  }, 300);
});

function showDropdown(projects) {
  dropdownProjects = projects;
  dropdownActiveIndex = -1;
  if (!projects.length) {
    projectDropdown.classList.add('hidden');
    return;
  }
  projectDropdown.innerHTML = projects.map((p, i) =>
    `<div class="dropdown-item" data-index="${i}">
      ${p.kojimei} <span class="kojiban">${p.kojiban}</span>
    </div>`
  ).join('');
  projectDropdown.classList.remove('hidden');

  projectDropdown.querySelectorAll('.dropdown-item').forEach((el, i) => {
    el.addEventListener('click', () => selectProject(projects[i]));
  });
}

function selectProject(project) {
  selectedProject = project;
  fieldProject.value = project.kojimei;
  fieldKojiban.textContent = project.kojiban;
  fieldDest.textContent = project.route_subdir || '--';
  projectDropdown.classList.add('hidden');
  checkConfirmReady();
}

// Close dropdown on outside click
document.addEventListener('click', (e) => {
  if (!e.target.closest('.field-group')) {
    projectDropdown.classList.add('hidden');
  }
});

// --- Filename preview ---
function vendorShort(vendor) {
  return vendor.replace(/(株式会社|有限会社|合同会社|合資会社)/g, '').trim();
}
function sanitizeName(name) {
  return name.replace(/[\\/:*?"<>|]/g, '_').trim();
}
function buildFilename() {
  const vendor = fieldVendor.value.trim();
  const project = selectedProject ? selectedProject.kojimei.trim() : fieldProject.value.trim();
  const vendorPart = vendor ? sanitizeName(vendorShort(vendor)) : '（業者名）';
  const projectPart = project ? sanitizeName(project) : '（工事名）';
  return `${projectPart}_${vendorPart}.pdf`;
}

function updateFilenamePreview() {
  const preview = $('#filename-preview');
  const vendor = fieldVendor.value.trim();
  if (!vendor) {
    preview.textContent = '--';
    preview.classList.remove('preview-ready');
    return;
  }
  preview.textContent = buildFilename();
  preview.classList.add('preview-ready');
}

// --- Validation ---
function checkConfirmReady() {
  const ready = !!fieldVendor.value.trim();  // 業者名のみ必須。工事名は任意
  btnConfirm.disabled = !ready;
  updateFilenamePreview();
}

fieldVendor.addEventListener('input', checkConfirmReady);
fieldDate.addEventListener('input', checkConfirmReady);
fieldAmount.addEventListener('input', checkConfirmReady);

// --- Actions ---
async function confirmCurrent() {
  if (!currentItem || btnConfirm.disabled) return;
  btnConfirm.disabled = true;
  btnConfirm.textContent = '処理中...';

  const projectName = selectedProject ? selectedProject.kojimei : (fieldProject.value.trim() || '（工事名）');
  const routeSubdir = selectedProject ? (selectedProject.route_subdir || '') : '';

  try {
    await api('POST', `/queue/${currentItem.id}/confirm`, {
      vendor: fieldVendor.value.trim(),
      project: projectName,
      route_subdir: routeSubdir,
      issue_date: fieldDate.value.trim() || null,
      amount: fieldAmount.value.trim() || null,
      invoice_no: null,
    });

    lastAction.textContent = `✓ ${currentItem.filename} → 確定`;
    await loadQueue();
    advanceToNext();
  } catch (e) {
    alert(`確定エラー: ${e.message}`);
  } finally {
    btnConfirm.textContent = '確定 (Enter)';
  }
}

async function skipCurrent() {
  if (!currentItem) return;
  try {
    await api('POST', `/queue/${currentItem.id}/skip`);
    lastAction.textContent = `→ ${currentItem.filename} スキップ`;
    await loadQueue();
    advanceToNext();
  } catch (e) {
    alert(`スキップエラー: ${e.message}`);
  }
}

async function excludeCurrent() {
  if (!currentItem) return;
  if (!confirm('このファイルを非請求書として除外しますか？')) return;
  try {
    await api('POST', `/queue/${currentItem.id}/exclude`);
    lastAction.textContent = `✕ ${currentItem.filename} 除外`;
    await loadQueue();
    advanceToNext();
  } catch (e) {
    alert(`除外エラー: ${e.message}`);
  }
}

function advanceToNext() {
  // Find next pending item
  const nextPending = queue.findIndex(i => i.state === 'pending');
  if (nextPending >= 0) {
    displayItem(nextPending);
  } else {
    currentItem = null;
    currentFilename.textContent = '全件処理完了';
    pdfPlaceholder.textContent = '全てのPDFを処理しました';
    pdfPlaceholder.style.display = 'block';
    pdfCanvas.style.display = 'none';
    stopTimer();
  }
}

// --- Timer ---
function startTimer() {
  stopTimer();
  timerStart = Date.now();
  timerInterval = setInterval(() => {
    const elapsed = Math.floor((Date.now() - timerStart) / 1000);
    const min = Math.floor(elapsed / 60);
    const sec = String(elapsed % 60).padStart(2, '0');
    timerEl.textContent = `${min}:${sec}`;
  }, 1000);
}

function stopTimer() {
  if (timerInterval) clearInterval(timerInterval);
  timerInterval = null;
}

// --- PDF controls ---
$('#pdf-prev-page')?.addEventListener('click', async () => {
  if (pdfDoc && currentPage > 1) { currentPage--; await renderPage(currentPage); }
});
$('#pdf-next-page')?.addEventListener('click', async () => {
  if (pdfDoc && currentPage < pdfDoc.numPages) { currentPage++; await renderPage(currentPage); }
});
$('#pdf-zoom-in')?.addEventListener('click', async () => {
  pdfScale += 0.2; await renderPage(currentPage);
});
$('#pdf-zoom-out')?.addEventListener('click', async () => {
  if (pdfScale > 0.4) { pdfScale -= 0.2; await renderPage(currentPage); }
});
$('#pdf-rotate-ccw')?.addEventListener('click', async () => {
  pdfRotation = (pdfRotation + 270) % 360; await renderPage(currentPage);
});
$('#pdf-rotate-cw')?.addEventListener('click', async () => {
  pdfRotation = (pdfRotation + 90) % 360; await renderPage(currentPage);
});

// --- Button handlers ---
btnConfirm.addEventListener('click', confirmCurrent);
btnSkip.addEventListener('click', skipCurrent);
btnExclude.addEventListener('click', excludeCurrent);
btnPrev.addEventListener('click', () => {
  if (currentIndex > 0) displayItem(currentIndex - 1);
});
btnNext.addEventListener('click', () => {
  if (currentIndex < queue.length - 1) displayItem(currentIndex + 1);
});

// --- Keyboard shortcuts ---
document.addEventListener('keydown', (e) => {
  // Don't trigger shortcuts when typing in inputs
  if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
    if (e.key === 'Escape') {
      e.target.blur();
      e.preventDefault();
    }
    return;
  }

  if (e.key === 'Enter') { e.preventDefault(); confirmCurrent(); }
  if (e.key === 'Escape') { e.preventDefault(); skipCurrent(); }
});

// --- Init ---
(async () => {
  await loadQueue();
  if (queue.length > 0) {
    const firstPending = queue.findIndex(i => i.state === 'pending');
    displayItem(firstPending >= 0 ? firstPending : 0);
  }
})();
