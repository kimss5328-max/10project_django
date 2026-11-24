/* [10단계] Django가 ORM으로 집계해 넘겨준 데이터(json_script)로 Chart.js 차트 2개 */
(() => {
  const data = JSON.parse(document.getElementById("chart-data").textContent);
  if (typeof Chart === "undefined") {
    document.querySelectorAll(".chart-box").forEach((b) => (b.innerHTML = '<p class="muted">Chart.js를 불러오지 못했습니다(인터넷 연결 확인).</p>'));
    return;
  }
  Chart.defaults.font.family = 'system-ui, "Noto Sans KR", sans-serif';

  // 1) 동작별 예측 건수 — 막대
  new Chart(document.getElementById("actionChart"), {
    type: "bar",
    data: { labels: data.actions.labels, datasets: [{ label: "예측 건수", data: data.actions.counts, backgroundColor: "#2563eb", borderRadius: 4 }] },
    options: {
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: { y: { beginAtZero: true, ticks: { precision: 0 } } },
    },
  });

  // 2) 작업 상태별 건수 — 원형(도넛)
  const COLOR = { PENDING: "#9ca3af", PROCESSING: "#f59e0b", COMPLETED: "#16a34a", FAILED: "#dc2626" };
  new Chart(document.getElementById("statusChart"), {
    type: "doughnut",
    data: {
      labels: data.statuses.labels.map((l, i) => `${l} (${data.statuses.counts[i]})`),
      datasets: [{ data: data.statuses.counts, backgroundColor: data.statuses.keys.map((k) => COLOR[k]) }],
    },
    options: { maintainAspectRatio: false, plugins: { legend: { position: "right" } } },
  });
})();
