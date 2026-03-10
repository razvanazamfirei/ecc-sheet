/**
 * Daily Sheet Page JavaScript
 * Handles entry editing, bulk save, auto-lock countdown, and clipboard copy
 */
let editAllMode = false;
const originalValues = {};

/**
 * Shows an in-page notification, with alert fallback for isolated contexts
 * @param {string} message - Message to show
 * @param {string} type - Notification type
 */
function notify(message, type) {
  if (window.showNotification) {
    window.showNotification(message, type);
    return;
  }

  const nativeAlert = globalThis.alert || window.alert;
  if (typeof nativeAlert === "function") {
    nativeAlert(message);
  }
}

/**
 * Escapes HTML special characters to prevent XSS
 * @param {string} text - Text to escape
 * @returns {string} Escaped text
 */
function escapeHtml(text) {
  const div = document.createElement("div");
  div.textContent = text;
  return div.innerHTML;
}

/**
 * Copies the daily sheet as a basic HTML table to clipboard
 * @param {Event} event - The click event
 */
async function copyToClipboard(event) {
  const rows = document.querySelectorAll("tr[data-entry-id]");
  const dateElement = document.getElementById("sheet-date");
  const isWeekendOrHoliday =
    document.querySelector(".start-time-cell") !== null;

  if (!rows.length) {
    notify("No entries to copy", "warning");
    return;
  }

  const dateText = dateElement
    ? dateElement.textContent.trim().split("\n")[0].trim()
    : "";

  let html = `<p>Attached is the resident ECC sheet for ${escapeHtml(dateText)}.</p>`;
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

  let plainText = `Attached is the resident ECC sheet for ${dateText}.\n\n`;
  plainText += `Role\tName${isWeekendOrHoliday ? "\tStart Time" : ""}\tOvertime\n`;

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
    html += `<td>${escapeHtml(role)}</td>`;
    html += `<td>${escapeHtml(name)}</td>`;

    plainText += `${role}\t${name}`;

    if (isWeekendOrHoliday) {
      const startElement = row.querySelector(".start-time-cell span");
      const start = startElement ? startElement.textContent.trim() : "-";
      html += `<td>${escapeHtml(start)}</td>`;
      plainText += `\t${start}`;
    }

    html += `<td>${escapeHtml(overtime)}</td>`;
    html += "</tr>";
    plainText += `\t${overtime}\n`;

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

  plainText += `\nTotal Overtime: ${totalOvertime.toFixed(2)} hrs`;

  try {
    const htmlBlob = new Blob([html], { type: "text/html" });
    const textBlob = new Blob([plainText], { type: "text/plain" });
    const clipboardItem = new ClipboardItem({
      "text/html": htmlBlob,
      "text/plain": textBlob,
    });

    await navigator.clipboard.write([clipboardItem]);

    // Update button UI if event came from a button click
    const btn = event?.target?.closest("button");
    if (btn) {
      const originalHTML = btn.innerHTML;
      btn.innerHTML = '<i class="bi bi-check-circle me-1"></i>Copied!';
      btn.classList.remove("btn-outline-primary");
      btn.classList.add("btn-success");
      setTimeout(() => {
        btn.innerHTML = originalHTML;
        btn.classList.remove("btn-success");
        btn.classList.add("btn-outline-primary");
      }, 2000);
    }
  } catch (err) {
    notify("Failed to copy to clipboard. Please try again.", "error");
    console.error("Clipboard error:", err);
  }
}

/**
 * Builds dialog options when locking a sheet with missing exit times
 * @param {HTMLFormElement} form - The lock form element
 * @returns {object} Confirmation dialog options
 */
function getLockConfirmationOptions(form) {
  const missingCount = form.dataset.missingCount;
  const missingResidents = JSON.parse(form.dataset.missingResidents || "[]");
  return {
    title: "Lock Sheet?",
    message:
      "Warning: " +
      missingCount +
      " entries are missing exit times.\n\n" +
      "These residents will not receive overtime credit:\n" +
      missingResidents.join(", ") +
      "\n\nLock anyway?",
    confirmLabel: "Lock Sheet",
    confirmVariant: "warning",
  };
}

/**
 * Shows confirmation dialog when locking sheet with missing exit times
 * @param {HTMLFormElement} form - The lock form element
 * @returns {Promise<boolean>} Whether to proceed with locking
 */
function confirmLockWithMissing(form) {
  const options = getLockConfirmationOptions(form);
  if (window.showConfirmationDialog) {
    return window.showConfirmationDialog(options);
  }

  const nativeConfirm = globalThis.confirm || window.confirm;
  return nativeConfirm ? nativeConfirm(options.message) : true;
}

/**
 * Applies confirmation metadata to the lock form when needed
 */
function initializeLockConfirmation() {
  const form = document.getElementById("lock-sheet-form");
  if (!form || !form.dataset.missingCount) {
    return;
  }

  const options = getLockConfirmationOptions(form);
  form.dataset.confirmTitle = options.title;
  form.dataset.confirmMessage = options.message;
  form.dataset.confirmLabel = options.confirmLabel;
  form.dataset.confirmVariant = options.confirmVariant;
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
 * Updates the display state for an entry after a successful save
 * @param {string|number} entryId - The entry ID
 * @param {object} entry - Saved entry payload
 */
function applyEntryUpdate(entryId, entry) {
  const display = document.getElementById("display-" + entryId);
  if (display) {
    if (entry.missing_exit_time) {
      display.innerHTML =
        '<span class="text-warning"><i class="bi bi-exclamation-triangle-fill"></i> Exit time?</span>';
    } else {
      display.innerHTML = escapeHtml(entry.exit_time_display || "");
    }
  }

  const exitCell = document.getElementById("cell-" + entryId);
  if (exitCell) {
    exitCell.classList.toggle("missing", entry.missing_exit_time);
  }

  const startDisplay = document.getElementById("start-display-" + entryId);
  if (startDisplay) {
    startDisplay.innerHTML = entry.start_time_display
      ? escapeHtml(entry.start_time_display)
      : '<span class="text-muted">-</span>';
  }

  const overtimeDisplay = document.getElementById("overtime-" + entryId);
  if (overtimeDisplay) {
    overtimeDisplay.textContent = entry.overtime_display;
  }

  const row = document.getElementById("entry-row-" + entryId);
  if (row) {
    row.classList.toggle("entry-missing-data", entry.missing_exit_time);
  }

  const exitInput = document.getElementById("input-" + entryId);
  if (exitInput) {
    exitInput.value = entry.exit_time || "";
  }

  const startInput = document.getElementById("start-input-" + entryId);
  if (startInput) {
    startInput.value = entry.start_time || "";
  }

  originalValues[entryId] = {
    exit: entry.exit_time || "",
    start: entry.start_time || "",
  };
}

/**
 * Recalculates the total overtime footer from all rows
 */
function updateTotalOvertime() {
  let total = 0;
  const rows = document.querySelectorAll("tr[data-entry-id]");

  rows.forEach((row) => {
    const overtimeText =
      row.querySelector(".overtime-cell span")?.textContent || "";
    const overtimeMatch = overtimeText.match(/[\d.]+/);
    if (overtimeMatch) {
      total += parseFloat(overtimeMatch[0]);
    }
  });

  const totalElement = document.querySelector("tfoot .overtime-cell strong");
  if (totalElement) {
    totalElement.textContent = `${total.toFixed(2)} hrs`;
  }
}

/**
 * Parses a fetch response as JSON, surfacing HTML/error redirects cleanly
 * @param {Response} response - Fetch response
 * @returns {Promise<object>} Parsed JSON payload
 */
async function parseJsonResponse(response) {
  const contentType = response.headers?.get?.("content-type") || "";
  if (contentType.includes("application/json") || !response.text) {
    return response.json();
  }

  const responseText = await response.text();
  throw new Error(
    responseText.trim().toLowerCase().startsWith("<!doctype")
      ? "The server returned an HTML page instead of JSON. The save may have been redirected or failed before the async response was generated."
      : responseText || "The server returned an unexpected response.",
  );
}

/**
 * Saves a single entry asynchronously
 * @param {string|number} entryId - The entry ID to save
 * @param {object} [options] - Save options
 * @returns {Promise<boolean>} Whether the save succeeded
 */
async function saveEntry(entryId, options = {}) {
  const form = document.getElementById("form-" + entryId);
  if (!form) {
    return false;
  }

  const saveButton = document.querySelector(
    `#edit-controls-${entryId} .save-btn`,
  );
  const cancelButton = document.querySelector(
    `#edit-controls-${entryId} .cancel-btn`,
  );
  const inputs = form.querySelectorAll("input");
  const startInput = document.getElementById("start-input-" + entryId);
  const originalSaveHtml = saveButton?.innerHTML;
  const formData = new FormData(form);

  if (saveButton) {
    saveButton.disabled = true;
    saveButton.innerHTML =
      '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
  }
  if (cancelButton) {
    cancelButton.disabled = true;
  }
  inputs.forEach((input) => {
    input.disabled = true;
  });
  if (startInput) {
    startInput.disabled = true;
  }

  try {
    const response = await fetch(form.action, {
      method: "POST",
      body: formData,
      credentials: "same-origin",
      headers: {
        "Accept": "application/json",
        "X-Expect-JSON": "1",
        "X-Requested-With": "XMLHttpRequest",
      },
    });
    const payload = await parseJsonResponse(response);

    if (!response.ok || !payload.success) {
      throw new Error(
        payload.message || "Error saving entry. Please try again.",
      );
    }

    applyEntryUpdate(entryId, payload.entry);
    updateTotalOvertime();
    cancelEdit(entryId);

    if (options.showSuccess !== false) {
      notify(payload.message || "Entry updated successfully", "success");
    }
    return true;
  } catch (error) {
    notify(error.message || "Error saving entry. Please try again.", "error");
    console.error("Save entry error:", error);
    return false;
  } finally {
    if (saveButton) {
      saveButton.disabled = false;
      saveButton.innerHTML = originalSaveHtml;
    }
    if (cancelButton) {
      cancelButton.disabled = false;
    }
    inputs.forEach((input) => {
      input.disabled = false;
    });
    if (startInput) {
      startInput.disabled = false;
    }
  }
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
    const rows = document.querySelectorAll("tr[data-entry-id]");
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
    const rows = document.querySelectorAll("tr[data-entry-id]");
    rows.forEach((row) => {
      const entryId = row.dataset.entryId;
      cancelEdit(entryId);
    });
  }
}

/**
 * Collects the current inline-edit values for a bulk save request
 * @param {NodeListOf<Element> | Element[]} rows - Entry rows on the page
 * @returns {{ csrfToken: string, entries: object[], controls: object[] }}
 */
function buildBulkSaveRequest(rows) {
  const entries = [];
  const controls = [];
  let csrfToken = "";

  rows.forEach((row) => {
    const entryId = row.dataset.entryId;
    const form = document.getElementById("form-" + entryId);
    if (!form) {
      return;
    }

    const formInputs = Array.from(form.querySelectorAll("input"));
    const startInput = document.getElementById("start-input-" + entryId);
    const csrfInput = formInputs.find((input) => input.name === "csrf_token");
    if (!csrfToken && csrfInput?.value) {
      csrfToken = csrfInput.value;
    }

    entries.push({
      id: entryId,
      exit_time: document.getElementById("input-" + entryId)?.value || "",
      ...(startInput ? { start_time: startInput.value || "" } : {}),
    });
    controls.push({
      formInputs,
      startInput,
      saveButton: document.querySelector(`#edit-controls-${entryId} .save-btn`),
      cancelButton: document.querySelector(
        `#edit-controls-${entryId} .cancel-btn`,
      ),
    });
  });

  return { csrfToken, entries, controls };
}

/**
 * Enables or disables row-level inline-edit controls during bulk save
 * @param {object[]} controls - Row control descriptors from buildBulkSaveRequest
 * @param {boolean} disabled - Whether controls should be disabled
 */
function setBulkSaveDisabled(controls, disabled) {
  controls.forEach(({ formInputs, startInput, saveButton, cancelButton }) => {
    formInputs.forEach((input) => {
      input.disabled = disabled;
    });
    if (startInput) {
      startInput.disabled = disabled;
    }
    if (saveButton) {
      saveButton.disabled = disabled;
    }
    if (cancelButton) {
      cancelButton.disabled = disabled;
    }
  });
}

/**
 * Saves all entries asynchronously
 */
async function saveAll() {
  const rows = document.querySelectorAll("tr[data-entry-id]");
  const saveAllBtn = document.getElementById("save-all-btn");
  const editAllBtn = document.getElementById("edit-all-btn");
  const { csrfToken, entries, controls } = buildBulkSaveRequest(rows);

  if (!entries.length) {
    notify("No entries are available to save.", "warning");
    return;
  }
  if (!csrfToken) {
    notify(
      "Your form session expired. Reload the page and try again.",
      "error",
    );
    return;
  }

  // Disable buttons and show loading state
  saveAllBtn.disabled = true;
  editAllBtn.disabled = true;
  saveAllBtn.innerHTML =
    '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Saving...';
  setBulkSaveDisabled(controls, true);

  try {
    const response = await fetch("/entries/update-all", {
      method: "POST",
      body: JSON.stringify({ entries }),
      credentials: "same-origin",
      headers: {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "X-CSRFToken": csrfToken,
        "X-Expect-JSON": "1",
        "X-Requested-With": "XMLHttpRequest",
      },
    });
    const payload = await parseJsonResponse(response);

    if (!response.ok || !payload.success) {
      throw new Error(
        payload.message || "Error saving entries. Please try again.",
      );
    }

    payload.entries.forEach((entry) => {
      applyEntryUpdate(entry.id, entry);
      cancelEdit(entry.id);
    });
    updateTotalOvertime();

    editAllMode = false;
    editAllBtn.innerHTML = '<i class="bi bi-pencil-square me-1"></i>Edit All';
    document.getElementById("edit-all-controls")?.classList.remove("btn-group");
    editAllBtn.classList.remove("btn-warning");
    editAllBtn.classList.add("btn-outline-secondary");
    saveAllBtn.style.display = "none";
    notify(payload.message || "All entries updated successfully.", "success");
  } catch (error) {
    notify(error.message || "Error saving entries. Please try again.", "error");
    console.error("Save all error:", error);
  } finally {
    setBulkSaveDisabled(controls, false);
    saveAllBtn.disabled = false;
    editAllBtn.disabled = false;
    saveAllBtn.innerHTML = '<i class="bi bi-check-all me-1"></i>Save All';
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
window.initializeInlineEditors = initializeInlineEditors;

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

// Expose for testing
window.toggleStartTimeField = toggleStartTimeField;

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

/**
 * Submits an inline editor form using the browser's submit flow
 * @param {HTMLFormElement | null} form - The inline editor form
 * @returns {void}
 */
function submitInlineEditorForm(form) {
  if (!form) {
    return;
  }

  if (typeof form.requestSubmit === "function") {
    form.requestSubmit();
    return;
  }

  form.dispatchEvent(new Event("submit", { bubbles: true, cancelable: true }));
}

/**
 * Binds async submit and Enter-to-save behavior for inline row editors
 */
function initializeInlineEditors() {
  const forms = document.querySelectorAll(".time-edit-form");
  forms.forEach((form) => {
    const entryId = form.dataset.entryId || form.id.replace("form-", "");
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      await saveEntry(entryId);
    });
  });

  const timeInputs = document.querySelectorAll(
    '[id^="input-"], [id^="start-input-"]',
  );
  timeInputs.forEach((input) => {
    input.addEventListener("keydown", async (event) => {
      const isEnterKey =
        event.key === "Enter" ||
        event.key === "NumpadEnter" ||
        event.code === "Enter" ||
        event.code === "NumpadEnter";
      if (!isEnterKey) {
        return;
      }

      event.preventDefault();
      submitInlineEditorForm(
        input.form ||
          document.getElementById(
            "form-" +
              input.id.replace("start-input-", "").replace("input-", ""),
          ),
      );
    });
  });
}

// Initialize when DOM is ready
function initializePage() {
  initializeCountdown();
  initializeRoleSelect();
  initializeLockConfirmation();
  initializeInlineEditors();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializePage);
} else {
  initializePage();
}
