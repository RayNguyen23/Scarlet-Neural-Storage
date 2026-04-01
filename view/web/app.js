const LOG_TAIL = 5;
let pollTimer = null;
let jobRunning = false;

function escapeHtml(s) {
  const d = document.createElement("div");
  d.textContent = s;
  return d.innerHTML;
}

function showBanner(msg) {
  const b = document.getElementById("bannerError");
  if (!msg) {
    b.hidden = true;
    b.textContent = "";
    return;
  }
  b.textContent = msg;
  b.hidden = false;
}

function setPoll(on) {
  if (on) {
    if (pollTimer) return;
    pollTimer = setInterval(tick, 220);
    tick();
  } else {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }
}

async function tick() {
  try {
    const s = await eel.get_state()();
    applyState(s);
    if (!s.running && jobRunning) {
      jobRunning = false;
      setPoll(false);
    }
  } catch (e) {
    console.error(e);
  }
}

function badgeForWorkflow(wf) {
  const el = document.getElementById("workflowBadge");
  el.className = "badge";
  const map = {
    idle: ["badge-idle", "Idle"],
    encoding: ["badge-run", "Encoding"],
    encoded: ["badge-ready", "Session ready"],
    summoning: ["badge-run", "Summoning"],
    restored: ["badge-done", "Restored"],
    failed: ["badge-fail", "Failed"],
  };
  const [cls, text] = map[wf] || map.idle;
  el.classList.add(cls);
  el.textContent = text;
}

function stepperClasses(wf) {
  const s1 = document.getElementById("step1");
  const s2 = document.getElementById("step2");
  s1.className = "step";
  s2.className = "step";

  const step1Done = ["encoded", "summoning", "restored"].includes(wf);

  if (wf === "encoding") {
    s1.classList.add("step-active");
    s2.classList.add("step-pending");
  } else if (wf === "summoning") {
    s1.classList.add("step-done");
    s2.classList.add("step-active");
  } else if (wf === "encoded") {
    s1.classList.add("step-done");
    s2.classList.add("step-next");
  } else if (wf === "restored") {
    s1.classList.add("step-done");
    s2.classList.add("step-done");
  } else if (wf === "failed") {
    s1.classList.add("step-active");
    s2.classList.add("step-pending");
  } else {
    s2.classList.add("step-pending");
  }

  if (step1Done && wf !== "encoding") s1.classList.add("step-done");
}

function applyState(s) {
  const wf = s.workflow || "idle";
  const pct = Math.round(s.pct ?? 0);
  document.getElementById("progressFill").style.width = `${pct}%`;
  document.getElementById("pctText").textContent = `${pct}%`;
  document.getElementById("opLine").textContent = s.operation || "—";
  document.getElementById("opLine").classList.toggle("muted", !s.operation);

  badgeForWorkflow(wf);
  stepperClasses(wf);

  const pathOk = document.getElementById("sourcePath").value.trim().length > 0;
  document.getElementById("chkPath").classList.toggle("ok", pathOk);
  document.getElementById("chkSession").classList.toggle("ok", !!s.encoding_complete);

  document.getElementById("sumHash").textContent = s.params?.original_sha256
    ? String(s.params.original_sha256).slice(0, 24) + "…"
    : "—";
  document.getElementById("sumSize").textContent =
    s.params?.original_size_bytes != null ? `${s.params.original_size_bytes} B` : "—";
  document.getElementById("sumBlocks").textContent =
    s.params?.seed_block_count != null ? String(s.params.seed_block_count) : "—";
  document.getElementById("sumOut").textContent = s.result_path || "—";

  const busy = !!s.running;
  document.getElementById("btnEncode").disabled = busy || !pathOk;
  document.getElementById("btnSummon").disabled = busy || !s.encoding_complete;
  document.getElementById("btnFile").disabled = busy;
  document.getElementById("btnFolder").disabled = busy;
  document.getElementById("deviceCount").disabled = busy;
  document.getElementById("btnFinder").disabled = !s.result_path;
  document.getElementById("btnLoadSession").disabled = busy;
  document.getElementById("btnSaveSession").disabled = busy || !s.encoding_complete;
  document.getElementById("btnReset").disabled = busy;

  const dh = document.getElementById("diskHint");
  if (s.session_file_exists) {
    dh.textContent = `Disk session: ${s.session_file_path}`;
  } else {
    dh.textContent = "No disk session yet (created after successful encode).";
  }

  renderLogTail(s.event_log || []);
  renderParams(s.params || {});

  if (s.error) showBanner(s.error);
  else showBanner("");
}

function renderLogTail(lines) {
  const el = document.getElementById("logTail");
  const tail = lines.slice(-LOG_TAIL);
  el.innerHTML = tail
    .map((ln) => {
      const err = ln.includes("[ERROR]");
      return `<div class="log-line${err ? " err" : ""}">${escapeHtml(ln)}</div>`;
    })
    .join("") || `<div class="log-line muted">—</div>`;
}

function renderParams(p) {
  const el = document.getElementById("paramList");
  const keys = Object.keys(p).sort();
  if (!keys.length) {
    el.innerHTML = "";
    return;
  }
  el.innerHTML = keys
    .map((k) => {
      let v = p[k];
      if (v && typeof v === "object") v = JSON.stringify(v);
      const vs = String(v);
      const short = vs.length > 120 ? vs.slice(0, 117) + "…" : vs;
      return `<div class="param-item"><strong>${escapeHtml(k)}</strong> ${escapeHtml(
        short
      )}</div>`;
    })
    .join("");
}

function startJob() {
  jobRunning = true;
  setPoll(true);
}

async function boot() {
  try {
    const s = await eel.get_state()();
    applyState(s);
  } catch (e) {
    console.error(e);
  }
}

document.getElementById("btnFile").addEventListener("click", async () => {
  showBanner("");
  const p = await eel.pick_file()();
  if (p) {
    document.getElementById("sourcePath").value = p;
    document.getElementById("isFolder").value = "false";
    const s = await eel.get_state()();
    applyState(s);
  }
});

document.getElementById("btnFolder").addEventListener("click", async () => {
  showBanner("");
  const p = await eel.pick_folder()();
  if (p) {
    document.getElementById("sourcePath").value = p;
    document.getElementById("isFolder").value = "true";
    const s = await eel.get_state()();
    applyState(s);
  }
});

document.getElementById("btnEncode").addEventListener("click", async () => {
  const path = document.getElementById("sourcePath").value.trim();
  const isFolder = document.getElementById("isFolder").value === "true";
  const n = parseInt(document.getElementById("deviceCount").value, 10) || 1;
  showBanner("");
  const r = await eel.start_encoding(path, isFolder, n)();
  if (!r.ok) {
    showBanner(r.error);
    return;
  }
  startJob();
});

document.getElementById("btnSummon").addEventListener("click", async () => {
  showBanner("");
  const r = await eel.start_summon()();
  if (!r.ok) {
    showBanner(r.error);
    return;
  }
  startJob();
});

document.getElementById("btnFinder").addEventListener("click", async () => {
  const s = await eel.get_state()();
  if (s.result_path) await eel.open_in_finder(s.result_path)();
});

document.getElementById("btnLoadSession").addEventListener("click", async () => {
  showBanner("");
  const r = await eel.load_saved_session()();
  if (!r.ok) {
    showBanner(r.error);
    return;
  }
  await boot();
});

document.getElementById("btnSaveSession").addEventListener("click", async () => {
  showBanner("");
  const r = await eel.save_session_now()();
  if (!r.ok) {
    showBanner(r.error);
    return;
  }
  await boot();
});

document.getElementById("btnReset").addEventListener("click", async () => {
  if (!confirm("Reset workspace? Clears memory session and disk session file.")) return;
  showBanner("");
  const r = await eel.reset_workspace()();
  if (!r.ok) {
    showBanner(r.error);
    return;
  }
  document.getElementById("sourcePath").value = "";
  document.getElementById("isFolder").value = "false";
  await boot();
});

document.getElementById("btnToggleParams").addEventListener("click", () => {
  const d = document.getElementById("paramsDrawer");
  const btn = document.getElementById("btnToggleParams");
  const open = d.hidden;
  d.hidden = !open;
  btn.setAttribute("aria-expanded", open ? "true" : "false");
  btn.textContent = open ? "Hide parameters" : "Parameters";
});

boot();
