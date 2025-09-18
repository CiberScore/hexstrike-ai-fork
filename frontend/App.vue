<template>
  <div id="app">
    <header class="header">
      <h1>CiberScore Auto Pentesting Dashboard</h1>
    </header>

    <main class="main-content">
      <div class="target-input">
        <label for="target">Target URL or IP:</label>
        <input
          id="target"
          v-model="target"
          placeholder="example.com or 192.168.1.1"
          @keyup.enter="startScan"
        />
      </div>

      <div style="margin-top: 20px;">
        <button :disabled="!canStart" class="btn-light" @click="startScan">
          {{ running ? "Running..." : "Start Scan" }}
        </button>
        <button class="btn-copy" @click="copyOutput" :disabled="!report">Copy Report</button>
        <button class="btn-download" @click="downloadReport" :disabled="!report">Download Report</button>
      </div>

      <div v-if="jobId" class="scanning-progress" style="margin-top: 20px;">
        <strong>Job ID:</strong> {{ jobId }} <br />
        <strong>Status:</strong> {{ status }} <br />
        <div class="progress-bar" aria-hidden="true">
          <div class="progress" :style="{ width: progressWidth }"></div>
        </div>
        <div v-if="startedAt"><small>Started: {{ startedAt }}</small></div>
        <div v-if="finishedAt"><small>Finished: {{ finishedAt }}</small></div>
      </div>

      <div v-if="error" class="error-message">
        <strong>Error:</strong> {{ error }}
      </div>

      <div class="report-section" v-if="report">
        <div class="report-actions">
          <button class="btn-download" @click="downloadReport">Download</button>
          <button class="btn-copy" @click="copyOutput">Copy</button>
        </div>

        <div class="report-content">
          <pre>{{ report }}</pre>
        </div>
      </div>
    </main>
  </div>
</template>

<script setup>
import { ref, computed } from "vue";

const API_BASE = "http://192.168.10.165:8000";

const target = ref("");
const depth = ref("medium");
const jobId = ref(null);
const status = ref("idle");
const report = ref("");
const error = ref("");
const running = ref(false);
const startedAt = ref(null);
const finishedAt = ref(null);

let pollHandle = null;

const canStart = computed(() => !running.value && target.value.trim().length > 0);
const progressWidth = computed(() => {
  if (status.value === "idle") return "0%";
  if (status.value === "pending") return "10%";
  if (status.value === "running") return "40%";
  if (status.value === "done") return "100%";
  if (status.value === "failed") return "100%";
  return "0%";
});

async function startScan() {
  error.value = "";
  report.value = "";
  jobId.value = null;
  startedAt.value = null;
  finishedAt.value = null;

  if (!canStart.value) {
    error.value = "Please provide a valid target.";
    return;
  }

  running.value = true;
  status.value = "pending";

  try {
    const body = {
      target: target.value
    };

    const res = await fetch(`${API_BASE}/startpentest`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!res.ok) {
      const text = await res.text();
      error.value = `Server returned ${res.status}: ${text}`;
      running.value = false;
      status.value = "idle";
      return;
    }

    const json = await res.json();
    jobId.value = json.job_id;
    status.value = "pending";
    pollHandle = setInterval(pollResult, 2000);
  } catch (err) {
    error.value = String(err);
    running.value = false;
    status.value = "idle";
  }
}

async function pollResult() {
  if (!jobId.value) return;

  try {
    const res = await fetch(`${API_BASE}/result/${encodeURIComponent(jobId.value)}`);
    if (res.status === 404) {
      error.value = "Job not found (404).";
      clearPolling();
      return;
    }
    const json = await res.json();

    status.value = json.status || status.value;
    startedAt.value = json.started_at || startedAt.value;
    finishedAt.value = json.finished_at || finishedAt.value;

    if (json.output) {
      report.value = json.output;
    }

    if (json.status === "done" || json.status === "failed") {
      clearPolling();
      running.value = false;
    }
  } catch (err) {
    error.value = `Polling error: ${err}`;
  }
}

function clearPolling() {
  if (pollHandle) {
    clearInterval(pollHandle);
    pollHandle = null;
  }
}

function downloadReport() {
  if (!report.value) return;
  const blob = new Blob([report.value], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = (target.value ? target.value.replace(/[:/\\?<>|*"']/g, "_") : "report") + ".txt";
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

async function copyOutput() {
  if (!report.value) return;
  try {
    await navigator.clipboard.writeText(report.value);
  } catch (err) {
    console.warn("Copy failed:", err);
  }
}

</script>

