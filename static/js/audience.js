/**
 * InstaFlow Audience Controller (Seguidores/Seguidos + Ley de Benford)
 * =====================================================================
 * Orquesta la extracción de audiencia, el sondeo del trabajo en segundo
 * plano, la tabla de resultados con tarjeta flotante al pasar el mouse,
 * y el dashboard de la Ley de Benford (curva teórica vs. observada).
 */

document.addEventListener("DOMContentLoaded", () => {
  const state = {
    currentJobId: null,
    pollingInterval: null,
    isScraping: false,
    lastUsers: [],
  };

  const el = {
    inputUsername: document.getElementById("audience-input-username"),
    selectLimit: document.getElementById("audience-select-limit"),
    chkDownloadImages: document.getElementById("audience-chk-download-images"),
    btnStart: document.getElementById("audience-btn-start"),
    btnCancel: document.getElementById("audience-btn-cancel"),
    progressBar: document.getElementById("audience-progress-bar"),
    stagesContainer: document.getElementById("audience-stages-container"),
    logsConsole: document.getElementById("audience-logs-console"),

    benfordSection: document.getElementById("audience-benford-section"),
    classificationBadge: document.getElementById("audience-classification-badge"),
    canvas: document.getElementById("audience-benford-canvas"),
    statSample: document.getElementById("audience-stat-sample"),
    statChi2: document.getElementById("audience-stat-chi2"),
    statDf: document.getElementById("audience-stat-df"),
    statThresholds: document.getElementById("audience-stat-thresholds"),
    verdictMessage: document.getElementById("audience-verdict-message"),

    tableSection: document.getElementById("audience-table-section"),
    tableCount: document.getElementById("audience-table-count"),
    tableBody: document.getElementById("audience-table-body"),
    emptyState: document.getElementById("audience-empty-state"),

    hoverCard: document.getElementById("audience-hover-card"),
    hoverAvatar: document.getElementById("audience-hover-avatar"),
    hoverUsername: document.getElementById("audience-hover-username"),
    hoverVerified: document.getElementById("audience-hover-verified"),
    hoverPosts: document.getElementById("audience-hover-posts"),
    hoverFollowers: document.getElementById("audience-hover-followers"),
    hoverFollowing: document.getElementById("audience-hover-following"),
  };

  setupEventListeners();

  function setupEventListeners() {
    el.btnStart.addEventListener("click", handleStart);
    el.inputUsername.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleStart();
      }
    });
    el.btnCancel.addEventListener("click", handleCancel);
  }

  // ==========================================================================
  // FLUJO PRINCIPAL
  // ==========================================================================
  async function handleStart() {
    const rawUsername = el.inputUsername.value.trim();
    if (!rawUsername) {
      alert("Por favor, introduzca un nombre de usuario de Instagram válido.");
      el.inputUsername.focus();
      return;
    }

    const limit = parseInt(el.selectLimit.value, 10) || 200;
    const downloadImages = el.chkDownloadImages.checked;

    setScrapingState(true);
    resetViews();

    try {
      addLog("info", `Solicitando análisis de audiencia para @${rawUsername} (límite: ${limit})...`);
      const res = await fetch("/api/audience/scrape", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          username: rawUsername,
          limit: limit,
          download_images: downloadImages,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        throw new Error(data.error || `Error HTTP ${res.status}`);
      }

      state.currentJobId = data.job_id;
      addLog("success", `Trabajo aceptado [ID: ${data.job_id.substring(0, 8)}]. Modo: ${data.mode === "followers" ? "Seguidores" : "Seguidos"}.`);
      startPolling(data.job_id);
    } catch (err) {
      addLog("error", `Fallo al iniciar el análisis: ${err.message}`);
      alert(`Error al iniciar el análisis: ${err.message}`);
      setScrapingState(false);
    }
  }

  async function handleCancel() {
    if (!state.currentJobId) return;
    el.btnCancel.disabled = true;
    el.btnCancel.textContent = "Cancelando...";
    try {
      await fetch(`/api/jobs/${encodeURIComponent(state.currentJobId)}/cancel`, { method: "POST" });
      addLog("warning", "Solicitud de cancelación enviada al servidor.");
    } catch (err) {
      addLog("error", `Error al solicitar cancelación: ${err.message}`);
    }
  }

  function startPolling(jobId) {
    if (state.pollingInterval) clearInterval(state.pollingInterval);
    state.pollingInterval = setInterval(async () => {
      try {
        const res = await fetch(`/api/jobs/${encodeURIComponent(jobId)}`);
        const job = await res.json();
        if (!res.ok) throw new Error(job.error || `Error HTTP ${res.status}`);

        updateProgressUI(job);

        if (["completed", "partial", "failed", "cancelled"].includes(job.status)) {
          stopPolling();
          setScrapingState(false);
          finalizeUI(job);
        }
      } catch (err) {
        console.error("Error en sondeo de audiencia:", err);
      }
    }, 1200);
  }

  function stopPolling() {
    if (state.pollingInterval) {
      clearInterval(state.pollingInterval);
      state.pollingInterval = null;
    }
  }

  function setScrapingState(isScraping) {
    state.isScraping = isScraping;
    el.btnStart.disabled = isScraping;
    el.inputUsername.disabled = isScraping;
    el.selectLimit.disabled = isScraping;

    if (isScraping) {
      el.btnStart.innerHTML = `<span class="spinner"></span> Analizando...`;
      el.btnCancel.style.display = "inline-flex";
      el.btnCancel.disabled = false;
      el.btnCancel.textContent = "Cancelar ejecución";
    } else {
      el.btnStart.innerHTML = `<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> Analizar audiencia`;
      el.btnCancel.style.display = "none";
    }
  }

  // ==========================================================================
  // ETAPAS Y REGISTRO
  // ==========================================================================
  function updateProgressUI(job) {
    const pct = Math.min(100, Math.max(0, job.progress_percent || 0));
    el.progressBar.style.width = `${pct}%`;
    if (job.stages && job.stages.length) renderStages(job.stages);
    if (job.logs && job.logs.length) renderLogs(job.logs);
  }

  function renderStages(stages) {
    el.stagesContainer.innerHTML = stages
      .map((st) => {
        const statusClass = st.status || "running";
        let icon = `<span class="status-dot warning pulse"></span>`;
        if (statusClass === "success") icon = `<span style="color:var(--accent-green)">✓</span>`;
        else if (statusClass === "warning") icon = `<span style="color:var(--accent-amber)">⚠</span>`;
        else if (statusClass === "error") icon = `<span style="color:var(--accent-red)">✕</span>`;
        const duration = st.duration_sec ? ` (${st.duration_sec}s)` : "";
        return `
          <div class="stage-item ${statusClass}">
            <div class="stage-left">
              <span class="stage-number">${st.stage_number}</span>
              <div>
                <div class="stage-name">${escapeHtml(st.name)}</div>
                <div class="stage-message">${escapeHtml(st.message || "")}${duration}</div>
              </div>
            </div>
            <div class="stage-right">${icon}</div>
          </div>`;
      })
      .join("");
    el.stagesContainer.scrollTop = el.stagesContainer.scrollHeight;
  }

  function renderLogs(logs) {
    el.logsConsole.innerHTML = logs
      .map((l) => `
        <div class="log-entry">
          <span class="log-time">[${l.timestamp}]</span>
          <span class="log-msg ${l.level}">${escapeHtml(l.message)}</span>
        </div>`)
      .join("");
    el.logsConsole.scrollTop = el.logsConsole.scrollHeight;
  }

  function addLog(level, message) {
    const timeStr = new Date().toTimeString().split(" ")[0];
    const div = document.createElement("div");
    div.className = "log-entry";
    div.innerHTML = `<span class="log-time">[${timeStr}]</span><span class="log-msg ${level}">${escapeHtml(message)}</span>`;
    el.logsConsole.appendChild(div);
    el.logsConsole.scrollTop = el.logsConsole.scrollHeight;
  }

  // ==========================================================================
  // FINALIZACIÓN: TABLA + BENFORD
  // ==========================================================================
  function finalizeUI(job) {
    el.progressBar.style.width = "100%";

    const users = job.audience_users || [];
    state.lastUsers = users;

    if (users.length > 0) {
      el.emptyState.style.display = "none";
      el.tableSection.style.display = "block";
      renderTable(users);
    }

    if (job.benford) {
      el.benfordSection.style.display = "block";
      renderBenford(job.benford);
    } else if (job.status === "failed" && job.error_message) {
      addLog("error", job.error_message);
      alert(`No se pudo aplicar la Ley de Benford:\n\n${job.error_message}`);
    }
  }

  function renderTable(users) {
    el.tableCount.textContent = `${users.length} perfiles`;
    el.tableBody.innerHTML = users
      .map((u, idx) => {
        const avatarSrc = u.profile_image_path
          ? `/${u.profile_image_path}`
          : (u.profile_image_url || "/static/img/placeholder.svg");
        return `
          <tr>
            <td><img class="audience-row-avatar" src="${escapeAttr(avatarSrc)}" alt="" onerror="this.src='/static/img/placeholder.svg';"></td>
            <td>
              <span class="audience-username-trigger" data-idx="${idx}">@${escapeHtml(u.username)}</span>
              ${u.is_verified ? '<span class="audience-badge-verified-inline">✔</span>' : ""}
            </td>
            <td>${u.full_name ? escapeHtml(u.full_name) : '<span class="audience-unknown">No disponible</span>'}</td>
            <td>${formatNumberCell(u.followers_count)}</td>
            <td>${formatNumberCell(u.following_count)}</td>
            <td>${formatNumberCell(u.posts_count)}</td>
            <td>${u.is_private === true ? "Sí" : (u.is_private === false ? "No" : '<span class="audience-unknown">—</span>')}</td>
          </tr>`;
      })
      .join("");

    el.tableBody.querySelectorAll(".audience-username-trigger").forEach((trigger) => {
      trigger.addEventListener("mouseenter", (e) => showHoverCard(e, users[parseInt(trigger.dataset.idx, 10)]));
      trigger.addEventListener("mousemove", positionHoverCard);
      trigger.addEventListener("mouseleave", hideHoverCard);
    });
  }

  function formatNumberCell(val) {
    if (val === null || val === undefined) return '<span class="audience-unknown">No disponible</span>';
    return Number(val).toLocaleString();
  }

  // --- Tarjeta flotante estilo Instagram al pasar el mouse ---
  function showHoverCard(evt, user) {
    if (!user) return;
    const avatarSrc = user.profile_image_path
      ? `/${user.profile_image_path}`
      : (user.profile_image_url || "/static/img/placeholder.svg");
    el.hoverAvatar.src = avatarSrc;
    el.hoverUsername.textContent = `@${user.username}`;
    el.hoverVerified.style.display = user.is_verified ? "inline-flex" : "none";
    el.hoverPosts.textContent = user.posts_count !== null && user.posts_count !== undefined ? Number(user.posts_count).toLocaleString() : "—";
    el.hoverFollowers.textContent = user.followers_count !== null && user.followers_count !== undefined ? Number(user.followers_count).toLocaleString() : "—";
    el.hoverFollowing.textContent = user.following_count !== null && user.following_count !== undefined ? Number(user.following_count).toLocaleString() : "—";
    el.hoverCard.classList.add("visible");
    positionHoverCard(evt);
  }

  function positionHoverCard(evt) {
    const margin = 14;
    const cardWidth = el.hoverCard.offsetWidth || 230;
    const cardHeight = el.hoverCard.offsetHeight || 190;
    let x = evt.clientX + margin;
    let y = evt.clientY + margin;
    if (x + cardWidth > window.innerWidth) x = evt.clientX - cardWidth - margin;
    if (y + cardHeight > window.innerHeight) y = evt.clientY - cardHeight - margin;
    el.hoverCard.style.left = `${Math.max(8, x)}px`;
    el.hoverCard.style.top = `${Math.max(8, y)}px`;
  }

  function hideHoverCard() {
    el.hoverCard.classList.remove("visible");
  }

  // --- Dashboard de la Ley de Benford ---
  function renderBenford(benford) {
    el.statSample.textContent = benford.sample_size;
    el.statChi2.textContent = benford.chi_square !== null ? benford.chi_square : "—";
    el.statDf.textContent = benford.degrees_of_freedom;
    el.statThresholds.textContent = `Bot > ${benford.bot_threshold} · Posible Bot > ${benford.possible_bot_threshold}`;
    el.verdictMessage.textContent = benford.verdict_message || "";

    el.classificationBadge.textContent = benford.classification_label;
    el.classificationBadge.className = `audience-classification-badge ${benford.classification}`;

    drawBenfordChart(el.canvas, benford.digits, benford.expected_proportions, benford.observed_proportions);
  }

  function drawBenfordChart(canvas, digits, theoretical, observed) {
    const ctx = canvas.getContext("2d");
    const W = canvas.width;
    const H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const paddingLeft = 46;
    const paddingRight = 20;
    const paddingTop = 20;
    const paddingBottom = 36;
    const chartW = W - paddingLeft - paddingRight;
    const chartH = H - paddingTop - paddingBottom;

    const maxVal = Math.max(0.05, ...theoretical, ...observed) * 1.15;
    const n = digits.length;
    const slotW = chartW / n;

    // Ejes
    ctx.strokeStyle = "#23273c";
    ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(paddingLeft, paddingTop);
    ctx.lineTo(paddingLeft, paddingTop + chartH);
    ctx.lineTo(paddingLeft + chartW, paddingTop + chartH);
    ctx.stroke();

    // Líneas de referencia horizontales + etiquetas de eje Y
    ctx.fillStyle = "#5E6682";
    ctx.font = "11px sans-serif";
    ctx.textAlign = "right";
    const ySteps = 4;
    for (let i = 0; i <= ySteps; i++) {
      const val = (maxVal / ySteps) * i;
      const y = paddingTop + chartH - (val / maxVal) * chartH;
      ctx.strokeStyle = "rgba(255,255,255,0.05)";
      ctx.beginPath();
      ctx.moveTo(paddingLeft, y);
      ctx.lineTo(paddingLeft + chartW, y);
      ctx.stroke();
      ctx.fillText(`${(val * 100).toFixed(0)}%`, paddingLeft - 8, y + 3);
    }

    // Barras: distribución observada
    ctx.fillStyle = "rgba(137, 54, 255, 0.55)";
    for (let i = 0; i < n; i++) {
      const barH = (observed[i] / maxVal) * chartH;
      const x = paddingLeft + i * slotW + slotW * 0.22;
      const barW = slotW * 0.56;
      ctx.fillRect(x, paddingTop + chartH - barH, barW, barH);
    }

    // Porcentaje observado sobre cada barra
    ctx.fillStyle = "#C9B6FF";
    ctx.font = "10px sans-serif";
    ctx.textAlign = "center";
    for (let i = 0; i < n; i++) {
      if (!observed[i]) continue;
      const x = paddingLeft + i * slotW + slotW / 2;
      const y = paddingTop + chartH - (observed[i] / maxVal) * chartH - 6;
      ctx.fillText(`${(observed[i] * 100).toFixed(1)}%`, x, y);
    }

    // Curva teórica de Benford (línea + puntos)
    ctx.strokeStyle = "#FFB020";
    ctx.lineWidth = 2.5;
    ctx.beginPath();
    for (let i = 0; i < n; i++) {
      const x = paddingLeft + i * slotW + slotW / 2;
      const y = paddingTop + chartH - (theoretical[i] / maxVal) * chartH;
      if (i === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();

    ctx.fillStyle = "#FFB020";
    for (let i = 0; i < n; i++) {
      const x = paddingLeft + i * slotW + slotW / 2;
      const y = paddingTop + chartH - (theoretical[i] / maxVal) * chartH;
      ctx.beginPath();
      ctx.arc(x, y, 3.5, 0, Math.PI * 2);
      ctx.fill();
    }

    // Etiquetas del eje X (dígitos 1-9)
    ctx.fillStyle = "#9BA3BF";
    ctx.font = "12px sans-serif";
    ctx.textAlign = "center";
    for (let i = 0; i < n; i++) {
      const x = paddingLeft + i * slotW + slotW / 2;
      ctx.fillText(String(digits[i]), x, paddingTop + chartH + 20);
    }
  }

  function resetViews() {
    el.stagesContainer.innerHTML = "";
    el.logsConsole.innerHTML = "";
    el.progressBar.style.width = "0%";
    el.benfordSection.style.display = "none";
    el.tableSection.style.display = "none";
    el.emptyState.style.display = "block";
    el.tableBody.innerHTML = "";
  }

  function escapeHtml(str) {
    if (!str) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function escapeAttr(str) {
    return escapeHtml(str).replace(/`/g, "&#096;");
  }
});
