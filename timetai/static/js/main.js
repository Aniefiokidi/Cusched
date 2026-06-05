/* CovenantSched — Main JavaScript */

// ── FLASH AUTO-DISMISS ──
document.querySelectorAll(".flash").forEach(function(el) {
  setTimeout(function() {
    el.style.opacity = "0";
    el.style.transition = "opacity 0.4s";
    setTimeout(function() { el.remove(); }, 400);
  }, 4000);
});

// ── DRAG AND DROP UPLOAD ──
(function() {
  var zones = document.querySelectorAll(".drop-zone");
  zones.forEach(function(zone) {
    var fileInput = zone.querySelector("input[type=file]");
    var fileType = zone.dataset.fileType;

    zone.addEventListener("click", function() { fileInput && fileInput.click(); });

    zone.addEventListener("dragover", function(e) {
      e.preventDefault();
      zone.classList.add("drag-over");
    });

    zone.addEventListener("dragleave", function() {
      zone.classList.remove("drag-over");
    });

    zone.addEventListener("drop", function(e) {
      e.preventDefault();
      zone.classList.remove("drag-over");
      var files = e.dataTransfer.files;
      if (files.length > 0) handleFile(files[0], fileType);
    });

    if (fileInput) {
      fileInput.addEventListener("change", function() {
        if (fileInput.files.length > 0) handleFile(fileInput.files[0], fileType);
      });
    }
  });

  function handleFile(file, fileType) {
    if (!file.name.endsWith(".csv")) {
      showNotification("Only CSV files are accepted.", "error");
      return;
    }

    var formData = new FormData();
    formData.append("file", file);
    formData.append("file_type", fileType);

    updateUploadItem(fileType, file.name, formatBytes(file.size), "uploading");

    fetch("/upload/file", { method: "POST", body: formData })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.success) {
          updateUploadItem(fileType, file.name, formatBytes(file.size), "ok",
            data.count + " records loaded");
          checkAllUploaded();
        } else {
          updateUploadItem(fileType, file.name, formatBytes(file.size), "err", data.error);
        }
      })
      .catch(function(err) {
        updateUploadItem(fileType, file.name, formatBytes(file.size), "err", "Upload failed");
      });
  }

  function updateUploadItem(fileType, name, size, status, extra) {
    var item = document.getElementById("upload-item-" + fileType);
    if (!item) return;
    item.querySelector(".file-name").textContent = name;
    item.querySelector(".file-size").textContent = size + (extra ? " — " + extra : "");
    var statusEl = item.querySelector(".file-status");
    statusEl.className = "file-status " + status;
    statusEl.textContent = status === "ok" ? "✓ Uploaded" : status === "err" ? "✗ Error" : "⟳ Uploading...";
  }

  function checkAllUploaded() {
    var types = ["courses", "rooms", "lecturers", "groups"];
    var allOk = types.every(function(t) {
      var el = document.getElementById("upload-item-" + t);
      return el && el.querySelector(".file-status.ok");
    });
    var btn = document.getElementById("proceed-btn");
    if (btn) btn.disabled = !allOk;
  }

  function formatBytes(bytes) {
    if (bytes < 1024) return bytes + " B";
    return (bytes / 1024).toFixed(1) + " KB";
  }
})();

// ── CONSTRAINT TOGGLE ──
document.querySelectorAll(".constraint-toggle").forEach(function(toggle) {
  toggle.addEventListener("change", function() {
    var cid = this.dataset.id;
    var card = this.closest(".constraint-card");
    fetch("/constraints/toggle/" + cid, { method: "POST" })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (card) card.classList.toggle("inactive", !data.is_active);
      });
  });
});

// ── CONSTRAINT DELETE ──
document.querySelectorAll(".constraint-delete").forEach(function(btn) {
  btn.addEventListener("click", function() {
    var cid = this.dataset.id;
    if (!confirm("Delete this constraint?")) return;
    var card = this.closest(".constraint-card");
    fetch("/constraints/delete/" + cid, { method: "POST" })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (data.success && card) {
          card.style.opacity = "0";
          card.style.transition = "opacity 0.2s";
          setTimeout(function() { card.remove(); }, 200);
        }
      });
  });
});

// ── NATURAL LANGUAGE CONSTRAINT PARSER ──
(function() {
  var parseBtn = document.getElementById("nl-parse-btn");
  var nlInput = document.getElementById("nl-input");
  if (!parseBtn || !nlInput) return;

  parseBtn.addEventListener("click", function() {
    var text = nlInput.value.trim();
    if (!text) { showNotification("Please enter a constraint.", "warning"); return; }

    parseBtn.disabled = true;
    parseBtn.textContent = "Parsing...";

    fetch("/constraints/parse-nl", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: text }),
    })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        parseBtn.disabled = false;
        parseBtn.textContent = "Parse & Add";
        if (data.success) {
          nlInput.value = "";
          showNotification("Constraint parsed and added (" + data.parsed.type + ")", "success");
          setTimeout(function() { window.location.reload(); }, 1000);
        } else {
          showNotification(data.error || "Parse failed.", "error");
        }
      })
      .catch(function() {
        parseBtn.disabled = false;
        parseBtn.textContent = "Parse & Add";
        showNotification("Request failed.", "error");
      });
  });
})();

// ── TIMETABLE GENERATION ──
(function() {
  var startBtn = document.getElementById("start-gen-btn");
  var terminal = document.getElementById("gen-terminal");
  var statusBox = document.getElementById("gen-status");
  if (!startBtn) return;

  var pollInterval = null;

  startBtn.addEventListener("click", function() {
    var semester = document.getElementById("semester-sel")?.value || "FIRST";
    var dept = document.getElementById("dept-sel")?.value || "CST";

    if (terminal) terminal.textContent = "[INFO] Initialising generation session...\n";
    startBtn.disabled = true;
    startBtn.textContent = "Generating...";
    setStep(1);

    var formData = new FormData();
    formData.append("semester", semester);
    formData.append("department", dept);

    fetch("/generate/start", { method: "POST", body: formData })
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (!data.success) {
          showNotification("Failed to start generation.", "error");
          startBtn.disabled = false;
          startBtn.textContent = "Start Generation";
          return;
        }
        var sid = data.session_id;
        pollInterval = setInterval(function() { pollStatus(sid); }, 2000);
      });
  });

  function pollStatus(sid) {
    fetch("/generate/status/" + sid)
      .then(function(r) { return r.json(); })
      .then(function(data) {
        if (terminal) terminal.textContent = coloriseLog(data.log_output || "");
        if (terminal) terminal.scrollTop = terminal.scrollHeight;

        var step = 1;
        if (data.status === "GENERATING")  step = 2;
        if (data.status === "VALIDATING")  step = 4;
        if (data.status === "COMPLETE")    step = 6;
        if (data.status === "FAILED")      step = 6;
        setStep(step);

        if (data.status === "COMPLETE" || data.status === "FAILED") {
          clearInterval(pollInterval);
          startBtn.disabled = false;
          startBtn.textContent = "Re-run Generation";

          if (statusBox) {
            statusBox.style.display = "block";
            statusBox.innerHTML = data.status === "COMPLETE"
              ? '<div class="flash success">Generation complete — ' + data.iteration_count + ' iteration(s), ' +
                data.hard_violations + ' hard violations, ' + data.soft_violations + ' soft violations. ' +
                '<a href="/timetable">View Timetable →</a></div>'
              : '<div class="flash error">Generation failed. Check the log above.</div>';
          }
        }
      });
  }

  function coloriseLog(text) {
    return text
      .replace(/\[ERROR\]/g, "")
      .replace(/\[DONE\]/g, "")
      .replace(/\[INFO\]/g, "")
      .replace(/\[ITER/g, "")
      .replace(/\[VIOLATION\]/g, "");
  }

  function setStep(n) {
    document.querySelectorAll(".step").forEach(function(el, i) {
      el.classList.remove("active", "done");
      if (i + 1 < n) el.classList.add("done");
      else if (i + 1 === n) el.classList.add("active");
    });
  }
})();

// ── TIMETABLE LEVEL FILTER ──
(function() {
  var filter = document.getElementById("level-filter");
  if (!filter) return;
  filter.addEventListener("change", function() {
    var val = this.value;
    document.querySelectorAll(".tt-entry").forEach(function(el) {
      if (!val || el.dataset.level === val) {
        el.style.display = "";
      } else {
        el.style.display = "none";
      }
    });
  });
})();

// ── NOTIFICATION HELPER ──
function showNotification(msg, type) {
  type = type || "info";
  var div = document.createElement("div");
  div.className = "flash " + type;
  div.textContent = msg;
  div.style.position = "fixed";
  div.style.bottom = "24px";
  div.style.right = "24px";
  div.style.zIndex = "9999";
  div.style.padding = "12px 18px";
  div.style.borderRadius = "6px";
  div.style.fontSize = "13px";
  div.style.boxShadow = "0 4px 12px rgba(0,0,0,0.15)";
  document.body.appendChild(div);
  setTimeout(function() {
    div.style.opacity = "0";
    div.style.transition = "opacity 0.4s";
    setTimeout(function() { div.remove(); }, 400);
  }, 3500);
}

// ── BAR CHART ANIMATION ──
window.addEventListener("load", function() {
  document.querySelectorAll(".bar-fill").forEach(function(bar) {
    var target = bar.dataset.width || "0";
    bar.style.width = "0";
    setTimeout(function() { bar.style.width = target + "%"; }, 100);
  });
});
