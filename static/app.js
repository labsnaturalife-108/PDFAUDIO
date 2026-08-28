// AudioBook Studio Client
let currentSessionId = null;
let progressInterval = null;
let loadedDictionary = {};
let loadedChapters = [];
let activeChapterId = null;
let activeChunks = [];
let selectedFormat = 'mp3';
let voicesData = [];
let isBatchRunning = false;
let currentTtsProvider = 'fish_audio';

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initServerStatus();
  initVoices();
  initDictionary();
  initVedicCleaner();
  initStudio();
  initLumeanAndSettings();
  initOutputModal();
});

// --- Output Folder Modal & Explorer ---
function initOutputModal() {
  const modal = document.getElementById('outputFolderModal');
  const btnClose = document.getElementById('btnCloseModal');
  const btnTriggerFinder = document.getElementById('btnTriggerFinderOpen');
  const btnOpenFolder = document.getElementById('btnOpenFolder');
  const btnRefresh = document.getElementById('btnRefreshOutputs');

  if (btnRefresh) {
    btnRefresh.addEventListener('click', () => {
      btnRefresh.textContent = '⏳ Загрузка...';
      loadOutputFiles().finally(() => {
        btnRefresh.textContent = '🔄 Обновить';
      });
    });
  }

  async function openModal() {
    if (modal) modal.classList.remove('hidden');
    try {
      fetch('/api/open-output-folder', { method: 'POST' });
    } catch (e) {}
    loadOutputFiles();
  }

  function closeModal() {
    if (modal) modal.classList.add('hidden');
  }

  if (btnOpenFolder) btnOpenFolder.addEventListener('click', openModal);
  if (btnClose) btnClose.addEventListener('click', closeModal);
  if (modal) {
    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });
  }

  if (btnTriggerFinder) {
    btnTriggerFinder.addEventListener('click', async () => {
      try {
        await fetch('/api/open-output-folder', { method: 'POST' });
        btnTriggerFinder.textContent = '✓ Открыто';
        setTimeout(() => btnTriggerFinder.textContent = '🖥️ Открыть в Finder', 2000);
      } catch (e) {
        alert('Не удалось открыть Finder');
      }
    });
  }
}

async function loadOutputFiles() {
  const container = document.getElementById('modalFilesList');
  const pathLabel = document.getElementById('modalFolderPath');
  if (!container) return;

  try {
    const res = await fetch('/api/outputs');
    const data = await res.json();
    if (pathLabel && data.folder_path) pathLabel.textContent = data.folder_path;

    if (!data.files || data.files.length === 0) {
      container.innerHTML = '<div class="empty-state-mini">В папке output пока нет готовых аудиофайлов.</div>';
      return;
    }

    container.innerHTML = '';
    data.files.forEach(f => {
      const card = document.createElement('div');
      card.className = 'file-item-card';
      card.innerHTML = `
        <div class="file-item-top">
          <span class="file-item-title">🎵 ${escapeHtml(f.name)}</span>
          <span class="file-item-meta">${f.size_mb} MB • ${f.date}</span>
        </div>
        <audio controls class="custom-audio-player" src="${f.url}"></audio>
        <div class="file-item-actions">
          <a href="${f.url}" download="${escapeHtml(f.name)}" class="btn-sm-text">⬇️ Скачать этот файл</a>
        </div>
      `;
      container.appendChild(card);
    });
  } catch (e) {
    container.innerHTML = '<div class="empty-state-mini">Ошибка загрузки списка файлов.</div>';
  }
}

// --- Vedic Text Cleaner Tab ---
function initVedicCleaner() {
  const rawInput = document.getElementById('vedicRawInput');
  const cleanedOutput = document.getElementById('vedicCleanedOutput');
  const rawCharCount = document.getElementById('vedicRawCharCount');
  const cleanCharCount = document.getElementById('vedicCleanCharCount');
  const removedBadge = document.getElementById('vedicRemovedBadge');
  const btnClean = document.getElementById('btnCleanVedicText');
  const btnClear = document.getElementById('btnClearVedicRaw');
  const btnCopy = document.getElementById('btnCopyVedicCleaned');
  const btnDownload = document.getElementById('btnDownloadVedicCleaned');
  const btnSendToStudio = document.getElementById('btnSendToStudio');
  const dropZone = document.getElementById('vedicDropZone');
  const fileInput = document.getElementById('vedicFileInput');
  const btnChooseFile = document.getElementById('btnVedicChooseFile');

  if (rawInput && rawCharCount) {
    rawInput.addEventListener('input', () => {
      rawCharCount.textContent = rawInput.value.length;
    });
  }

  if (btnClear) {
    btnClear.addEventListener('click', () => {
      rawInput.value = '';
      rawCharCount.textContent = '0';
      cleanedOutput.value = '';
      cleanCharCount.textContent = '0';
      removedBadge.textContent = 'Удалено: 0%';
    });
  }

  if (btnChooseFile && fileInput) {
    btnChooseFile.addEventListener('click', (e) => {
      e.stopPropagation();
      fileInput.click();
    });
  }

  if (dropZone && fileInput) {
    dropZone.addEventListener('click', () => fileInput.click());
    dropZone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropZone.style.borderColor = 'var(--bg-emerald)';
      dropZone.style.background = '#f0fdf4';
    });
    dropZone.addEventListener('dragleave', () => {
      dropZone.style.borderColor = '#cbd5e1';
      dropZone.style.background = '#fafaf9';
    });
    dropZone.addEventListener('drop', async (e) => {
      e.preventDefault();
      dropZone.style.borderColor = '#cbd5e1';
      dropZone.style.background = '#fafaf9';
      if (e.dataTransfer.files.length) {
        handleVedicFileUpload(e.dataTransfer.files[0]);
      }
    });

    fileInput.addEventListener('change', (e) => {
      if (e.target.files.length) {
        handleVedicFileUpload(e.target.files[0]);
      }
    });
  }

  let currentVedicOriginalFileName = '';

  async function handleVedicFileUpload(file) {
    const formData = new FormData();
    formData.append('file', file);
    currentVedicOriginalFileName = file.name.replace(/\.[^/.]+$/, "");

    try {
      if (btnClean) {
        btnClean.disabled = true;
        btnClean.textContent = `Чтение и очистка файла ${file.name}...`;
      }
      const res = await fetch('/api/vedic/clean-file', { method: 'POST', body: formData });
      if (!res.ok) throw new Error('Ошибка обработки файла');
      const data = await res.json();

      rawInput.value = `[Загружен файл: ${file.name}, исходных символов: ${data.original_chars}]\n\n` + data.cleaned_text.slice(0, 1000) + '...';
      rawCharCount.textContent = data.original_chars;

      cleanedOutput.value = data.cleaned_text;
      cleanCharCount.textContent = data.cleaned_chars;
      removedBadge.textContent = `Удалено: ${data.removed_chars} (${data.percent_removed}%)`;
    } catch (e) {
      alert('Ошибка при очистке файла: ' + e.message);
    } finally {
      if (btnClean) {
        btnClean.disabled = false;
        btnClean.innerHTML = '<span>✨ Очистить от санскрита и пословного перевода</span>';
      }
    }
  }

  if (btnClean) {
    btnClean.addEventListener('click', async () => {
      const text = rawInput.value.trim();
      if (!text) {
        alert('Пожалуйста, вставьте текст с санскритом или загрузите файл слева!');
        return;
      }

      // If user pasted text without file upload, derive file name from first line
      if (!currentVedicOriginalFileName) {
        const firstLine = text.split('\n')[0].trim();
        if (firstLine) {
          currentVedicOriginalFileName = firstLine.replace(/[^\w\sа-яА-ЯёЁ.-]/gi, '_').replace(/\s+/g, '_').slice(0, 80);
        }
      }

      try {
        btnClean.disabled = true;
        btnClean.textContent = '⏳ Очистка текста от санскрита...';

        const res = await fetch('/api/vedic/clean', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text })
        });
        if (!res.ok) throw new Error('Ошибка очистки текста');
        const data = await res.json();

        cleanedOutput.value = data.cleaned_text;
        cleanCharCount.textContent = data.cleaned_chars;
        removedBadge.textContent = `Удалено: ${data.removed_chars} (${data.percent_removed}%)`;
      } catch (e) {
        alert(e.message);
      } finally {
        btnClean.disabled = false;
        btnClean.innerHTML = '<span>✨ Очистить от санскрита и пословного перевода</span>';
      }
    });
  }

  if (btnCopy) {
    btnCopy.addEventListener('click', () => {
      const text = cleanedOutput.value;
      if (!text) {
        alert('Нет очищенного текста для копирования!');
        return;
      }
      navigator.clipboard.writeText(text);
      btnCopy.textContent = '✓ Скопировано';
      setTimeout(() => btnCopy.textContent = '📋 Скопировать', 2000);
    });
  }

  window.downloadVedicCleanedFile = function(event) {
    if (event) {
      try { event.preventDefault(); event.stopPropagation(); } catch (e) {}
    }
    const cleanedOutput = document.getElementById('vedicCleanedOutput');
    const rawInput = document.getElementById('vedicRawInput');
    const text = cleanedOutput ? cleanedOutput.value : '';
    if (!text || !text.trim()) {
      alert('Нет очищенного текста для скачивания!');
      return;
    }

    let baseName = currentVedicOriginalFileName;
    if (!baseName && rawInput && rawInput.value) {
      const mFile = rawInput.value.match(/\[Загружен файл:\s*([^,\]]+)/i);
      if (mFile) {
        baseName = mFile[1].replace(/\.[^/.]+$/, "").trim();
      }
    }

    if (!baseName) {
      const lines = text.split('\n').map(l => l.trim()).filter(l => l.length > 0);
      for (const l of lines) {
        if (l.length >= 3 && !l.startsWith('ТЕКСТ') && !l.startsWith('TEXT')) {
          baseName = l.replace(/[^\w\sа-яА-ЯёЁ.-]/gi, '_').replace(/\s+/g, '_').slice(0, 80);
          break;
        }
      }
    }

    if (!baseName) baseName = 'cleaned_text';
    baseName = baseName.replace(/_end$/i, ''); // prevent double _end
    const downloadFileName = `${baseName}_end.txt`;

    const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = downloadFileName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  if (btnDownload) {
    btnDownload.onclick = window.downloadVedicCleanedFile;
  }

  if (btnSendToStudio) {
    btnSendToStudio.addEventListener('click', () => {
      const text = cleanedOutput.value.trim();
      if (!text) {
        alert('Сначала выполните очистку текста!');
        return;
      }
      // Switch to Studio Tab
      const studioTabBtn = document.querySelector('.nav-pill[data-tab="studio"]');
      if (studioTabBtn) studioTabBtn.click();

      // Put text into main raw text area
      const studioInput = document.getElementById('rawTextInput');
      if (studioInput) {
        studioInput.value = text;
        const charCountEl = document.getElementById('statCharCount');
        if (charCountEl) charCountEl.textContent = text.length;
      }

      // Automatically trigger chapter & stress parsing
      const btnApplyStress = document.getElementById('btnApplyStressPreview');
      if (btnApplyStress) {
        btnApplyStress.click();
      }
    });
  }
}

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

function getTtsProviderPayload() {
  const isLumean = currentTtsProvider === 'lumean';
  const lumeanVoiceInput = document.getElementById('lumeanVoiceIdInput');
  const lumeanVoiceId = lumeanVoiceInput ? lumeanVoiceInput.value.trim() : '';
  return {
    provider: currentTtsProvider,
    lumean_voice_id: isLumean ? (lumeanVoiceId || '1') : null
  };
}

function initLumeanAndSettings() {
  const engineBtns = document.querySelectorAll('#ttsEngineToggle .seg-btn');
  const fishSection = document.getElementById('fishAudioVoiceSection');
  const lumeanSection = document.getElementById('lumeanVoiceSection');
  const lumeanVoiceInput = document.getElementById('lumeanVoiceIdInput');
  const lumeanDisplay = document.getElementById('activeLumeanVoiceDisplay');
  const btnTestLumeanQuick = document.getElementById('btnTestLumeanQuick');
  const btnCheckLumeanLive = document.getElementById('btnCheckLumeanLive');
  const btnSaveSettings = document.getElementById('btnSaveLumeanSettings');
  const apiKeyInput = document.getElementById('settingLumeanApiKey');
  const bearerTokenInput = document.getElementById('settingLumeanBearerToken');
  const defaultVoiceInput = document.getElementById('settingLumeanDefaultVoiceId');
  const btnToggleEye = document.getElementById('btnToggleApiKeyVisibility');
  const btnToggleTokenEye = document.getElementById('btnToggleTokenVisibility');
  const resultBox = document.getElementById('lumeanTestResultBox');
  const quickStatusText = document.getElementById('lumeanStatusQuickText');

  // Load settings on startup
  fetch('/api/settings')
    .then(res => res.json())
    .then(data => {
      if (data.tts_provider) {
        setTtsEngine(data.tts_provider);
      }
      if (data.lumean_api_key && apiKeyInput) {
        apiKeyInput.value = data.lumean_api_key;
      }
      if (data.lumean_bearer_token && bearerTokenInput) {
        bearerTokenInput.value = data.lumean_bearer_token;
      }
      if (data.lumean_voice_id) {
        if (defaultVoiceInput) defaultVoiceInput.value = data.lumean_voice_id;
        if (lumeanVoiceInput && !lumeanVoiceInput.value) {
          lumeanVoiceInput.value = data.lumean_voice_id;
          if (lumeanDisplay) lumeanDisplay.textContent = `ID: ${data.lumean_voice_id}`;
        }
      }
    })
    .catch(() => {});

  function setTtsEngine(engine) {
    currentTtsProvider = engine;
    engineBtns.forEach(b => {
      b.classList.toggle('active', b.dataset.engine === engine);
    });
    if (engine === 'lumean') {
      if (fishSection) fishSection.classList.add('hidden');
      if (lumeanSection) lumeanSection.classList.remove('hidden');
    } else {
      if (fishSection) fishSection.classList.remove('hidden');
      if (lumeanSection) lumeanSection.classList.add('hidden');
    }
  }

  engineBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      setTtsEngine(btn.dataset.engine);
      // Persist chosen provider
      fetch('/api/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ tts_provider: currentTtsProvider })
      }).catch(() => {});
    });
  });

  if (lumeanVoiceInput) {
    lumeanVoiceInput.addEventListener('input', () => {
      const v = lumeanVoiceInput.value.trim();
      if (lumeanDisplay) lumeanDisplay.textContent = v ? `ID: ${v}` : 'ID: не указан';
    });
  }

  // Eye toggle for API Key & Token
  if (btnToggleEye && apiKeyInput) {
    btnToggleEye.addEventListener('click', () => {
      apiKeyInput.type = apiKeyInput.type === 'password' ? 'text' : 'password';
    });
  }
  if (btnToggleTokenEye && bearerTokenInput) {
    btnToggleTokenEye.addEventListener('click', () => {
      bearerTokenInput.type = bearerTokenInput.type === 'password' ? 'text' : 'password';
    });
  }

  // Test Lumean Connection
  async function testLumean(targetElem, showInResultBox = false) {
    if (targetElem) targetElem.textContent = '⏳ Проверка...';
    try {
      const res = await fetch('/api/lumean/test');
      const data = await res.json();
      if (data.connected) {
        if (quickStatusText) quickStatusText.textContent = `✅ ${data.message}`;
        if (showInResultBox && resultBox) {
          resultBox.classList.remove('hidden');
          resultBox.innerHTML = `<h4>✅ Подключение успешно!</h4><p>${escapeHtml(data.message)}</p>`;
        } else {
          alert(`✅ Lumean API: ${data.message}`);
        }
      } else {
        if (quickStatusText) quickStatusText.textContent = `⚠️ ${data.message}`;
        if (showInResultBox && resultBox) {
          resultBox.classList.remove('hidden');
          resultBox.innerHTML = `<h4>⚠️ Статус подключения:</h4><p>${escapeHtml(data.message)}</p>`;
        } else {
          alert(`⚠️ Lumean API: ${data.message}`);
        }
      }
    } catch (e) {
      if (quickStatusText) quickStatusText.textContent = '✕ Ошибка проверки API';
      alert('Ошибка запроса к серверу: ' + e.message);
    } finally {
      if (targetElem) targetElem.textContent = targetElem.id === 'btnTestLumeanQuick' ? '🔍 Тест' : '🔍 Проверить подключение';
    }
  }

  if (btnTestLumeanQuick) {
    btnTestLumeanQuick.addEventListener('click', () => testLumean(btnTestLumeanQuick, false));
  }
  if (btnCheckLumeanLive) {
    btnCheckLumeanLive.addEventListener('click', () => testLumean(btnCheckLumeanLive, true));
  }

  // Save Settings button
  if (btnSaveSettings) {
    btnSaveSettings.addEventListener('click', async () => {
      const key = apiKeyInput ? apiKeyInput.value.trim() : '';
      const token = bearerTokenInput ? bearerTokenInput.value.trim() : '';
      const defVoice = defaultVoiceInput ? defaultVoiceInput.value.trim() : '';
      btnSaveSettings.textContent = '⏳ Сохранение...';

      try {
        const res = await fetch('/api/settings', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            lumean_api_key: key,
            lumean_bearer_token: token,
            lumean_voice_id: defVoice,
            tts_provider: currentTtsProvider
          })
        });
        if (res.ok) {
          btnSaveSettings.textContent = '✓ Сохранено!';
          if (lumeanVoiceInput && defVoice && !lumeanVoiceInput.value) {
            lumeanVoiceInput.value = defVoice;
            if (lumeanDisplay) lumeanDisplay.textContent = `ID: ${defVoice}`;
          }
          setTimeout(() => btnSaveSettings.textContent = '💾 Сохранить настройки API', 2000);
          testLumean(null, true);
        } else {
          throw new Error('Ошибка сервера при сохранении');
        }
      } catch (e) {
        alert('Не удалось сохранить настройки: ' + e.message);
        btnSaveSettings.textContent = '💾 Сохранить настройки API';
      }
    });
  }
}

function applyVoiceSettings(voice) {
  if (!voice) return;
  const speedSlider = document.getElementById('paramSpeed');
  const valSpeed = document.getElementById('valSpeed');
  const pauseSlider = document.getElementById('paramPause');
  const valPause = document.getElementById('valPause');
  const tempSlider = document.getElementById('paramTemp');
  const valTemp = document.getElementById('valTemp');
  const instructInput = document.getElementById('customInstructInput');

  const speedVal = (voice.speed !== undefined && voice.speed !== null) ? parseFloat(voice.speed) : 1.0;
  const pauseVal = (voice.pause_duration !== undefined && voice.pause_duration !== null) ? parseFloat(voice.pause_duration) : 0.6;
  const tempVal = (voice.temperature !== undefined && voice.temperature !== null) ? parseFloat(voice.temperature) : 0.88;
  const instructVal = (voice.instruct !== undefined && voice.instruct !== null) ? voice.instruct : '';

  if (speedSlider) speedSlider.value = speedVal;
  if (valSpeed) valSpeed.textContent = speedVal;

  if (pauseSlider) pauseSlider.value = pauseVal;
  if (valPause) valPause.textContent = pauseVal;

  if (tempSlider) tempSlider.value = tempVal;
  if (valTemp) valTemp.textContent = tempVal;

  if (instructInput) instructInput.value = instructVal;

  // Sync emotion chips if matching
  const chips = document.querySelectorAll('.emotion-chip');
  chips.forEach(chip => {
    const cTemp = parseFloat(chip.getAttribute('data-temp'));
    const cSpeed = parseFloat(chip.getAttribute('data-speed'));
    if (Math.abs(cTemp - tempVal) < 0.03 && Math.abs(cSpeed - speedVal) < 0.03) {
      chip.classList.add('active');
    } else {
      chip.classList.remove('active');
    }
  });
}

function renderVoicesVaultList() {
  const container = document.getElementById('voicesListContainer');
  if (!container) return;
  container.innerHTML = '';
  voicesData.forEach(v => {
    const card = document.createElement('div');
    card.className = 'voice-card-modern';
    const filename = v.audio_path.split('/').pop();
    card.innerHTML = `
      <div class="voice-card-header">
        <span class="voice-card-name">${v.name === 'default' ? '⭐️ Основной голос (Default)' : `👤 ${v.name}`}</span>
        ${v.name !== 'default' ? `<button class="btn-del" onclick="deleteVoice('${v.name}')">Удалить</button>` : ''}
      </div>
      <div class="voice-settings-strip" style="display:flex; flex-wrap:wrap; gap:8px; margin: 8px 0 10px; font-size:12px; color: var(--text-secondary);">
        <span class="stat-badge">⚡ Скорость: <strong>${v.speed ?? 1.0}x</strong></span>
        <span class="stat-badge">⏸ Пауза: <strong>${v.pause_duration ?? 0.6}с</strong></span>
        <span class="stat-badge">🎭 Темп: <strong>${v.temperature ?? 0.88}</strong></span>
      </div>
      <p class="voice-card-text">«${v.text}»</p>
      <audio controls class="custom-audio-player" src="/api/audio/voice/${filename}"></audio>
    `;
    container.appendChild(card);
  });
}

// --- Voices ---
async function initVoices() {
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
        await loadVoices();
      } catch (err) {
        alert(err.message);
      }
    });
  }

  let referenceAudioInstance = null;
  const btnListenRef = document.getElementById('btnListenRef');
  const btnStopRef = document.getElementById('btnStopRef');
  const voiceSelect = document.getElementById('voiceSelect');
  const btnQuickAdd = document.getElementById('btnQuickAddVoice');

  if (btnQuickAdd) {
    btnQuickAdd.addEventListener('click', () => {
      const voicesTabBtn = document.querySelector('.nav-pill[data-tab="voices"]');
      if (voicesTabBtn) voicesTabBtn.click();
    });
  }

  if (voiceSelect) {
    voiceSelect.addEventListener('change', () => {
      if (referenceAudioInstance) {
        referenceAudioInstance.pause();
        referenceAudioInstance.currentTime = 0;
      }
      const selectedName = voiceSelect.value;
      localStorage.setItem('pdfaudio_selected_voice', selectedName);
      const voice = voicesData.find(v => v.name === selectedName) || voicesData[0];
      if (voice) {
        const nameEl = document.getElementById('activeVoiceName');
        const captionEl = document.getElementById('voiceSampleCaption');
        if (nameEl) nameEl.textContent = voice.name === 'default' ? 'Мой голос (Default)' : voice.name;
        if (captionEl) captionEl.textContent = `«${voice.text}»`;
        applyVoiceSettings(voice);
      }
    });
  }

window.saveCurrentVoiceSettings = async function(event) {
  if (event) {
    try { event.preventDefault(); event.stopPropagation(); } catch (e) {}
  }
  const voiceSelect = document.getElementById('voiceSelect');
  const selectedName = voiceSelect ? voiceSelect.value : 'default';
  const speed = parseFloat(document.getElementById('paramSpeed').value);
  const pause_duration = parseFloat(document.getElementById('paramPause').value);
  const temperature = parseFloat(document.getElementById('paramTemp') ? document.getElementById('paramTemp').value : 0.88);
  const instruct = document.getElementById('customInstructInput') ? document.getElementById('customInstructInput').value.trim() : null;

  const btnSave = document.getElementById('btnSaveVoiceSettings');
  if (btnSave) {
    btnSave.disabled = true;
    btnSave.textContent = '⏳ Сохранение...';
  }

  try {
    const res = await fetch(`/api/voices/${encodeURIComponent(selectedName)}/settings`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ speed, pause_duration, temperature, instruct })
    });
    if (!res.ok) throw new Error('Ошибка сохранения настроек голоса');
    const data = await res.json();
    
    // Update cached voices in memory
    const idx = voicesData.findIndex(v => v.name === selectedName);
    if (idx !== -1 && data.voice) {
      voicesData[idx] = data.voice;
    }

    renderVoicesVaultList();

    if (btnSave) {
      btnSave.textContent = `✓ Настройки для "${selectedName}" сохранены!`;
      setTimeout(() => {
        btnSave.disabled = false;
        btnSave.textContent = '💾 Сохранить для этого голоса';
      }, 2500);
    }
  } catch (e) {
    alert('Ошибка сохранения: ' + e.message);
    if (btnSave) {
      btnSave.disabled = false;
      btnSave.textContent = '💾 Сохранить для этого голоса';
    }
  }
};

  // Also bind event listener if present
  const btnSaveVoiceSettings = document.getElementById('btnSaveVoiceSettings');
  if (btnSaveVoiceSettings) {
    btnSaveVoiceSettings.onclick = window.saveCurrentVoiceSettings;
  }

  if (btnListenRef) {
    btnListenRef.addEventListener('click', () => {
      const selectedName = voiceSelect ? voiceSelect.value : 'default';
      const voice = voicesData.find(v => v.name === selectedName) || voicesData[0];
      if (voice) {
        if (referenceAudioInstance) {
          referenceAudioInstance.pause();
          referenceAudioInstance.currentTime = 0;
        }
        const filename = voice.audio_path.split('/').pop();
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

  await loadVoices();
}

async function loadVoices() {
  try {
    const res = await fetch('/api/voices');
    voicesData = await res.json();

    const select = document.getElementById('voiceSelect');
    const savedVoice = localStorage.getItem('pdfaudio_selected_voice') || 'default';

    if (select) {
      select.innerHTML = '';
      voicesData.forEach(v => {
        const opt = document.createElement('option');
        opt.value = v.name;
        opt.textContent = v.name === 'default' ? '⭐️ Мой голос (Default)' : `👤 ${v.name}`;
        select.appendChild(opt);
      });
      if (voicesData.some(v => v.name === savedVoice)) {
        select.value = savedVoice;
      }
    }

    const currentSelected = select ? select.value : 'default';
    const activeVoice = voicesData.find(v => v.name === currentSelected) || voicesData[0];
    if (activeVoice) {
      const nameEl = document.getElementById('activeVoiceName');
      const captionEl = document.getElementById('voiceSampleCaption');
      if (nameEl) nameEl.textContent = activeVoice.name === 'default' ? 'Мой голос (Default)' : activeVoice.name;
      if (captionEl) captionEl.textContent = `«${activeVoice.text}»`;
      applyVoiceSettings(activeVoice);
    }

    renderVoicesVaultList();
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

let chapterTimers = {};

function cancelAllOperations() {
  isBatchRunning = false;
  // Send global cancellation to backend
  fetch('/api/cancel-all', { method: 'POST' }).catch(() => {});
  if (currentSessionId) {
    fetch(`/api/cancel/${currentSessionId}`, { method: 'POST' }).catch(() => {});
  }
  if (progressInterval) {
    clearInterval(progressInterval);
    progressInterval = null;
  }
  Object.values(chapterTimers).forEach(t => clearInterval(t));
  chapterTimers = {};

  // Reset all generating chapters to idle
  loadedChapters.forEach(chap => {
    if (chap.status === 'generating') {
      chap.status = 'idle';
    }
  });
  renderChaptersList();

  const btnStopGen = document.getElementById('btnStopGeneration');
  if (btnStopGen) btnStopGen.classList.add('hidden');

  const btnStartTTS = document.getElementById('btnStartTTS');
  if (btnStartTTS) {
    btnStartTTS.disabled = false;
    btnStartTTS.textContent = '🚀 Начать озвучку книги';
  }

  const btnSynthesizeAll = document.getElementById('btnSynthesizeAllChapters');
  if (btnSynthesizeAll) {
    btnSynthesizeAll.disabled = false;
    btnSynthesizeAll.textContent = '⚡ Озвучить все главы';
  }

  const statusMsg = document.getElementById('pipelineStatusMessage');
  if (statusMsg) statusMsg.textContent = '⏹️ Озвучка остановлена пользователем';
  updateTimeline(0, 'Остановлено');

  // Reset chunk cards to pending
  renderChunksGrid(activeChunks);
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
  const btnSynthesizeAll = document.getElementById('btnSynthesizeAllChapters');

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
  bindSlider('paramTemp', 'valTemp', '');

  // Emotion presets
  const emotionChips = document.querySelectorAll('.emotion-chip');
  const tempSlider = document.getElementById('paramTemp');
  const valTemp = document.getElementById('valTemp');
  const speedSlider = document.getElementById('paramSpeed');
  const valSpeed = document.getElementById('valSpeed');
  const instructInput = document.getElementById('customInstructInput');

  emotionChips.forEach(chip => {
    chip.addEventListener('click', () => {
      emotionChips.forEach(c => c.classList.remove('active'));
      chip.classList.add('active');

      const temp = chip.getAttribute('data-temp');
      const speed = chip.getAttribute('data-speed');
      const instruct = chip.getAttribute('data-instruct');

      if (tempSlider && temp) {
        tempSlider.value = temp;
        if (valTemp) valTemp.textContent = temp;
      }
      if (speedSlider && speed) {
        speedSlider.value = speed;
        if (valSpeed) valSpeed.textContent = speed;
      }
      if (instructInput && instruct) {
        instructInput.value = instruct;
      }
    });
  });

  // Live text input character counter
  rawTextInput.addEventListener('input', () => {
    statCharCount.textContent = rawTextInput.value.length;
    if (rawTextInput.value.length > 0) {
      updateTimeline(15, `${rawTextInput.value.length} символов`);
    }
  });

  // Output filename live change handler
  const outputNameInput = document.getElementById('outputNameInput');
  if (outputNameInput) {
    outputNameInput.addEventListener('input', () => {
      const val = outputNameInput.value.trim();
      const activeChap = loadedChapters.find(c => c.id === activeChapterId);
      if (activeChap) {
        activeChap.custom_output_name = val;
        if (val) {
          activeChap.title = val;
          const cardTitleInput = document.querySelector(`#chapCard-${activeChap.id} .chapter-title-input`);
          if (cardTitleInput) {
            cardTitleInput.value = val;
          }
        }
      }
    });
  }

  // Clear text button
  if (btnClearText) {
    btnClearText.addEventListener('click', () => {
      cancelAllOperations();
      rawTextInput.value = '';
      statCharCount.textContent = '0';
      loadedChapters = [];
      activeChunks = [];
      renderChaptersList();
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

  // Apply Stress & Split into Chapters Preview
  if (btnApplyStress) {
    btnApplyStress.addEventListener('click', async () => {
      const text = rawTextInput.value.trim();
      if (!text) {
        alert('Сначала загрузите PDF/TXT файл или вставьте текст в поле выше!');
        return;
      }
      try {
        btnApplyStress.disabled = true;
        btnApplyStress.textContent = 'Разбиение на главы и ударения...';
        const res = await fetch('/api/preview', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text, max_chunk_len: 1000 })
        });
        const data = await res.json();
        
        currentBookId = data.book_id || 'custom_book';
        loadedChapters = data.chapters || [];
        renderChaptersList();

        if (loadedChapters.length > 0) {
          showChapterChunks(loadedChapters[0].id);
        }

        updateTimeline(40, `Книга разбита на ${loadedChapters.length} глав`);
        setMilestoneActive('msChunk');
      } catch (e) {
        alert('Ошибка обработки: ' + e.message);
      } finally {
        btnApplyStress.disabled = false;
        btnApplyStress.innerHTML = '<span>🔍 Разобрать текст и расставить ударения</span>';
      }
    });
  }

  // Split by fixed size button (~10 000 chars)
  const btnSplitFixed = document.getElementById('btnSplitFixed');
  if (btnSplitFixed) {
    btnSplitFixed.addEventListener('click', () => {
      const text = rawTextInput.value.trim();
      if (!text) {
        alert('Сначала загрузите или вставьте текст книги!');
        return;
      }
      const paragraphs = text.split('\n\n');
      let parts = [];
      let cur = [];
      let curLen = 0;
      let pIdx = 1;

      paragraphs.forEach(p => {
        cur.push(p);
        curLen += p.length + 2;
        if (curLen >= 10000) {
          const body = cur.join('\n\n').trim();
          parts.push({
            id: `chapter_${pIdx}`,
            index: pIdx,
            title: `${pIdx}. Часть ${pIdx}`,
            text: body,
            char_count: body.length,
            chunks: [],
            status: 'idle',
            audio_url: null
          });
          cur = [];
          curLen = 0;
          pIdx++;
        }
      });

      if (cur.length > 0) {
        const body = cur.join('\n\n').trim();
        parts.push({
          id: `chapter_${pIdx}`,
          index: pIdx,
          title: `${pIdx}. Часть ${pIdx}`,
          text: body,
          char_count: body.length,
          chunks: [],
          status: 'idle',
          audio_url: null
        });
      }

      parts.forEach(part => {
        const sentences = part.text.replace(/\r\n/g, '\n').split(/(?<=[.!?…])\s+/).filter(s => s.trim().length > 0);
        let chs = [];
        let curChunk = '';
        sentences.forEach(s => {
          if (curChunk.length + s.length > 1000 && curChunk.length > 0) {
            chs.push(curChunk);
            curChunk = s;
          } else {
            curChunk = curChunk ? curChunk + ' ' + s : s;
          }
        });
        if (curChunk) chs.push(curChunk);
        part.chunks = chs;
      });

      loadedChapters = parts;
      renderChaptersList();
      if (loadedChapters.length > 0) {
        showChapterChunks(loadedChapters[0].id);
      }
      alert(`Книга нарезана на ${parts.length} частей (по ~10 тыс. символов).`);
    });
  }

  // Stop Generation Button (Square/Pill)
  const btnStopGen = document.getElementById('btnStopGeneration');
  if (btnStopGen) {
    btnStopGen.addEventListener('click', () => {
      cancelAllOperations();
    });
  }

  // Synthesize ALL Chapters Sequentially
  if (btnSynthesizeAll) {
    btnSynthesizeAll.addEventListener('click', async () => {
      if (loadedChapters.length === 0) {
        alert('Нет загруженных глав для озвучки!');
        return;
      }
      if (isBatchRunning) {
        alert('Пакетная озвучка уже выполняется...');
        return;
      }
      await runBatchAllChapters();
    });
  }

  // Start TTS for active selected chapter / text
  if (btnStartTTS) {
    btnStartTTS.addEventListener('click', async () => {
      if (activeChapterId) {
        await synthesizeSingleChapter(activeChapterId);
      } else if (loadedChapters.length > 0) {
        await synthesizeSingleChapter(loadedChapters[0].id);
      } else {
        const rawText = rawTextInput.value.trim();
        if (!rawText) {
          alert('Нет текста для озвучки! Вставьте текст или загрузите файл.');
          return;
        }
        await synthesizeRawText(rawText);
      }
    });
  }
}

let currentBookId = 'default_book';
let selectedChapterIds = new Set();

function toggleChapterSelection(chapId, isChecked) {
  if (isChecked) {
    selectedChapterIds.add(chapId);
  } else {
    selectedChapterIds.delete(chapId);
  }
  updateSelectionUI();
}

function toggleSelectAllChapters(isChecked) {
  if (isChecked) {
    loadedChapters.forEach(c => selectedChapterIds.add(c.id));
  } else {
    selectedChapterIds.clear();
  }
  renderChaptersList();
}

function selectUnvoicedChapters() {
  selectedChapterIds.clear();
  loadedChapters.forEach(c => {
    if (c.status !== 'done') {
      selectedChapterIds.add(c.id);
    }
  });
  renderChaptersList();
}

function deselectAllChapters() {
  selectedChapterIds.clear();
  renderChaptersList();
}

function updateSelectionUI() {
  const count = selectedChapterIds.size;
  const badge = document.getElementById('selectedCountBadge');
  const btnSynthSelected = document.getElementById('btnSynthesizeSelectedChapters');
  const chkAll = document.getElementById('chkSelectAllChapters');

  if (badge) badge.textContent = count;
  if (btnSynthSelected) {
    btnSynthSelected.style.display = count > 0 ? 'inline-flex' : 'none';
    btnSynthSelected.textContent = `✨ Озвучить выбранные (${count})`;
  }
  if (chkAll) {
    chkAll.checked = loadedChapters.length > 0 && count === loadedChapters.length;
    chkAll.indeterminate = count > 0 && count < loadedChapters.length;
  }

  // Update visual selected-chapter class on cards
  loadedChapters.forEach(c => {
    const card = document.getElementById(`chapCard-${c.id}`);
    const chk = document.querySelector(`.chapter-select-checkbox[data-id="${c.id}"]`);
    if (card) {
      if (selectedChapterIds.has(c.id)) {
        card.classList.add('selected-chapter');
      } else {
        card.classList.remove('selected-chapter');
      }
    }
    if (chk) {
      chk.checked = selectedChapterIds.has(c.id);
    }
  });
}

function renderChaptersList() {
  const container = document.getElementById('chaptersList');
  const doneBadge = document.getElementById('chaptersDoneBadge');
  const totalBadge = document.getElementById('chaptersTotalBadge');
  const percentBadge = document.getElementById('chaptersPercentBadge');
  const progressFill = document.getElementById('bookProgressFill');
  const btnSynthesizeAll = document.getElementById('btnSynthesizeAllChapters');

  if (!container) return;

  const totalCount = loadedChapters.length;
  const doneCount = loadedChapters.filter(c => c.status === 'done').length;
  const percent = totalCount > 0 ? Math.round((doneCount / totalCount) * 100) : 0;

  if (doneBadge) doneBadge.textContent = doneCount;
  if (totalBadge) totalBadge.textContent = totalCount;
  if (percentBadge) percentBadge.textContent = `${percent}%`;
  if (progressFill) progressFill.style.width = `${percent}%`;

  if (btnSynthesizeAll) {
    const remaining = totalCount - doneCount;
    if (remaining === 0 && totalCount > 0) {
      btnSynthesizeAll.textContent = '✓ Все главы озвучены';
    } else {
      btnSynthesizeAll.textContent = remaining < totalCount ? `⚡ Озвучить оставшиеся главы (${remaining})` : '⚡ Озвучить все главы';
    }
  }

  if (loadedChapters.length === 0) {
    container.innerHTML = `
      <div class="empty-chapters-placeholder">
        <div class="placeholder-icon">📚</div>
        <h4>Главы книги еще не загружены</h4>
        <p>Загрузите PDF или текстовый файл книги, и она автоматически разделится по главам с сохранением лога озвучки.</p>
      </div>
    `;
    updateSelectionUI();
    return;
  }

  container.innerHTML = '';
  loadedChapters.forEach((chap, idx) => {
    const isCurrentActive = chap.id === activeChapterId;
    const isDone = chap.status === 'done';
    const isSelected = selectedChapterIds.has(chap.id);
    const card = document.createElement('div');
    card.className = `chapter-card-item ${isCurrentActive ? 'active-chapter' : ''} ${isSelected ? 'selected-chapter' : ''} ${chap.status}`;
    card.id = `chapCard-${chap.id}`;

    let statusBadge = 'Ожидание';
    if (chap.status === 'generating') statusBadge = 'Синтез...';
    if (chap.status === 'done') statusBadge = 'Готово ✓';
    if (chap.status === 'error') statusBadge = 'Ошибка ✕';

    const estMinutes = Math.max(1, Math.ceil(chap.char_count / 850));

    card.innerHTML = `
      <div class="chapter-item-top">
        <div class="chapter-title-group">
          <input type="checkbox" class="chapter-select-checkbox" data-id="${chap.id}" ${isSelected ? 'checked' : ''}
                 onchange="toggleChapterSelection('${chap.id}', this.checked)" title="Выбрать главу для выборочной озвучки">
          <span class="chapter-icon">${isDone ? '✅' : '📖'}</span>
          <input type="text" class="chapter-title-input" value="${escapeHtml(chap.title)}" 
                 onchange="updateChapterTitle('${chap.id}', this.value)" title="Нажмите, чтобы переименовать главу">
        </div>
        <div class="chapter-meta-group">
          <span class="stat-badge">${chap.char_count} симв. (~${estMinutes} мин)</span>
          <span class="chunk-status-chip ${chap.status}" id="chapStatusChip-${chap.id}">${statusBadge}</span>
        </div>
      </div>

      <div class="chapter-actions-row">
        <div class="chapter-left-actions">
          <button class="btn-synthesize-chap" onclick="synthesizeSingleChapter('${chap.id}')" id="btnSynthChap-${chap.id}">
            ${isDone ? '🔄 Переозвучить' : '▶️ Озвучить эту главу'}
          </button>
          <button class="btn-sm-text" onclick="showChapterChunks('${chap.id}')">
            👁️ Показать чанки (${chap.chunks.length})
          </button>
        </div>
        <button class="btn-del" onclick="deleteChapter('${chap.id}')" title="Удалить главу из очереди">
          🗑️ Удалить главу
        </button>
      </div>

      ${chap.audio_url ? `
        <div class="chapter-audio-box" style="margin-top: 6px;">
          <audio controls class="custom-audio-player" src="${chap.audio_url}"></audio>
          <a href="${chap.audio_url}" download="${escapeHtml(chap.title)}.${selectedFormat}" class="btn-sm-text" style="display:inline-block; margin-top:4px;">⬇️ Скачать аудио главы</a>
        </div>
      ` : ''}
    `;
    container.appendChild(card);
  });

  updateSelectionUI();
}

function updateChapterTitle(chapId, newTitle) {
  const chap = loadedChapters.find(c => c.id === chapId);
  if (chap && newTitle.trim()) {
    chap.title = newTitle.trim();
    chap.custom_output_name = newTitle.trim();
    if (activeChapterId === chapId) {
      const nameInput = document.getElementById('outputNameInput');
      if (nameInput) nameInput.value = chap.title;
    }
  }
}

function deleteChapter(chapId) {
  const chap = loadedChapters.find(c => c.id === chapId);
  const name = chap ? chap.title : 'эту главу';
  if (!confirm(`Удалить "${name}"?`)) return;

  loadedChapters = loadedChapters.filter(c => c.id !== chapId);
  if (activeChapterId === chapId) {
    activeChapterId = loadedChapters.length > 0 ? loadedChapters[0].id : null;
    if (activeChapterId) {
      showChapterChunks(activeChapterId);
    } else {
      activeChunks = [];
      renderChunksGrid([]);
    }
  }
  renderChaptersList();
}

function showChapterChunks(chapId) {
  activeChapterId = chapId;
  const chap = loadedChapters.find(c => c.id === chapId);
  const nameInput = document.getElementById('outputNameInput');
  if (chap) {
    activeChunks = chap.chunks;
    renderChunksGrid(activeChunks);
    if (nameInput) {
      nameInput.value = chap.custom_output_name || chap.title;
    }
  }
  // Re-highlight active card
  document.querySelectorAll('.chapter-card-item').forEach(c => c.classList.remove('active-chapter'));
  const activeCard = document.getElementById(`chapCard-${chapId}`);
  if (activeCard) activeCard.classList.add('active-chapter');
}

async function synthesizeSingleChapter(chapId) {
  const chap = loadedChapters.find(c => c.id === chapId);
  if (!chap) return;

  // Clear any existing active session timers
  if (chapterTimers[chapId]) {
    clearInterval(chapterTimers[chapId]);
    delete chapterTimers[chapId];
  }

  // If user changed input, capture it immediately
  const nameInput = document.getElementById('outputNameInput');
  let currentOutputName = (nameInput && nameInput.value.trim()) ? nameInput.value.trim() : (chap.custom_output_name || chap.title);

  if (activeChapterId === chapId) {
    chap.custom_output_name = currentOutputName;
    chap.title = currentOutputName;
  }

  showChapterChunks(chapId);

  // If this chapter has custom name, ensure it is in the input
  if (chap.custom_output_name && nameInput) {
    nameInput.value = chap.custom_output_name;
    currentOutputName = chap.custom_output_name;
  }

  // Update card UI
  chap.status = 'generating';
  renderChaptersList();

  const payload = {
    chunks: chap.chunks,
    book_id: currentBookId,
    chapter_id: chap.id,
    chapter_title: currentOutputName,
    voice_name: document.getElementById('voiceSelect') ? document.getElementById('voiceSelect').value : 'default',
    output_name: currentOutputName,
    output_format: selectedFormat,
    pause_duration: parseFloat(document.getElementById('paramPause').value),
    speed: parseFloat(document.getElementById('paramSpeed').value),
    temperature: parseFloat(document.getElementById('paramTemp') ? document.getElementById('paramTemp').value : 0.88),
    instruct: document.getElementById('customInstructInput') ? document.getElementById('customInstructInput').value.trim() : null,
    apply_loudnorm: true,
    ...getTtsProviderPayload()
  };

  try {
    const res = await fetch('/api/generate', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    if (!res.ok) throw new Error('Ошибка запуска генерации главы');
    const data = await res.json();
    currentSessionId = data.session_id;

    // Track generation and set audio_url when done
    trackChapterProgress(chapId, data.session_id);
  } catch (e) {
    chap.status = 'error';
    renderChaptersList();
    alert('Ошибка генерации главы: ' + e.message);
  }
}

function trackChapterProgress(chapId, sessionId) {
  const chap = loadedChapters.find(c => c.id === chapId);
  startProgressPolling();

  if (chapterTimers[chapId]) clearInterval(chapterTimers[chapId]);

  const checkInterval = setInterval(async () => {
    try {
      const res = await fetch(`/api/progress/${sessionId}`);
      if (!res.ok) return;
      const data = await res.json();

      if (data.status === 'completed') {
        clearInterval(checkInterval);
        delete chapterTimers[chapId];
        if (chap) {
          chap.status = 'done';
          chap.audio_url = data.output_url;
          renderChaptersList();

          // Persist progress to server
          fetch('/api/projects/record-chapter', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              book_id: currentBookId,
              chapter_id: chap.id,
              chapter_title: chap.title,
              audio_url: data.output_url
            })
          }).catch(() => {});
        }
      } else if (data.status === 'cancelled') {
        clearInterval(checkInterval);
        delete chapterTimers[chapId];
        if (chap) {
          chap.status = 'idle';
          renderChaptersList();
        }
      } else if (data.status === 'error') {
        clearInterval(checkInterval);
        delete chapterTimers[chapId];
        if (chap) {
          chap.status = 'error';
          renderChaptersList();
        }
      }
    } catch (e) {}
  }, 1200);

  chapterTimers[chapId] = checkInterval;
}

async function runBatchAllChapters() {
  const uncompleted = loadedChapters.filter(c => c.status !== 'done');
  if (uncompleted.length === 0) {
    alert('Все главы этой книги уже успешно озвучены!');
    return;
  }

  isBatchRunning = true;
  const btnSynthesizeAll = document.getElementById('btnSynthesizeAllChapters');
  if (btnSynthesizeAll) {
    btnSynthesizeAll.disabled = true;
    btnSynthesizeAll.textContent = '⏳ Озвучка книги...';
  }

  for (let i = 0; i < loadedChapters.length; i++) {
    if (!isBatchRunning) break;
    const chap = loadedChapters[i];
    if (chap.status === 'done') continue; // Skip already finished chapters!

    await new Promise((resolve) => {
      showChapterChunks(chap.id);
      chap.status = 'generating';
      renderChaptersList();

      const outputName = chap.custom_output_name || chap.title.replace(/[^\w\sа-яА-ЯёЁ.-]/gi, '_');
      const payload = {
        chunks: chap.chunks,
        book_id: currentBookId,
        chapter_id: chap.id,
        chapter_title: chap.title,
        voice_name: document.getElementById('voiceSelect') ? document.getElementById('voiceSelect').value : 'default',
        output_name: outputName,
        output_format: selectedFormat,
        pause_duration: parseFloat(document.getElementById('paramPause').value),
        speed: parseFloat(document.getElementById('paramSpeed').value),
        temperature: parseFloat(document.getElementById('paramTemp') ? document.getElementById('paramTemp').value : 0.88),
        instruct: document.getElementById('customInstructInput') ? document.getElementById('customInstructInput').value.trim() : null,
        apply_loudnorm: true,
        ...getTtsProviderPayload()
      };

      fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      .then(res => res.json())
      .then(data => {
        currentSessionId = data.session_id;
        startProgressPolling();

        const timer = setInterval(async () => {
          if (!isBatchRunning) {
            clearInterval(timer);
            resolve();
            return;
          }
          try {
            const pRes = await fetch(`/api/progress/${data.session_id}`);
            const pData = await pRes.json();
            if (pData.status === 'completed') {
              clearInterval(timer);
              chap.status = 'done';
              chap.audio_url = pData.output_url;
              renderChaptersList();

              fetch('/api/projects/record-chapter', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  book_id: currentBookId,
                  chapter_id: chap.id,
                  chapter_title: chap.title,
                  audio_url: pData.output_url
                })
              }).catch(() => {});

              resolve();
            } else if (pData.status === 'cancelled') {
              clearInterval(timer);
              chap.status = 'idle';
              renderChaptersList();
              resolve();
            } else if (pData.status === 'error') {
              clearInterval(timer);
              chap.status = 'error';
              renderChaptersList();
              resolve();
            }
          } catch (e) {
            clearInterval(timer);
            resolve();
          }
        }, 1200);
      })
      .catch(e => {
        chap.status = 'error';
        renderChaptersList();
        resolve();
      });
    });
  }

  isBatchRunning = false;
  if (btnSynthesizeAll) {
    btnSynthesizeAll.disabled = false;
    renderChaptersList();
  }
}

async function synthesizeSelectedChapters() {
  const targetChapters = loadedChapters.filter(c => selectedChapterIds.has(c.id));
  if (targetChapters.length === 0) {
    alert('Выберите хотя бы одну главу галочкой!');
    return;
  }

  isBatchRunning = true;
  const btnStop = document.getElementById('btnStopGeneration');
  if (btnStop) btnStop.classList.remove('hidden');

  const btnSynthSelected = document.getElementById('btnSynthesizeSelectedChapters');
  if (btnSynthSelected) {
    btnSynthSelected.disabled = true;
    btnSynthSelected.textContent = `⏳ Озвучка (${targetChapters.length} глав)...`;
  }

  for (let i = 0; i < targetChapters.length; i++) {
    if (!isBatchRunning) break;
    const chap = targetChapters[i];

    await new Promise((resolve) => {
      showChapterChunks(chap.id);
      chap.status = 'generating';
      renderChaptersList();

      const outputName = chap.custom_output_name || chap.title.replace(/[^\w\sа-яА-ЯёЁ.-]/gi, '_');
      const payload = {
        chunks: chap.chunks,
        book_id: currentBookId,
        chapter_id: chap.id,
        chapter_title: chap.title,
        voice_name: document.getElementById('voiceSelect') ? document.getElementById('voiceSelect').value : 'default',
        output_name: outputName,
        output_format: selectedFormat,
        pause_duration: parseFloat(document.getElementById('paramPause').value),
        speed: parseFloat(document.getElementById('paramSpeed').value),
        temperature: parseFloat(document.getElementById('paramTemp') ? document.getElementById('paramTemp').value : 0.88),
        instruct: document.getElementById('customInstructInput') ? document.getElementById('customInstructInput').value.trim() : null,
        apply_loudnorm: true,
        ...getTtsProviderPayload()
      };

      fetch('/api/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      })
      .then(res => res.json())
      .then(data => {
        currentSessionId = data.session_id;
        startProgressPolling();

        const timer = setInterval(async () => {
          if (!isBatchRunning) {
            clearInterval(timer);
            resolve();
            return;
          }
          try {
            const pRes = await fetch(`/api/progress/${data.session_id}`);
            const pData = await pRes.json();
            if (pData.status === 'completed') {
              clearInterval(timer);
              chap.status = 'done';
              chap.audio_url = pData.output_url;
              selectedChapterIds.delete(chap.id); // Finished chapter is unselected
              renderChaptersList();

              fetch('/api/projects/record-chapter', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                  book_id: currentBookId,
                  chapter_id: chap.id,
                  chapter_title: chap.title,
                  audio_url: pData.output_url
                })
              }).catch(() => {});

              resolve();
            } else if (pData.status === 'cancelled') {
              clearInterval(timer);
              chap.status = 'idle';
              renderChaptersList();
              resolve();
            } else if (pData.status === 'error') {
              clearInterval(timer);
              chap.status = 'error';
              renderChaptersList();
              resolve();
            }
          } catch (e) {
            clearInterval(timer);
            resolve();
          }
        }, 1200);
      })
      .catch(e => {
        chap.status = 'error';
        renderChaptersList();
        resolve();
      });
    });
  }

  isBatchRunning = false;
  if (btnSynthSelected) {
    btnSynthSelected.disabled = false;
    updateSelectionUI();
  }
  if (btnStop) btnStop.classList.add('hidden');
}

async function synthesizeRawText(rawText) {
  const payload = {
    text: rawText,
    voice_name: document.getElementById('voiceSelect') ? document.getElementById('voiceSelect').value : 'default',
    output_name: document.getElementById('outputNameInput').value.trim() || null,
    output_format: selectedFormat,
    pause_duration: parseFloat(document.getElementById('paramPause').value),
    speed: parseFloat(document.getElementById('paramSpeed').value),
    temperature: parseFloat(document.getElementById('paramTemp') ? document.getElementById('paramTemp').value : 0.88),
    instruct: document.getElementById('customInstructInput') ? document.getElementById('customInstructInput').value.trim() : null,
    apply_loudnorm: true,
    ...getTtsProviderPayload()
  };

  try {
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
  titleEl.textContent = `Чтение и разбивка: ${file.name}...`;

  try {
    const res = await fetch('/api/extract', { method: 'POST', body: formData });
    if (!res.ok) throw new Error('Ошибка чтения файла');
    const data = await res.json();

    document.getElementById('rawTextInput').value = data.raw_text;
    document.getElementById('statCharCount').textContent = data.total_chars;
    document.getElementById('outputNameInput').value = file.name.replace(/\.[^/.]+$/, "");

    currentBookId = data.book_id || file.name.replace(/\.[^/.]+$/, "");
    loadedChapters = data.chapters || [];
    renderChaptersList();

    if (loadedChapters.length > 0) {
      showChapterChunks(loadedChapters[0].id);
    }

    titleEl.textContent = `✓ Загружена книга: ${file.name}`;
    subEl.textContent = `${data.total_chars} символов, ${data.total_chapters} глав`;

    updateTimeline(30, `Книга разбита на ${data.total_chapters} глав`);
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
        <p>Выберите главу выше или нажмите кнопку <strong>«Разобрать текст и расставить ударения»</strong>.</p>
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
  const btnStopGen = document.getElementById('btnStopGeneration');

  if (btnStopGen) btnStopGen.classList.remove('hidden');

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
        if (btnStopGen) btnStopGen.classList.add('hidden');
        if (btnStartTTS) {
          btnStartTTS.disabled = false;
          btnStartTTS.textContent = '🚀 Начать озвучку книги';
        }
        updateTimeline(100, 'Склейка завершена!');
        setMilestoneActive('msReady');
        if (statusMsg) statusMsg.textContent = 'Готово! Аудиофайл успешно создан.';

        if (data.output_url) {
          finalBox.classList.remove('hidden');
          mainPlayer.src = data.output_url;
          btnDownload.href = data.output_url;
          finalFilename.textContent = data.output_url.split('/').pop();
        }
      } else if (data.status === 'cancelled') {
        clearInterval(progressInterval);
        if (btnStopGen) btnStopGen.classList.add('hidden');
        if (btnStartTTS) {
          btnStartTTS.disabled = false;
          btnStartTTS.textContent = '🚀 Начать озвучку книги';
        }
        if (statusMsg) statusMsg.textContent = '⏹️ Озвучка остановлена пользователем.';
      } else if (data.status === 'error') {
        clearInterval(progressInterval);
        if (btnStopGen) btnStopGen.classList.add('hidden');
        if (btnStartTTS) {
          btnStartTTS.disabled = false;
          btnStartTTS.textContent = '🚀 Начать озвучку книги';
        }
        if (statusMsg) statusMsg.textContent = 'Ошибка генерации: ' + data.error;
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
