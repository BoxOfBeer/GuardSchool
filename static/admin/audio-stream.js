/**
 * Панель «Звук ПК» / стрим ffmpeg, тесты из настроек программы.
 * selectedScreenSlug передаётся из app.js через setAudioStreamDeps.
 */
import { state, elements } from "./state.js";
import { t, tf } from "./i18n-helpers.js";
import { api, mergeFetchOptions, apiDetailMessage } from "./api-client.js";
import { escapeHtmlAttr } from "./escape-html.js";

let selectedScreenSlug = () => "tv-1";

/** @param {{ selectedScreenSlug: () => string }} d */
export function setAudioStreamDeps(d) {
  if (d && typeof d.selectedScreenSlug === "function") {
    selectedScreenSlug = d.selectedScreenSlug;
  }
}

export function ensureAudioStreamConfig() {
  const d = {
    enabled: false,
    receiver_ip: "",
    stream_port: 11990,
    ping_host: "",
    multicast_ip: "224.0.224.1",
    multicast_ttl: 10,
    base_port: 11990,
    ffmpeg_path: "",
    interface_note: "",
    use_bell_schedule: true,
    use_bell_sound_files: true,
    volume_percent: 80,
    source_screen_id: "",
    send_via_multicast: false,
    udp_bind_localaddr: false,
    stream_profile: "mpegts_aac",
    break_music_on_breaks: false,
    break_music_volume_percent: 40,
    bell_trigger_sec_window: 25,
  };
  state.config.audio_stream = { ...d, ...(state.config.audio_stream || {}) };
  const s = state.config.audio_stream;
  if (!s.receiver_ip && s.ping_host) s.receiver_ip = s.ping_host;
  if (!s.ping_host && s.receiver_ip) s.ping_host = s.receiver_ip;
  if (s.stream_port == null && s.base_port != null) s.stream_port = s.base_port;
}

export function refreshBellSoundsForStream() {
  api("/api/admin/bell-sounds")
    .then((r) => {
      state.bellSoundFiles = r.files || [];
    })
    .catch(() => {});
}

export async function refreshPcPlayerFiles() {
  let breaks = [];
  try {
    const r = await api("/api/admin/break-music-files");
    breaks = (r.files || []).map((x) => x && x.filename).filter(Boolean);
  } catch (_) {
    breaks = [];
  }
  const out = [];
  breaks.forEach((fn) => {
    const name = String(fn != null ? fn : "").trim();
    if (!name) return;
    out.push({ filename: name, label: name });
  });
  state.pcPlayerFiles = out;
  if (state.pcPlayerSelectedIndex >= out.length) state.pcPlayerSelectedIndex = 0;
  renderPcPlayerFileList();
}

export function selectedPcPlayerItem() {
  return state.pcPlayerFiles && state.pcPlayerFiles.length
    ? state.pcPlayerFiles[Math.max(0, Math.min(state.pcPlayerFiles.length - 1, state.pcPlayerSelectedIndex))]
    : null;
}

export function renderPcPlayerFileList() {
  const el = elements.pcPlayerFileList;
  if (!el) return;
  const items = state.pcPlayerFiles || [];
  if (!items.length) {
    el.innerHTML = `<div class="hint">${t("audio.noBreakFiles")}</div>`;
    return;
  }
  el.innerHTML = "";
  items.forEach((item, idx) => {
    const b = document.createElement("button");
    b.type = "button";
    b.className = `pc-player-file-item ${idx === state.pcPlayerSelectedIndex ? "active" : ""}`;
    b.innerHTML = `<span class="pc-player-file-badge break">${escapeHtmlAttr(t("audio.badgeBreak"))}</span><span class="pc-player-file-name">${escapeHtmlAttr(item.label)}</span>`;
    b.onclick = () => {
      state.pcPlayerSelectedIndex = idx;
      renderPcPlayerFileList();
    };
    el.appendChild(b);
  });
}

export async function pcPlayerPlaySelected() {
  const item = selectedPcPlayerItem();
  if (!item) return;
  readAudioStreamFormIntoState();
  const breakVol = Number(elements.audioStreamBreakMusicVol && elements.audioStreamBreakMusicVol.value);
  const volBreak = Number.isFinite(breakVol) ? Math.max(0, Math.min(100, breakVol)) : 40;
  if (elements.audioStreamStatusBar) elements.audioStreamStatusBar.textContent = t("audio.statusStarting");

  try {
    const fn = String(item.filename != null ? item.filename : "").trim();
    if (!fn) {
      if (elements.audioStreamStatusBar) elements.audioStreamStatusBar.textContent = t("audio.noFileName");
      return;
    }
    await api("/api/admin/break-music-preview", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: fn, volume_percent: volBreak }),
    });
    updateStreamStatusBar();
  } catch (e) {
    if (elements.audioStreamStatusBar) elements.audioStreamStatusBar.textContent = String(e.message || e);
  }
}

export function pcPlayerStep(delta) {
  const n = state.pcPlayerFiles ? state.pcPlayerFiles.length : 0;
  if (!n) return;
  state.pcPlayerSelectedIndex = (state.pcPlayerSelectedIndex + delta + n) % n;
  renderPcPlayerFileList();
}

export function breakMusicVolumesFromForm() {
  const rawB = elements.audioStreamVolume && elements.audioStreamVolume.value;
  const rawBr = elements.audioStreamBreakMusicVol && elements.audioStreamBreakMusicVol.value;
  const bell =
    rawB !== undefined && rawB !== "" && Number.isFinite(Number(rawB))
      ? Math.max(0, Math.min(100, Number(rawB)))
      : null;
  const br =
    rawBr !== undefined && rawBr !== "" && Number.isFinite(Number(rawBr))
      ? Math.max(0, Math.min(100, Number(rawBr)))
      : null;
  return { bell, br };
}

/** Порядок очереди с сервера + громкость из полей формы (или с сервера). */
export async function renderBreakMusicPlayback() {
  const el = elements.breakMusicPlayerList;
  if (!el) return;
  try {
    const r = await api("/api/admin/break-music-files");
    const pb = r.playback;
    if (!pb) {
      el.innerHTML = `<p class="hint">${t("audio.queueEmpty")}</p>`;
      return;
    }
    const vf = breakMusicVolumesFromForm();
    const bellPct = vf.bell ?? pb.volume_bell_percent;
    const breakPct = vf.br ?? pb.volume_break_percent;
    const volLine = `<div class="break-music-vol-line"><strong>Громкость:</strong> звонки <strong>${bellPct}%</strong> · перемена <strong>${breakPct}%</strong> (ffmpeg <code>volume=${(breakPct / 100).toFixed(3)}</code> для фона)</div><p class="hint break-music-save-hint">Чтобы на ПК применились новые %, нажмите «Сохранить» вверху.</p>`;

    const kindLine =
      pb.play_kind && pb.play_kind !== "idle"
        ? `<p class="hint break-music-kind">Сейчас в плеере ПК: <code>${escapeHtmlAttr(String(pb.play_kind))}</code></p>`
        : "";

    const modeBlock = `<p class="break-music-mode"><strong>${escapeHtmlAttr(pb.mode_label || "")}</strong></p><p class="hint break-music-note">${escapeHtmlAttr(pb.order_note || "")}</p>`;

    const orows = pb.ordered_rows || [];
    const rows =
      orows.length > 0
        ? orows
            .map(
              (row) =>
                `<div class="break-music-row ${row.is_next ? "break-music-row-next" : ""}"><span class="break-music-idx">${row.i}.</span><span class="break-music-name">${escapeHtmlAttr(row.filename)}</span>${row.is_next ? '<span class="break-music-badge">следующий</span>' : ""}</div>`,
            )
            .join("")
        : '<p class="hint">Нет строк очереди.</p>';

    el.innerHTML = `${volLine}${kindLine}${modeBlock}<div class="break-music-order">${rows}</div>`;
  } catch (_) {
    el.innerHTML = `<p class="hint">${t("audio.queueLoadFail")}</p>`;
  }
}

export function updateStreamStatusBar() {
  const el = elements.audioStreamStatusBar;
  if (!el) return;
  api("/api/admin/audio-stream-status")
    .then((st) => {
      const last = st.last;
      const be = last && last.backend ? String(last.backend) : "";
      const run = st.ffmpeg_process_running
        ? `воспроизведение: да${be ? ` (${be})` : ""}`
        : "воспроизведение: нет";
      const pid = st.pid != null ? ` (PID ${st.pid})` : "";
      const kind = st.play_kind && st.play_kind !== "idle" ? `\nРежим: ${st.play_kind}` : "";
      const busy = st.stream_slot_busy ? "Занято" : "Свободно";
      let tail = "";
      if (last) {
        if (last.finished === false) tail += "\nВоспроизведение…";
        if (last.returncode != null) tail += `\nКод выхода: ${last.returncode}`;
        if (last.ok === false && last.stderr) tail += `\n${String(last.stderr).slice(0, 400)}`;
      }
      let diag = "";
      if (st.volume_bell_percent != null && st.volume_break_percent != null) {
        diag += `\nГромкость (настройки): звонки ${st.volume_bell_percent}% | перемена ${st.volume_break_percent}%`;
      }
      if (st.pc_playback_backend_hint) {
        diag += `\nПК: бэкенд ${st.pc_playback_backend_hint}`;
      }
      if (st.resolved_ffmpeg) diag += `\nffmpeg: ${st.resolved_ffmpeg}`;
      if (!st.resolved_ffmpeg && st.resolved_ffplay) diag += `\nffplay: ${st.resolved_ffplay}`;
      if (
        st.pc_audio_enabled &&
        !st.resolved_ffmpeg &&
        !st.resolved_ffplay
      ) {
        diag +=
          "\n⚠ Не найден ffmpeg/ffplay — звук с этого ПК не сыграет. Установите ffmpeg (Linux: `sudo apt install ffmpeg`) или укажите путь к ffmpeg/ffplay.";
      }
      el.textContent = `${run}${pid} (${busy})${kind}${tail}${diag}`;
      if (state.audioStreamPanelActive) {
        renderBreakMusicPlayback();
      }
    })
    .catch((err) => {
      el.textContent = tf("audio.statusUnavailable", { msg: String(err.message || err) });
    });
}

export function populateAudioStreamSourceScreenSelect() {
  const sel = elements.audioStreamSourceScreen;
  if (!sel || !state.config?.screens?.length) return;
  const cur = (state.config.audio_stream && state.config.audio_stream.source_screen_id) || "";
  sel.innerHTML = "";
  const first = document.createElement("option");
  first.value = "";
  first.textContent = t("audio.firstScreenOption");
  sel.appendChild(first);
  state.config.screens.forEach((sc) => {
    const o = document.createElement("option");
    o.value = String(sc.id);
    o.textContent = sc.name || sc.slug || sc.id;
    sel.appendChild(o);
  });
  const exists = [...sel.options].some((opt) => opt.value === cur);
  sel.value = exists ? cur : "";
}

export function syncAudioStreamFormFromState() {
  ensureAudioStreamConfig();
  populateAudioStreamSourceScreenSelect();
  const s = state.config.audio_stream;
  if (elements.audioStreamEnabled) elements.audioStreamEnabled.checked = !!s.enabled;
  if (elements.audioStreamFfmpegPath) elements.audioStreamFfmpegPath.value = s.ffmpeg_path || "";
  if (elements.audioStreamUseBellSchedule) elements.audioStreamUseBellSchedule.checked = s.use_bell_schedule !== false;
  if (elements.audioStreamUseBellFiles) elements.audioStreamUseBellFiles.checked = s.use_bell_sound_files !== false;
  if (elements.audioStreamVolume) elements.audioStreamVolume.value = String(s.volume_percent ?? 80);
  if (elements.audioStreamBreakMusic) elements.audioStreamBreakMusic.checked = !!s.break_music_on_breaks;
  if (elements.audioStreamBreakMusicVol) elements.audioStreamBreakMusicVol.value = String(s.break_music_volume_percent ?? 40);
  if (elements.audioStreamBellWindow) elements.audioStreamBellWindow.value = String(s.bell_trigger_sec_window ?? 25);
}

export function readAudioStreamFormIntoState() {
  ensureAudioStreamConfig();
  const s = state.config.audio_stream;
  s.enabled = !!(elements.audioStreamEnabled && elements.audioStreamEnabled.checked);
  s.ffmpeg_path = (elements.audioStreamFfmpegPath && elements.audioStreamFfmpegPath.value.trim()) || "";
  s.use_bell_schedule = !!(elements.audioStreamUseBellSchedule && elements.audioStreamUseBellSchedule.checked);
  s.use_bell_sound_files = !!(elements.audioStreamUseBellFiles && elements.audioStreamUseBellFiles.checked);
  s.volume_percent = Math.max(0, Math.min(100, Number(elements.audioStreamVolume && elements.audioStreamVolume.value) || s.volume_percent));
  s.source_screen_id = (elements.audioStreamSourceScreen && elements.audioStreamSourceScreen.value) || "";
  s.break_music_on_breaks = !!(elements.audioStreamBreakMusic && elements.audioStreamBreakMusic.checked);
  s.break_music_volume_percent = Math.max(0, Math.min(100, Number(elements.audioStreamBreakMusicVol && elements.audioStreamBreakMusicVol.value) || s.break_music_volume_percent));
  s.bell_trigger_sec_window = Math.max(5, Math.min(55, Number(elements.audioStreamBellWindow && elements.audioStreamBellWindow.value) || s.bell_trigger_sec_window));
}

let audioStreamFormWired = false;
export function bindAudioStreamFormOnce() {
  if (audioStreamFormWired) return;
  audioStreamFormWired = true;
  const onChange = () => readAudioStreamFormIntoState();
  [
    elements.audioStreamEnabled,
    elements.audioStreamFfmpegPath,
    elements.audioStreamUseBellSchedule,
    elements.audioStreamUseBellFiles,
    elements.audioStreamVolume,
    elements.audioStreamSourceScreen,
    elements.audioStreamBreakMusic,
    elements.audioStreamBreakMusicVol,
    elements.audioStreamBellWindow,
  ].forEach((el) => {
    if (!el) return;
    el.addEventListener(el.type === "checkbox" || el.tagName === "SELECT" ? "change" : "input", onChange);
  });
  [elements.audioStreamVolume, elements.audioStreamBreakMusicVol].forEach((el) => {
    if (!el) return;
    el.addEventListener("input", () => {
      if (state.audioStreamPanelActive) renderBreakMusicPlayback();
    });
  });
  if (elements.audioStreamStopBtn) {
    elements.audioStreamStopBtn.addEventListener("click", async () => {
      if (elements.audioStreamStatusBar) elements.audioStreamStatusBar.textContent = t("audio.statusStopping");
      try {
        await api("/api/admin/audio-stream-stop", { method: "POST" });
        updateStreamStatusBar();
      } catch (err) {
        if (elements.audioStreamStatusBar) elements.audioStreamStatusBar.textContent = String(err.message || err);
      }
    });
  }
}

let pcPlayerWired = false;
export function bindPcPlayerOnce() {
  if (pcPlayerWired) return;
  pcPlayerWired = true;
  if (elements.pcPlayerPrev) elements.pcPlayerPrev.addEventListener("click", () => pcPlayerStep(-1));
  if (elements.pcPlayerNext) elements.pcPlayerNext.addEventListener("click", () => pcPlayerStep(1));
  if (elements.pcPlayerPlay) elements.pcPlayerPlay.addEventListener("click", () => pcPlayerPlaySelected());
  if (elements.audioStreamBreakMusicVol) {
    const sync = () => {
      if (elements.pcPlayerVolDisplay) elements.pcPlayerVolDisplay.textContent = String(elements.audioStreamBreakMusicVol.value || "");
    };
    elements.audioStreamBreakMusicVol.addEventListener("input", sync);
    sync();
  }
}

let settingsSoundTestsWired = false;

function pollFfplayIntoPre(base, preEl) {
  const pollFfmpeg = async () => {
    for (let i = 0; i < 40; i += 1) {
      await new Promise((resolve) => setTimeout(resolve, 1500));
      try {
        const st = await api("/api/admin/audio-stream-last-send");
        const last = st.last;
        if (!last || !last.finished) continue;
        const rc = last.returncode;
        const err = last.stderr || "";
        const tail = `\n\n--- вывод (код ${rc === null || rc === undefined ? "?" : rc}) ---\n${err || "(пустой stderr)"}`;
        if (preEl) preEl.textContent = base + tail;
        return;
      } catch (_) {
        /* сеть */
      }
    }
    if (preEl) {
      preEl.textContent = `${base}\n\n${t("audio.statusTimeout")}`;
    }
  };
  pollFfmpeg();
}

export function bindSettingsSoundTestsOnce() {
  if (settingsSoundTestsWired) return;
  settingsSoundTestsWired = true;
  const out = () => elements.settingsSoundTestResult;

  if (elements.settingsTestRuporBtn) {
    elements.settingsTestRuporBtn.addEventListener("click", async () => {
      readAudioStreamFormIntoState();
      if (out()) out().textContent = t("audio.playbackStarting");
      const testUrl = "/api/admin/pc-audio-test-play?use_first=1";
      try {
        const response = await fetch(
          testUrl,
          mergeFetchOptions({
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ volume_percent: Number(elements.audioStreamVolume && elements.audioStreamVolume.value) || 80 }),
          }),
        );
        const payload = await response.json().catch(() => ({}));
        if (!response.ok) {
          if (response.status === 401) {
            window.location.href = "/login";
            return;
          }
          if (response.status === 404) {
            if (out()) {
              out().textContent =
                "Сервер не знает этот API (404) — запущен старый процесс GuardSchool.\n\n"
                + "Закройте все окна/службы, остановите python/uvicorn, запустите снова из папки с текущим проектом (где есть маршрут pc-audio-test-play в app.py).";
            }
            return;
          }
          throw new Error(apiDetailMessage(payload) || `Ошибка ${response.status}`);
        }
        const r = payload;
        const base = r.detail || "Готово.";
        if (out()) out().textContent = `${base}\n\n${t("audio.waitingFinish")}`;
        pollFfplayIntoPre(base, elements.settingsSoundTestResult);
      } catch (err) {
        if (out()) out().textContent = String(err.message || err);
      }
    });
  }

  if (elements.settingsTestTvBtn) {
    elements.settingsTestTvBtn.addEventListener("click", async () => {
      try {
        const r = await api("/api/admin/bell-sounds");
        const files = r.files || [];
        if (!files.length) {
          if (out()) {
            out().textContent =
              "В uploads/bells нет файлов. Загрузите звук в разделе «Звонки».";
          }
          return;
        }
        const slug = selectedScreenSlug();
        const screenUrl = `${window.location.origin}/screen/${encodeURIComponent(slug)}`;
        const w = window.open(screenUrl, "_blank", "noopener,noreferrer");
        let msg =
          `Тест ТВ: откройте экран «${slug}» — звук по расписанию идёт там. В админке файл не играет (Рупор только «Тест Рупор»).\n${screenUrl}`;
        if (!w) msg += "\n\nВкладка не открылась — разрешите всплывающие окна или скопируйте URL выше.";
        if (out()) out().textContent = msg;
      } catch (err) {
        if (out()) out().textContent = String(err.message || err);
      }
    });
  }
}
