// AudioBook Studio Client
let currentSessionId = null;
let progressInterval = null;
let loadedDictionary = {};
let activeChunks = [];
let selectedFormat = 'mp3';
let voicesData = [];

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initServerStatus();
  initVoices();
  initDictionary();
  initStudio();
});

// --- Tab Navigation ---
function initTabs() {
  const pills = document.querySelectorAll('.nav-pill');
  const panes = document.querySelectorAll('.tab-pane');

  pills.forEach(pill => {
    pill.addEventListener('click', () => {
      const tabId = pill.getAttribute('data-tab');
      pills.forEach(p => p.classList.remove('active'));
      panes.forEach(p => p.classList.remove('active'));

      pill.classList.add('active');
      const targetPane = document.getElementById(`tab-${tabId}`);
      if (targetPane) targetPane.classList.add('active');

      if (tabId === 'dictionary') loadDictionary();
      if (tabId === 'voices') loadVoices();
    });
  });
}

// --- Status Poller ---
async function initServerStatus() {
  const dot = document.getElementById('statusDot');
  const text = document.getElementById('statusText');

  async function check() {
    try {
      const res = await fetch('/api/status');
      const data = await res.json();
      if (data.fish_audio_connected) {
        dot.className = 'status-dot online';
        text.textContent = 'Flash Audio Онлайн (:8020)';
      } else {
        dot.className = 'status-dot offline';
        text.textContent = 'Сервер :8020 оффлайн';
      }
    } catch (e) {
      dot.className = 'status-dot offline';
      text.textContent = 'Бэкенд не отвечает';
    }
  }

  check();
  setInterval(check, 8000);
}

// --- Voices ---
async function initVoices() {
  loadVoices();

  const newVoiceForm = document.getElementById('newVoiceForm');
  if (newVoiceForm) {
    newVoiceForm.addEventListener('submit', async (e) => {
      e.preventDefault();
      const name = document.getElementById('newVoiceName').value.trim();
      const audio = document.getElementById('newVoiceAudio').files[0];
      const text = document.getElementById('newVoiceText').value.trim();

      if (!audio) {
        alert('Пожалуйста, выберите аудиофайл');
        return;
      }

      const formData = new FormData();
      formData.append('name', name);
      formData.append('audio', audio);
      formData.append('text', text);

      try {
        const res = await fetch('/api/voices', { method: 'POST', body: formData });
        if (!res.ok) throw new Error('Ошибка добавления голоса');
        alert('Голосовой профиль сохранен!');
        newVoiceForm.reset();
        loadVoices();
      } catch (err) {
        alert(err.message);
      }
    });
  }

  let referenceAudioInstance = null;
  const btnListenRef = document.getElementById('btnListenRef');
  const btnStopRef = document.getElementById('btnStopRef');

  if (btnListenRef) {
    btnListenRef.addEventListener('click', () => {
      const defaultVoice = voicesData.find(v => v.name === 'default') || voicesData[0];
      if (defaultVoice) {
        if (referenceAudioInstance) {
          referenceAudioInstance.pause();
          referenceAudioInstance.currentTime = 0;
        }
        const filename = defaultVoice.audio_path.split('/').pop();
        referenceAudioInstance = new Audio(`/api/audio/voice/${filename}`);
        referenceAudioInstance.play().catch(() => alert('Не удалось воспроизвести файл референса'));
      }
    });
  }

  if (btnStopRef) {
    btnStopRef.addEventListener('click', () => {
      if (referenceAudioInstance) {
        referenceAudioInstance.pause();
        referenceAudioInstance.currentTime = 0;
      }
    });
  }
}

async function loadVoices() {
  try {
    const res = await fetch('/api/voices');
    voicesData = await res.json();

    const activeVoice = voicesData.find(v => v.name === 'default') || voicesData[0];
    if (activeVoice) {
      const nameEl = document.getElementById('activeVoiceName');
      const captionEl = document.getElementById('voiceSampleCaption');
      if (nameEl) nameEl.textContent = activeVoice.name === 'default' ? 'Мой голос (Default)' : activeVoice.name;
      if (captionEl) captionEl.textContent = `«${activeVoice.text}»`;
    }

    const container = document.getElementById('voicesListContainer');
    if (container) {
      container.innerHTML = '';
      voicesData.forEach(v => {
        const card = document.createElement('div');
        card.className = 'voice-card-modern';
        const filename = v.audio_path.split('/').pop();
        card.innerHTML = `
          <div class="voice-card-header">
            <span class="voice-card-name">${v.name === 'default' ? '⭐️ Основной голос (Default)' : v.name}</span>
            ${v.name !== 'default' ? `<button class="btn-del" onclick="deleteVoice('${v.name}')">Удалить</button>` : ''}
          </div>
          <p class="voice-card-text">«${v.text}»</p>
          <audio controls class="custom-audio-player" src="/api/audio/voice/${filename}"></audio>
        `;
        container.appendChild(card);
      });
    }
  } catch (e) {
    console.error('Ошибка загрузки голосов:', e);
  }
}

async function deleteVoice(name) {
  if (!confirm(`Удалить голос "${name}"?`)) return;
  try {
    const res = await fetch(`/api/voices/${encodeURIComponent(name)}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Ошибка удаления');
    loadVoices();
  } catch (e) {
    alert(e.message);
  }
}

// --- Dictionary Management ---
async function initDictionary() {
  loadDictionary();

  const searchInput = document.getElementById('dictSearch');
  if (searchInput) {
    searchInput.addEventListener('input', (e) => renderDictionaryTable(e.target.value));
  }

  const btnInsert = document.getElementById('btnInsertStress');
  const replInput = document.getElementById('dictNewRepl');
  if (btnInsert && replInput) {
    btnInsert.addEventListener('click', () => {
      const start = replInput.selectionStart;
      const end = replInput.selectionEnd;
      const val = replInput.value;
      const stressChar = '\u0301'; // Combining acute accent
      replInput.value = val.substring(0, start) + stressChar + val.substring(end);
      replInput.focus();
      replInput.selectionStart = replInput.selectionEnd = start + 1;
    });
  }

  const btnAdd = document.getElementById('btnAddDictWord');
  if (btnAdd) {
    btnAdd.addEventListener('click', async () => {
      const wordInput = document.getElementById('dictNewWord');
      const word = wordInput.value.trim();
      const repl = replInput.value.trim();

      if (!word || !repl) {
        alert('Заполните оба поля!');
        return;
      }

      try {
        const res = await fetch('/api/dictionary', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ word, replacement: repl })
        });
        if (!res.ok) throw new Error('Ошибка добавления');
        wordInput.value = '';
        replInput.value = '';
        loadDictionary();
      } catch (e) {
        alert(e.message);
      }
    });
  }
}

async function loadDictionary() {
  try {
    const res = await fetch('/api/dictionary');
    loadedDictionary = await res.json();
    const count = Object.keys(loadedDictionary).length;
    const tabEl = document.getElementById('tabDictCount');
    const totalEl = document.getElementById('dictTotalCount');
    if (tabEl) tabEl.textContent = count;
    if (totalEl) totalEl.textContent = count;
    renderDictionaryTable();
  } catch (e) {
    console.error('Ошибка загрузки словаря:', e);
  }
}

function renderDictionaryTable(filter = '') {
  const tbody = document.getElementById('dictTableBody');
  if (!tbody) return;

  tbody.innerHTML = '';
  const entries = Object.entries(loadedDictionary).filter(([w, r]) => {
    return w.toLowerCase().includes(filter.toLowerCase()) || r.toLowerCase().includes(filter.toLowerCase());
  });

  entries.forEach(([word, repl]) => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${escapeHtml(word)}</strong></td>
      <td><span style="color: #0d382c; font-weight: 700;">${escapeHtml(repl)}</span></td>
      <td style="text-align: right;">
        <button class="btn-del" onclick="deleteDictWord('${escapeHtml(word)}')">Удалить</button>
      </td>
    `;
    tbody.appendChild(tr);
  });
}

async function deleteDictWord(word) {
  if (!confirm(`Удалить "${word}" из словаря?`)) return;
  try {
    const res = await fetch(`/api/dictionary/${encodeURIComponent(word)}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Ошибка удаления');
    loadDictionary();
  } catch (e) {
    alert(e.message);
  }
}

// --- Main Studio Interactions ---
function initStudio() {
  const dropZone = document.getElementById('dropZone');
  const fileInput = document.getElementById('fileInput');
  const btnChooseFile = document.getElementById('btnChooseFile');
  const rawTextInput = document.getElementById('rawTextInput');
  const btnApplyStress = document.getElementById('btnApplyStressPreview');
  const btnStartTTS = document.getElementById('btnStartTTS');
  const btnCopyText = document.getElementById('btnCopyText');
  const btnClearText = document.getElementById('btnClearText');
  const statCharCount = document.getElementById('statCharCount');

  // Format Toggle
  const formatButtons = document.querySelectorAll('#formatToggle .seg-btn');
  formatButtons.forEach(btn => {
    btn.addEventListener('click', () => {
      formatButtons.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      selectedFormat = btn.getAttribute('data-value');
      document.getElementById('badgeFormat').textContent = selectedFormat === 'mp3' ? 'MP3 (256k)' : 'WAV (Hi-Fi)';
    });
  });

  // Range sliders
  bindSlider('paramPause', 'valPause', '');
  bindSlider('paramSpeed', 'valSpeed', '');

  // Live text input character counter
  rawTextInput.addEventListener('input', () => {
    statCharCount.textContent = rawTextInput.value.length;
    if (rawTextInput.value.length > 0) {
      updateTimeline(15, `${rawTextInput.value.length} символов`);
    }
  });

  // Clear text button
  if (btnClearText) {
    btnClearText.addEventListener('click', () => {
      rawTextInput.value = '';
      statCharCount.textContent = '0';
      activeChunks = [];
      renderChunksGrid([]);
      updateTimeline(10, 'Текст очищен');
    });
  }

  // Choose file button
  if (btnChooseFile) {
    btnChooseFile.addEventListener('click', (e) => {
      e.stopPropagation();
      fileInput.click();
    });
  }

  // Dropzone drag-and-drop
  if (dropZone) {
    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropZone.classList.add('dragover');
    });
    dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
    dropZone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropZone.classList.remove('dragover');
      if (e.dataTransfer.files.length) handleFileUpload(e.dataTransfer.files[0]);
    });
  }

  if (fileInput) {
    fileInput.addEventListener('change', (e) => {
      if (e.target.files.length) handleFileUpload(e.target.files[0]);
    });
  }

  // Copy text button
  if (btnCopyText) {
    btnCopyText.addEventListener('click', () => {
      const text = rawTextInput.value;
      if (text) {
        navigator.clipboard.writeText(text);
        btnCopyText.textContent = '✓ Скопировано';
        setTimeout(() => btnCopyText.textContent = '📋 Копировать', 2000);
      }
    });
  }

  // Apply Stress & Split into Chunks Preview
  if (btnApplyStress) {
    btnApplyStress.addEventListener('click', async () => {
      const text = rawTextInput.value.trim();
      if (!text) {
        alert('Сначала загрузите PDF/TXT файл или вставьте текст в поле выше!');
        return;
      }
      try {
        btnApplyStress.disabled = true;
        btnApplyStress.textContent = 'Обработка текста и ударений...';
        const res = await fetch('/api/preview', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, max_chunk_len: 1000 })
        });
        const data = await res.json();
        activeChunks = data.chunks;
        renderChunksGrid(activeChunks);

        updateTimeline(40, `Разбито на ${data.chunks.length} чанков`);
        setMilestoneActive('msChunk');
      } catch (e) {
        alert('Ошибка обработки: ' + e.message);
      } finally {
        btnApplyStress.disabled = false;
        btnApplyStress.innerHTML = '<span>🔍 Разобрать текст и расставить ударения</span>';
      }
    });
  }

  // Start TTS Pipeline
  if (btnStartTTS) {
    btnStartTTS.addEventListener('click', async () => {
      const chunkInputs = document.querySelectorAll('.chunk-editor');
      let chunksToSend = [];
      if (chunkInputs.length > 0) {
        chunksToSend = Array.from(chunkInputs).map(i => i.value.trim()).filter(Boolean);
      }

      const rawText = rawTextInput.value.trim();
      if (chunksToSend.length === 0 && !rawText) {
        alert('Нет текста для озвучки! Вставьте текст или загрузите файл.');
        return;
      }

      const payload = {
        chunks: chunksToSend.length > 0 ? chunksToSend : null,
        text: chunksToSend.length === 0 ? rawText : null,
        voice_name: 'default',
        output_name: document.getElementById('outputNameInput').value.trim() || null,
        output_format: selectedFormat,
        pause_duration: parseFloat(document.getElementById('paramPause').value),
        speed: parseFloat(document.getElementById('paramSpeed').value),
        apply_loudnorm: true
      };

      try {
        btnStartTTS.disabled = true;
        btnStartTTS.textContent = '⏳ Синтез аудио...';
        const res = await fetch('/api/generate', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
        if (!res.ok) throw new Error('Ошибка запуска генерации');
        const data = await res.json();
        currentSessionId = data.session_id;
        startProgressPolling();
      } catch (e) {
        alert('Не удалось начать: ' + e.message);
        btnStartTTS.disabled = false;
        btnStartTTS.textContent = '🚀 Начать озвучку книги';
      }
    });
  }
}

function bindSlider(id, labelId, unit) {
  const slider = document.getElementById(id);
  const label = document.getElementById(labelId);
  if (slider && label) {
    slider.addEventListener('input', () => label.textContent = slider.value + unit);
  }
}

async function handleFileUpload(file) {
  const formData = new FormData();
  formData.append('file', file);

  const titleEl = document.getElementById('vaultTitle');
  const subEl = document.getElementById('vaultSub');
  titleEl.textContent = `Чтение: ${file.name}...`;

  try {
    const res = await fetch('/api/extract', { method: 'POST', body: formData });
    if (!res.ok) throw new Error('Ошибка чтения файла');
    const data = await res.json();

    document.getElementById('rawTextInput').value = data.stressed_text;
    document.getElementById('statCharCount').textContent = data.total_chars;
    document.getElementById('outputNameInput').value = file.name.replace(/\.[^/.]+$/, "");

    activeChunks = data.chunks;
    renderChunksGrid(activeChunks);

    titleEl.textContent = `✓ Загружен: ${file.name}`;
    subEl.textContent = `${data.total_chars} символов, ${data.chunk_count} фрагментов`;

    updateTimeline(30, 'Файл прочитан и расставлены ударения');
    setMilestoneActive('msStress');
  } catch (e) {
    alert('Ошибка при загрузке: ' + e.message);
    titleEl.textContent = 'Перетащите PDF или текстовый файл сюда';
    subEl.textContent = 'или нажмите на эту область для выбора файла';
  }
}

function renderChunksGrid(chunks, statuses = []) {
  const container = document.getElementById('chunksGrid');
  const badge = document.getElementById('activeChunksCountBadge');
  const scaleBadge = document.getElementById('overviewChunkCount');
  if (!container) return;

  container.innerHTML = '';
  if (badge) badge.textContent = `${chunks.length} чанков`;
  if (scaleBadge) scaleBadge.textContent = `0 / ${chunks.length}`;

  if (chunks.length === 0) {
    container.innerHTML = `
      <div class="empty-chunks-placeholder">
        <div class="placeholder-icon">✍️</div>
        <h4>Чанки еще не сформированы</h4>
        <p>Загрузите PDF/TXT файл или вставьте текст в поле выше и нажмите кнопку <strong>«Разобрать текст и расставить ударения»</strong>.</p>
      </div>
    `;
    return;
  }

  chunks.forEach((text, idx) => {
    const statusObj = statuses[idx] || { status: 'pending', audio_url: null };
    const card = document.createElement('div');
    card.className = `chunk-card-modern ${statusObj.status}`;
    card.id = `chunkCardModern-${idx}`;

    let statusText = 'Ожидание';
    if (statusObj.status === 'generating') statusText = 'Синтез...';
    if (statusObj.status === 'done') statusText = 'Готово ✓';
    if (statusObj.status === 'error') statusText = 'Ошибка ✕';

    card.innerHTML = `
      <div class="chunk-card-top">
        <span class="chunk-num">ЧАНК #${idx + 1} (${text.length} симв.)</span>
        <span class="chunk-status-chip ${statusObj.status}">${statusText}</span>
      </div>
      <textarea class="chunk-editor" rows="3">${escapeHtml(text)}</textarea>
      ${statusObj.audio_url ? `<audio controls class="chunk-audio-mini" src="${statusObj.audio_url}"></audio>` : ''}
    `;
    container.appendChild(card);
  });
}

function startProgressPolling() {
  const finalBox = document.getElementById('finalPlayerBox');
  const mainPlayer = document.getElementById('mainAudioPlayer');
  const btnDownload = document.getElementById('btnDownloadFinal');
  const btnOpenFolder = document.getElementById('btnOpenFolder');
  const finalFilename = document.getElementById('finalFilenameText');
  const scaleBadge = document.getElementById('overviewChunkCount');
  const btnStartTTS = document.getElementById('btnStartTTS');
  const statusMsg = document.getElementById('pipelineStatusMessage');

  if (btnOpenFolder) {
    btnOpenFolder.onclick = async () => {
      try {
        await fetch('/api/open-output-folder', { method: 'POST' });
      } catch (e) {
        console.error('Ошибка открытия папки:', e);
      }
    };
  }

  if (finalBox) finalBox.classList.add('hidden');
  setMilestoneActive('msTTS');

  if (progressInterval) clearInterval(progressInterval);

  progressInterval = setInterval(async () => {
    if (!currentSessionId) return;

    try {
      const res = await fetch(`/api/progress/${currentSessionId}`);
      if (!res.ok) return;
      const data = await res.json();

      const total = data.total_chunks || 1;
      const current = data.current_chunk || 0;
      const pct = Math.min(100, Math.round(40 + (current / total) * 60));

      updateTimeline(pct, `Озвучка: ${current}/${total}`);
      if (scaleBadge) scaleBadge.textContent = `${current} / ${total}`;
      if (statusMsg) statusMsg.textContent = data.message || `Синтез фрагментов: ${current} из ${total}`;

      // Update chunk cards
      if (data.chunks && data.chunks.length > 0) {
        data.chunks.forEach((c, idx) => {
          const card = document.getElementById(`chunkCardModern-${idx}`);
          if (card) {
            card.className = `chunk-card-modern ${c.status}`;
            const chip = card.querySelector('.chunk-status-chip');
            if (chip) {
              chip.className = `chunk-status-chip ${c.status}`;
              if (c.status === 'generating') chip.textContent = 'Синтез...';
              else if (c.status === 'done') chip.textContent = 'Готово ✓';
              else if (c.status === 'error') chip.textContent = 'Ошибка ✕';
            }
            if (c.audio_url && !card.querySelector('audio')) {
              const audio = document.createElement('audio');
              audio.controls = true;
              audio.className = 'chunk-audio-mini';
              audio.src = c.audio_url;
              card.appendChild(audio);
            }
          }
        });
      }

      if (data.status === 'completed') {
        clearInterval(progressInterval);
        btnStartTTS.disabled = false;
        btnStartTTS.textContent = '🚀 Начать озвучку книги';
        updateTimeline(100, 'Склейка завершена!');
        setMilestoneActive('msReady');
        if (statusMsg) statusMsg.textContent = 'Готово! Аудиокнига успешно создана.';

        if (data.output_url) {
          finalBox.classList.remove('hidden');
          mainPlayer.src = data.output_url;
          btnDownload.href = data.output_url;
          finalFilename.textContent = data.output_url.split('/').pop();
        }
      } else if (data.status === 'error') {
        clearInterval(progressInterval);
        btnStartTTS.disabled = false;
        btnStartTTS.textContent = '🚀 Начать озвучку книги';
        if (statusMsg) statusMsg.textContent = 'Ошибка генерации: ' + data.error;
        alert('Ошибка генерации: ' + data.error);
      }
    } catch (e) {
      console.error('Ошибка прогресса:', e);
    }
  }, 1000);
}

function updateTimeline(percent, tooltipText) {
  const bar = document.getElementById('timelineBarFill');
  const avatar = document.getElementById('timelineAvatar');
  const tooltip = document.getElementById('timelineTooltip');

  if (bar) bar.style.width = `${percent}%`;
  if (avatar) avatar.style.left = `${percent}%`;
  if (tooltip && tooltipText) tooltip.textContent = tooltipText;
}

function setMilestoneActive(id) {
  document.querySelectorAll('.ms-label').forEach(el => el.classList.remove('active'));
  const target = document.getElementById(id);
  if (target) target.classList.add('active');
}

function escapeHtml(string) {
  if (!string) return '';
  return String(string)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#039;');
}
