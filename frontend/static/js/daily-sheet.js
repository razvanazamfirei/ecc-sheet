/**
 * Daily Sheet Page JavaScript
 * Handles entry editing, bulk save, auto-lock countdown, and clipboard copy
 */
let editAllMode = false;
const originalValues = {};

/**
 * Copies the daily sheet as a basic HTML table to clipboard
 * @param {Event} event - The click event
 */
async function copyToClipboard(event) {
  const rows = document.querySelectorAll("[data-entry-id]");
  const dateElement = document.getElementById("sheet-date");
  const isWeekendOrHoliday =
    document.querySelector(".start-time-cell") !== null;

  if (!rows.length) {
    alert("No entries to copy");
    return;
  }

  const dateText = dateElement
    ? dateElement.textContent.trim().split("\n")[0].trim()
    : "";

  let html = `<p>Attached is the resident ECC sheet for ${dateText}.</p>`;
  html += "<table>";
  html += "<thead><tr>";
  html += "<th>Role</th>";
  html += "<th>Name</th>";
  if (isWeekendOrHoliday) {
    html += "<th>Start Time</th>";
  }
  html += "<th>Overtime</th>";
  html += "</tr></thead>";
  html += "<tbody>";

  let totalOvertime = 0;

  rows.forEach((row) => {
    const exitCell = row.querySelector(".exit-time-cell");
    const hasMissingData = exitCell && exitCell.classList.contains("missing");

    if (hasMissingData) {
      return;
    }

    const roleElement = row.querySelector("td:nth-child(1) .badge");
    const nameElement = row.querySelector("td:nth-child(2)");
    const overtimeElement = row.querySelector(".overtime-cell span");

    const role = roleElement ? roleElement.textContent.trim() : "";
    const name = nameElement ? nameElement.textContent.trim() : "";
    const overtime = overtimeElement ? overtimeElement.textContent.trim() : "";

    html += "<tr>";
    html += `<td>${role}</td>`;
    html += `<td>${name}</td>`;

    if (isWeekendOrHoliday) {
      const startElement = row.querySelector(".start-time-cell span");
      const start = startElement ? startElement.textContent.trim() : "-";
      html += `<td>${start}</td>`;
    }

    html += `<td>${overtime}</td>`;
    html += "</tr>";

    const overtimeMatch = overtime.match(/[\d.]+/);
    if (overtimeMatch) {
      totalOvertime += parseFloat(overtimeMatch[0]);
    }
  });

  html += "</tbody>";
  html += "<tfoot><tr>";
  html += `<td colspan='${isWeekendOrHoliday ? "3" : "2"}'><strong>Total Overtime:</strong></td>`;
  html += `<td><strong>${totalOvertime.toFixed(2)} hrs</strong></td>`;
  html += "</tr></tfoot>";
  html += "</table>";

  try {
    const htmlBlob = new Blob([html], { type: "text/html" });
    const textBlob = new Blob([html], { type: "text/plain" });
    const clipboardItem = new ClipboardItem({
      "text/html": htmlBlob,
      "text/plain": textBlob,
    });

    await navigator.clipboard.write([clipboardItem]);

    const btn = event.target.closest("button");
    const originalHTML = btn.innerHTML;
    btn.innerHTML = '<i class="bi bi-check-circle me-1"></i>Copied!';
    btn.classList.remove("btn-outline-primary");
    btn.classList.add("btn-success");
    setTimeout(() => {
      btn.innerHTML = originalHTML;
      btn.classList.remove("btn-success");
      btn.classList.add("btn-outline-primary");
    }, 2000);
  } catch (err) {
    alert("Failed to copy to clipboard. Please try again.");
    console.error("Clipboard error:", err);
  }
}

/**
 * Shows confirmation dialog when locking sheet with missing exit times
 * @param {HTMLFormElement} form - The lock form element
 * @returns {boolean} Whether to proceed with locking
 */
function confirmLockWithMissing(form) {
  const missingCount = form.dataset.missingCount;
  const missingResidents = JSON.parse(form.dataset.missingResidents || "[]");
  const message =
    "Warning: " +
    missingCount +
    " entries are missing exit times.\n\n" +
    "These residents will not receive overtime credit:\n" +
    missingResidents.join(", ") +
    "\n\nLock anyway?";
  return confirm(message);
}

/**
 * Enables edit mode for a single entry
 * @param {number} entryId - The entry ID to edit
 */
function editEntry(entryId) {
  // Store original value for exit time
  const input = document.getElementById("input-" + entryId);
  originalValues[entryId] = { exit: input.value };

  // Store original value for start time if it exists (backup roles)
  const startInput = document.getElementById("start-input-" + entryId);
  if (startInput) {
    originalValues[entryId].start = startInput.value;
    // Show start time input
    const startDisplay = document.getElementById("start-display-" + entryId);
    if (startDisplay) {
      startDisplay.style.display = "none";
    }
    startInput.style.display = "inline";
  }

  // Toggle visibility
  document.getElementById("display-" + entryId).style.display = "none";
  document.getElementById("form-" + entryId).style.display = "inline";

  // Toggle buttons
  const editBtnGroup = document.getElementById("edit-controls-" + entryId);
  const actionsGroup = document.getElementById("action-buttons-" + entryId);
  actionsGroup.style.display = "none";
  editBtnGroup.style.display = "inline-flex";

  // Focus the input
  input.focus();
}

/**
 * Saves a single entry by submitting its form
 * @param {number} entryId - The entry ID to save
 */
function saveEntry(entryId) {
  document.getElementById("form-" + entryId).submit();
}

/**
 * Cancels edit mode for a single entry
 * @param {number} entryId - The entry ID to cancel
 */
function cancelEdit(entryId) {
  // Restore original values
  if (originalValues[entryId] !== undefined) {
    const exitInput = document.getElementById("input-" + entryId);
    if (typeof originalValues[entryId] === "object") {
      exitInput.value = originalValues[entryId].exit || "";
      // Restore start time if it exists
      const startInput = document.getElementById("start-input-" + entryId);
      if (startInput && originalValues[entryId].start !== undefined) {
        startInput.value = originalValues[entryId].start;
      }
    } else {
      // Legacy: single value for exit time only
      exitInput.value = originalValues[entryId];
    }
  }

  // Hide start time input if it exists
  const startInput = document.getElementById("start-input-" + entryId);
  const startDisplay = document.getElementById("start-display-" + entryId);
  if (startInput) {
    startInput.style.display = "none";
  }
  if (startDisplay) {
    startDisplay.style.display = "inline";
  }

  // Toggle visibility
  document.getElementById("display-" + entryId).style.display = "inline";
  document.getElementById("form-" + entryId).style.display = "none";

  // Toggle buttons
  const editBtnGroup = document.getElementById("edit-controls-" + entryId);
  const actionsGroup = document.getElementById("action-buttons-" + entryId);
  actionsGroup.style.display = "inline-flex";
  editBtnGroup.style.display = "none";
}

/**
 * Toggles edit mode for all entries at once
 */
function toggleEditAll() {
  editAllMode = !editAllMode;
  const buttonContainer = document.getElementById("edit-all-controls");
  const editAllBtn = document.getElementById("edit-all-btn");
  const saveAllBtn = document.getElementById("save-all-btn");

  if (editAllMode) {
    // Enable edit mode for all entries
    buttonContainer.classList.add("btn-group");
    editAllBtn.innerHTML = '<i class="bi bi-x-circle me-1"></i>Cancel All';
    editAllBtn.classList.remove("btn-outline-secondary");
    editAllBtn.classList.add("btn-warning");
    saveAllBtn.style.display = "inline-block";

    // Get all entry rows and enable editing
    const rows = document.querySelectorAll("[data-entry-id]");
    rows.forEach((row) => {
      const entryId = row.dataset.entryId;
      editEntry(entryId);
    });
  } else {
    // Disable edit mode for all entries
    editAllBtn.innerHTML = '<i class="bi bi-pencil-square me-1"></i>Edit All';
    buttonContainer.classList.remove("btn-group");
    editAllBtn.classList.remove("btn-warning");
    editAllBtn.classList.add("btn-outline-secondary");
    saveAllBtn.style.display = "none";

    // Cancel all edits
    const rows = document.querySelectorAll("[data-entry-id]");
    rows.forEach((row) => {
      const entryId = row.dataset.entryId;
      cancelEdit(entryId);
    });
  }
}

/**
 * Saves all entries asynchronously
 */
async function saveAll() {
  const rows = document.querySelectorAll("[data-entry-id]");
  const savePromises = [];
  const saveAllBtn = document.getElementById("save-all-btn");
  const editAllBtn = document.getElementById("edit-all-btn");

  // Disable buttons and show loading state
  saveAllBtn.disabled = true;
  editAllBtn.disabled = true;
  saveAllBtn.innerHTML =
    '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Saving...';

  // Collect all forms to submit
  for (const row of rows) {
    const entryId = row.dataset.entryId;
    const form = document.getElementById("form-" + entryId);
    const formData = new FormData(form);

    // Submit each form via fetch
    const promise = fetch(form.action, {
      method: "POST",
      body: formData,
    });
    savePromises.push(promise);
  }

  try {
    // Wait for all saves to complete
    await Promise.all(savePromises);
    // Reload the page to show updated data
    window.location.reload();
  } catch (error) {
    // Re-enable buttons on error
    saveAllBtn.disabled = false;
    editAllBtn.disabled = false;
    saveAllBtn.innerHTML = '<i class="bi bi-check-all me-1"></i>Save All';
    alert("Error saving entries. Please try again.");
    console.error("Save all error:", error);
  }
}

/**
 * Updates the auto-lock countdown timer
 */
function updateCountdown() {
  const timer = document.getElementById("countdown-timer");
  if (!timer) {
    return;
  }

  let minutes = parseInt(timer.dataset.minutes);
  if (minutes > 0) {
    minutes--;
    timer.dataset.minutes = minutes;
    timer.textContent = `(${minutes} minutes remaining)`;

    if (minutes === 0) {
      timer.textContent = "(Locking now...)";
      // Reload page after a few seconds to show locked state
      setTimeout(() => window.location.reload(), 3000);
    }
  }
}

/**
 * Initializes the countdown timer interval
 */
function initializeCountdown() {
  if (document.getElementById("countdown-timer")) {
    setInterval(updateCountdown, 60000); // 60 seconds
  }
}

// Expose functions globally for onclick handlers
window.confirmLockWithMissing = confirmLockWithMissing;
window.editEntry = editEntry;
window.saveEntry = saveEntry;
window.cancelEdit = cancelEdit;
window.toggleEditAll = toggleEditAll;
window.saveAll = saveAll;
window.copyToClipboard = copyToClipboard;

/**
 * Toggles start time field visibility based on selected role
 */
function toggleStartTimeField() {
  const roleSelect = document.getElementById("role_id");
  const startTimeContainer = document.getElementById("start_time_container");

  if (!roleSelect || !startTimeContainer) {
    return;
  }

  const selectedOption = roleSelect.options[roleSelect.selectedIndex];
  const isBackup = selectedOption?.dataset?.isBackup === "true";

  startTimeContainer.style.display = isBackup ? "block" : "none";
}

/**
 * Initialize role select change handler
 */
function initializeRoleSelect() {
  const roleSelect = document.getElementById("role_id");
  if (roleSelect) {
    roleSelect.addEventListener("change", toggleStartTimeField);
    // Check initial state
    toggleStartTimeField();
  }
}

// Initialize when DOM is ready
function initializePage() {
  initializeCountdown();
  initializeRoleSelect();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializePage);
} else {
  initializePage();
}
