/* [9단계] 분석 화면: 작업 등록(POST) → 작업 ID로 상태 주기 조회 → 완료 시 결과 표시 */
(() => {
  const app = document.getElementById("app");
  const API = app.dataset.api;
  const CAPTURE_SEC = parseFloat(app.dataset.captureSeconds || "8");
  const POLL_MS = 2000;
  const UNCERTAIN_LABEL = "판단 불확실";
  const STATUS_KO = { PENDING: "대기", PROCESSING: "처리 중", COMPLETED: "완료", FAILED: "실패" };
  const INPUT_KO = { UPLOAD: "영상 업로드", CAMERA: "IP Webcam" };

  const $ = (s, el = document) => el.querySelector(s);
  const $$ = (s, el = document) => [...el.querySelectorAll(s)];
  const csrf = () => $("[name=csrfmiddlewaretoken]")?.value || "";
  const esc = (v) => String(v ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtTime = (iso) => (iso ? new Date(iso).toLocaleString("ko-KR", { hour12: false }) : "-");

  let mode = "UPLOAD";
  let pollTimer = null;
  let countdownTimer = null;

  /* ---------- 탭 · 카메라 미리보기 ---------- */
  function setMode(m) {
    mode = m;
    $$(".tab").forEach((t) => t.classList.toggle("active", t.dataset.mode === m));
    $$(".pane").forEach((p) => p.classList.toggle("hidden", p.dataset.pane !== m));
    m === "CAMERA" ? startPreview() : stopPreview();
  }
  function startPreview() {
    const name = $("#camera_name")?.value;
    const img = $("#preview"), msg = $("#preview-msg");
    if (!name || !img) return;
    msg.textContent = "미리보기 불러오는 중…";
    msg.classList.remove("hidden");
    img.onload = () => msg.classList.add("hidden");
    img.onerror = () => { msg.textContent = "카메라에 연결할 수 없습니다. 휴대폰 앱의 서버 실행·Wi-Fi를 확인하세요."; msg.classList.remove("hidden"); };
    img.src = `/api/v1/cameras/${encodeURIComponent(name)}/stream/?t=${Date.now()}`;
  }
  function stopPreview() {
    const img = $("#preview");
    if (img) { img.removeAttribute("src"); }   // src 제거 → 서버·카메라 연결 종료
  }
  $$(".tab").forEach((t) => t.addEventListener("click", () => !t.disabled && setMode(t.dataset.mode)));
  $("#camera_name")?.addEventListener("change", startPreview);
  window.addEventListener("beforeunload", stopPreview);

  /* ---------- 작업 등록 ---------- */
  $("#analysis-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const err = $("#form-error");
    err.classList.add("hidden");
    const fd = new FormData();
    fd.append("input_type", mode);
    ["title", "memo", "expected_action"].forEach((k) => fd.append(k, $("#" + k).value.trim()));
    if (mode === "UPLOAD") {
      const f = $("#video").files[0];
      if (!f) return showFormError("영상 파일을 선택하세요.");
      fd.append("video", f);
    } else {
      fd.append("camera_name", $("#camera_name").value);
    }

    const btn = $("#start-btn");
    btn.disabled = true; btn.textContent = "등록 중…";
    try {
      const r = await fetch(API, { method: "POST", body: fd, headers: { "X-CSRFToken": csrf() }, credentials: "same-origin" });
      const data = await r.json().catch(() => ({}));
      if (!r.ok) return showFormError(flattenErrors(data) || `요청 실패 (HTTP ${r.status})`);
      $("#analysis-form").reset();
      watchJob(data.id, data.input_type);          // 작업 ID를 즉시 받고 상태 조회 시작
      loadHistory();
    } catch (ex) {
      showFormError("서버에 연결할 수 없습니다.");
    } finally {
      btn.disabled = false; btn.textContent = "AI 분석 시작";
    }
  });
  function showFormError(msg) { const el = $("#form-error"); el.textContent = msg; el.classList.remove("hidden"); }
  function flattenErrors(d) {
    if (typeof d !== "object" || !d) return "";
    return Object.entries(d).map(([k, v]) => `${k === "non_field_errors" || k === "detail" ? "" : k + ": "}${[].concat(v).join(" ")}`).join(" / ");
  }

  /* ---------- 상태 조회 (polling) ---------- */
  function watchJob(id, inputType) {
    clearInterval(pollTimer); clearInterval(countdownTimer);
    $("#job-label").textContent = `#${id}`;
    $("#result").innerHTML = "";
    let seenProcessingAt = null;
    const tick = async () => {
      try {
        const r = await fetch(`${API}${id}/status/`, { credentials: "same-origin" });
        if (!r.ok) { setStatus("FAILED", `상태 조회 실패 (HTTP ${r.status})`); return clearInterval(pollTimer); }
        const s = await r.json();
        if (s.status === "PROCESSING" && inputType === "CAMERA" && !seenProcessingAt) {
          seenProcessingAt = Date.now();
          startCountdown();
        }
        if (s.done) {
          clearInterval(pollTimer); clearInterval(countdownTimer); hideOverlay();
          loadDetail(id); loadHistory();
        } else if (!(inputType === "CAMERA" && s.status === "PROCESSING")) {
          setStatus(s.status, s.status === "PENDING" ? "작업 대기 중 — Worker가 곧 처리합니다." : "AI 분석 중… (영상 길이에 따라 수십 초)");
        }
      } catch { /* 일시적 네트워크 오류는 다음 주기에 재시도 */ }
    };
    setStatus("PENDING", "작업 등록 완료 — 대기 중");
    tick();
    pollTimer = setInterval(tick, POLL_MS);
  }
  function startCountdown() {
    let left = Math.ceil(CAPTURE_SEC);
    const show = () => {
      if (left > 0) { setStatus("PROCESSING", `영상 수집 중… ${left}초 — 카메라 앞에서 동작하세요`); showOverlay(`● REC ${left}`); }
      else { setStatus("PROCESSING", "AI 분석 중… (Pose·Feature·Random Forest)"); hideOverlay(); clearInterval(countdownTimer); }
      left -= 1;
    };
    show();
    countdownTimer = setInterval(show, 1000);
  }
  function showOverlay(t) { const o = $("#capture-overlay"); if (o) { o.textContent = t; o.classList.remove("hidden"); } }
  function hideOverlay() { $("#capture-overlay")?.classList.add("hidden"); }

  function setStatus(status, text) {
    const order = { PENDING: 0, PROCESSING: 1, COMPLETED: 2, FAILED: 2 };
    $$("#steps li").forEach((li, i) => {
      li.className = i < order[status] ? "done" : i === order[status] ? (status === "FAILED" ? "fail" : status === "COMPLETED" ? "done" : "now") : "";
    });
    $("#status-text").textContent = text;
  }

  /* ---------- 결과 표시 ---------- */
  async function loadDetail(id) {
    const r = await fetch(`${API}${id}/`, { credentials: "same-origin" });
    if (!r.ok) return setStatus("FAILED", `결과를 불러오지 못했습니다 (HTTP ${r.status})`);
    renderJob(await r.json());
  }
  function renderJob(j) {
    $("#job-label").textContent = `#${j.id}`;
    if (j.status === "FAILED") setStatus("FAILED", `실패 — ${j.error_message || "알 수 없는 오류"}`);
    else if (j.status === "COMPLETED") setStatus("COMPLETED", j.result_message || "완료");
    else { setStatus(j.status, STATUS_KO[j.status]); if (!pollTimer) watchJob(j.id, j.input_type); }

    const meta = `
      <dl class="meta">
        <dt>입력</dt><dd>${esc(INPUT_KO[j.input_type])}${j.camera_name ? " · " + esc(j.camera_name) : ""}</dd>
        <dt>수행하려던 동작</dt><dd>${esc(j.expected_action) || "-"}</dd>
        <dt>처리 시간</dt><dd>${j.processing_sec != null ? j.processing_sec + "초" : "-"}</dd>
        <dt>모델</dt><dd>${esc(j.model_version) || "-"}</dd>
      </dl>`;
    let table = "";
    if (j.status === "COMPLETED") {
      table = j.predictions.length ? `
        <table class="table">
          <thead><tr><th>Track</th><th>예측 동작</th><th>신뢰도</th><th>유효 Frame</th></tr></thead>
          <tbody>${j.predictions.map((p) => `
            <tr>
              <td>${p.track_id}</td>
              <td>${esc(p.action_label)} ${p.uncertain ? `<span class="badge warn">${UNCERTAIN_LABEL}</span>` : ""}
                  ${j.expected_action ? (j.expected_action === p.action_label ? '<span class="badge ok">예상과 일치</span>' : '<span class="badge">예상과 다름</span>') : ""}</td>
              <td><div class="bar"><span style="width:${(p.confidence * 100).toFixed(0)}%"></span></div>${(p.confidence * 100).toFixed(1)}%</td>
              <td>${p.valid_frames}</td>
            </tr>`).join("")}</tbody>
        </table>
        <p class="help">신뢰도는 모델의 확신 정도이며 정답 여부가 아닙니다. 학습하지 않은 동작도 3개 중 하나로 예측될 수 있습니다.</p>`
        : `<p class="muted">예측 결과가 없습니다.</p>`;
    }
    const video = j.video ? `
      <video src="${esc(j.video)}" controls preload="metadata" class="video"></video>
      <p class="help">재생되지 않으면 <a href="${esc(j.video)}" download>영상 내려받기</a></p>` : "";
    $("#result").innerHTML = meta + table + video;
  }

  /* ---------- 최근 이력 ---------- */
  async function loadHistory() {
    const tb = $("#history");
    try {
      const r = await fetch(API, { credentials: "same-origin" });
      const jobs = (await r.json()).slice(0, 10);
      tb.innerHTML = jobs.length ? jobs.map((j) => `
        <tr class="clickable" data-id="${j.id}">
          <td>${j.id}</td><td>${esc(j.title) || "-"}</td><td>${esc(INPUT_KO[j.input_type])}</td>
          <td><span class="status s-${j.status}">${STATUS_KO[j.status]}</span></td>
          <td>${j.predictions.map((p) => esc(p.action_label)).join(", ") || "-"}</td>
          <td>${j.processing_sec != null ? j.processing_sec + "s" : "-"}</td>
          <td>${fmtTime(j.created_at)}</td>
        </tr>`).join("") : `<tr><td colspan="7" class="muted">아직 분석 기록이 없습니다.</td></tr>`;
      $$("#history tr.clickable").forEach((tr) => tr.addEventListener("click", () => { clearInterval(pollTimer); pollTimer = null; loadDetail(tr.dataset.id); }));
    } catch { tb.innerHTML = `<tr><td colspan="7" class="error">이력을 불러오지 못했습니다.</td></tr>`; }
  }
  $("#refresh").addEventListener("click", loadHistory);

  loadHistory();
})();
