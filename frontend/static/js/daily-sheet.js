/**
 * Daily Sheet Page JavaScript
 * Handles entry editing, bulk save, auto-lock countdown, and clipboard copy
 */
/** biome-ignore-all lint/security/noSecrets: false positive */
let editAllMode = false;
const originalValues = {};
const OVERTIME_VALUE_REGEX = /[\d.]+/;

/**
 * In-memory set of "residentId:roleId" keys for existing entry rows.
 * Initialized on page load; updated on insert/delete.
 * @type {Set<string>}
 */
const existingEntryKeys = new Set();

/**
 * Returns the page-level daily sheet metadata element when present.
 * @returns {HTMLElement|null} Daily sheet page element
 */
function getDailySheetPage() {
  return document.getElementById("daily-sheet-page");
}

/**
 * Reads a boolean data attribute using "true"/"false" string values.
 * @param {HTMLElement|null} element - Element to inspect
 * @param {string} key - dataset key
 * @returns {boolean|null} Parsed boolean or null when not declared
 */
function getBooleanDatasetValue(element, key) {
  const value = element?.dataset?.[key];
  if (value === "true") {
    return true;
  }
  if (value === "false") {
    return false;
  }
  return null;
}

/**
 * Persists the current lock state in page metadata for async UI guards.
 * @param {boolean} locked - Whether the sheet is locked
 */
function setSheetLocked(locked) {
  const page = getDailySheetPage();
  if (page?.dataset) {
    page.dataset.sheetLocked = locked ? "true" : "false";
  }
}

/**
 * Shows or hides elements that are rendered for async unlock but hidden while
 * the sheet is locked.
 * @param {boolean} locked - Whether the sheet is locked
 */
function setLockControlledVisibility(locked) {
  document.querySelectorAll(".lock-hidden-when-locked").forEach((element) => {
    element.style.display = locked ? "none" : "";
  });
}

/**
 * Returns the DOM elements associated with a single entry row
 * @param {string|number} entryId - The entry ID
 * @returns {object} Entry element references
 */
function getEntryElements(entryId) {
  return {
    display: document.getElementById(`display-${entryId}`),
    form: document.getElementById(`form-${entryId}`),
    exitInput: document.getElementById(`input-${entryId}`),
    startInput: document.getElementById(`start-input-${entryId}`),
    startDisplay: document.getElementById(`start-display-${entryId}`),
    editControls: document.getElementById(`edit-controls-${entryId}`),
    actionButtons: document.getElementById(`action-buttons-${entryId}`),
    exitCell: document.getElementById(`cell-${entryId}`),
    row: document.getElementById(`entry-row-${entryId}`),
    overtimeDisplay: document.getElementById(`overtime-${entryId}`),
  };
}

/**
 * Returns the editable controls associated with an entry row
 * @param {string|number} entryId - The entry ID
 * @returns {object} Entry edit controls
 */
function getEntryEditControls(entryId) {
  const elements = getEntryElements(entryId);
  const formInputs = elements.form
    ? Array.from(elements.form.querySelectorAll("input"))
    : [];
  return {
    ...elements,
    formInputs,
    saveButton: document.querySelector(`#edit-controls-${entryId} .save-btn`),
    cancelButton: document.querySelector(
      `#edit-controls-${entryId} .cancel-btn`,
    ),
  };
}

/**
 * Returns all entry rows on the page
 * @returns {NodeListOf<Element>} Entry row elements
 */
function getEntryRows() {
  return document.querySelectorAll("tr[data-entry-id]");
}

/**
 * Updates the inline editor visibility for a single entry row
 * @param {string|number} entryId - The entry ID
 * @param {boolean} editing - Whether the row is in edit mode
 * @returns {object} Entry element references
 */
function setEntryEditingState(entryId, editing) {
  const elements = getEntryElements(entryId);
  if (elements.display?.style) {
    elements.display.style.display = editing ? "none" : "inline";
  }
  if (elements.form?.style) {
    elements.form.style.display = editing ? "inline" : "none";
  }
  if (elements.actionButtons?.style) {
    elements.actionButtons.style.display = editing ? "none" : "inline-flex";
  }
  if (elements.editControls?.style) {
    elements.editControls.style.display = editing ? "inline-flex" : "none";
  }

  if (elements.startInput) {
    elements.startInput.style.display = editing ? "inline" : "none";
  }
  if (elements.startDisplay) {
    elements.startDisplay.style.display = editing ? "none" : "inline";
  }

  return elements;
}

/**
 * Updates the shared Edit All / Save All control state
 * @param {boolean} editing - Whether bulk edit mode is active
 * @returns {object} Control references
 */
function setEditAllControls(editing) {
  const buttonContainer = document.getElementById("edit-all-controls");
  const editAllBtn = document.getElementById("edit-all-btn");
  const saveAllBtn = document.getElementById("save-all-btn");

  if (!editAllBtn || !saveAllBtn) {
    return { buttonContainer, editAllBtn, saveAllBtn };
  }

  if (editing) {
    buttonContainer?.classList.add("btn-group");
    editAllBtn.innerHTML = '<i class="bi bi-x-circle me-1"></i>Cancel All';
    editAllBtn.classList.remove("btn-outline-secondary");
    editAllBtn.classList.add("btn-warning");
    saveAllBtn.style.display = "inline-block";
    return { buttonContainer, editAllBtn, saveAllBtn };
  }

  editAllBtn.innerHTML = '<i class="bi bi-pencil-square me-1"></i>Edit All';
  buttonContainer?.classList.remove("btn-group");
  editAllBtn.classList.remove("btn-warning");
  editAllBtn.classList.add("btn-outline-secondary");
  saveAllBtn.style.display = "none";
  return { buttonContainer, editAllBtn, saveAllBtn };
}

/**
 * Enables or disables the controls for a single inline editor
 * @param {object} controls - Entry edit controls
 * @param {boolean} disabled - Whether controls should be disabled
 */
function setEntryControlsDisabled(controls, disabled) {
  controls.formInputs.forEach((input) => {
    input.disabled = disabled;
  });
  if (controls.saveButton) {
    controls.saveButton.disabled = disabled;
  }
  if (controls.cancelButton) {
    controls.cancelButton.disabled = disabled;
  }
}

/**
 * Returns the CSRF token stored in a form input collection
 * @param {HTMLInputElement[]} inputs - Inputs to inspect
 * @returns {string} CSRF token value or an empty string
 */
function getCsrfTokenFromInputs(inputs) {
  const csrfInput = inputs.find((input) => input.name === "csrf_token");
  return csrfInput?.value || "";
}

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
  const rows = getEntryRows();
  const dateElement = document.getElementById("sheet-date");
  const weekendOrHoliday = isWeekendOrHoliday();

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
  if (weekendOrHoliday) {
    html += "<th>Start Time</th>";
  }
  html += "<th>Overtime</th>";
  html += "</tr></thead>";
  html += "<tbody>";

  let plainText = `Attached is the resident ECC sheet for ${dateText}.\n\n`;
  plainText += `Role\tName${weekendOrHoliday ? "\tStart Time" : ""}\tOvertime\n`;

  let totalOvertime = 0;

  rows.forEach((row) => {
    const exitCell = row.querySelector(".exit-time-cell");
    const hasMissingData = exitCell?.classList.contains("missing");

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

    if (weekendOrHoliday) {
      const startElement = row.querySelector(".start-time-cell span");
      const start = startElement ? startElement.textContent.trim() : "-";
      html += `<td>${escapeHtml(start)}</td>`;
      plainText += `\t${start}`;
    }

    html += `<td>${escapeHtml(overtime)}</td>`;
    html += "</tr>";
    plainText += `\t${overtime}\n`;

    const overtimeMatch = overtime.match(OVERTIME_VALUE_REGEX);
    if (overtimeMatch) {
      totalOvertime += parseFloat(overtimeMatch[0]);
    }
  });

  html += "</tbody>";
  html += "<tfoot><tr>";
  html += `<td colspan='${weekendOrHoliday ? "3" : "2"}'><strong>Total Overtime:</strong></td>`;
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
  if (!form?.dataset.missingCount) {
    return;
  }

  const options = getLockConfirmationOptions(form);
  form.dataset.confirmTitle = options.title;
  form.dataset.confirmMessage = options.message;
  form.dataset.confirmLabel = options.confirmLabel;
  form.dataset.confirmVariant = options.confirmVariant;
}

/**
 * Updates the lock button and lock status display after an async lock toggle.
 * @param {HTMLFormElement} form - The lock form
 * @param {boolean} locked - New lock state
 * @param {string|null} lockedBy - User who locked the sheet
 * @param {string|null} lockedAt - Formatted timestamp
 */
function applyLockToggle(form, locked, lockedBy, lockedAt) {
  // Update button appearance
  const btn = form.querySelector("button[type='submit']");
  if (btn) {
    if (locked) {
      btn.innerHTML = '<i class="bi bi-unlock me-1"></i>Unlock Sheet';
      btn.classList.remove("btn-success");
      btn.classList.add("btn-warning");
    } else {
      btn.innerHTML = '<i class="bi bi-lock me-1"></i>Lock Sheet';
      btn.classList.remove("btn-warning");
      btn.classList.add("btn-success");
    }
    btn.disabled = false;
  }

  // Update or remove the lock status span
  const controls = document.querySelector(".sheet-controls");
  let lockStatus = document.getElementById("lock-status");
  if (locked && lockedBy) {
    if (!lockStatus) {
      lockStatus = document.createElement("span");
      lockStatus.id = "lock-status";
      lockStatus.className = "btn btn-sm";
      controls?.appendChild(lockStatus);
    }
    lockStatus.innerHTML =
      `<i class="bi bi-lock-fill me-1"></i>Locked by ${escapeHtml(lockedBy)}` +
      (lockedAt ? ` at ${escapeHtml(lockedAt)}` : "");
  } else if (lockStatus) {
    lockStatus.remove();
  }

  // If locking while edit-all is active, cancel it before applying locked state.
  if (locked && editAllMode) {
    toggleEditAll();
  }

  setSheetLocked(locked);
  setLockControlledVisibility(locked);

  // Show/hide the Add Entry form and Edit All controls based on lock state
  const addEntryForm = document.querySelector(".add-entry-form");
  if (addEntryForm) {
    addEntryForm.style.display = locked ? "none" : "";
  }
  const editAllControls = document.getElementById("edit-all-controls");
  if (editAllControls) {
    editAllControls.style.display = locked ? "none" : "";
  }

  // Show/hide the Import Schedule button based on lock state
  const importContainer = document.getElementById("import-schedule-container");
  if (importContainer) {
    if (locked) {
      importContainer.classList.add("d-none");
    } else {
      importContainer.classList.remove("d-none");
    }
  }

  // Disable/enable per-row edit/delete buttons
  document
    .querySelectorAll("tr[data-entry-id] [id^='action-buttons-']")
    .forEach((el) => {
      el.style.display = locked ? "none" : "";
    });
  document
    .querySelectorAll("tr[data-entry-id] [id^='edit-controls-']")
    .forEach((el) => {
      el.style.display = "none";
    });
  document.querySelectorAll("tr[data-entry-id] .edit-btn").forEach((btn) => {
    btn.disabled = locked;
  });
  document
    .querySelectorAll("tr[data-entry-id] .time-edit-form")
    .forEach((el) => {
      el.style.display = "none";
    });
}

/**
 * Attaches async fetch to the lock/unlock form.
 * Preserves the missing-exit confirmation guard.
 */
function initializeLockForm() {
  const form = document.getElementById("lock-sheet-form");
  if (!form) {
    return;
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    event.stopImmediatePropagation();

    // Missing-exit guard: when locking with missing entries, confirm first
    const isMissingCount =
      form.dataset.missingCount && parseInt(form.dataset.missingCount, 10) > 0;
    const btn = form.querySelector("button[type='submit']");
    const isUnlocking = btn?.classList.contains("btn-warning");
    if (isMissingCount && !isUnlocking) {
      const proceed = await confirmLockWithMissing(form);
      if (!proceed) {
        return;
      }
    }

    const csrfToken = form.querySelector('[name="csrf_token"]')?.value || "";
    const originalBtnHtml = btn ? btn.innerHTML : "";
    if (btn) {
      btn.disabled = true;
      btn.innerHTML =
        '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
    }

    try {
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        credentials: "same-origin",
        headers: {
          "Accept": "application/json",
          "X-CSRFToken": csrfToken,
          "X-Expect-JSON": "1",
          "X-Requested-With": "XMLHttpRequest",
        },
      });
      const payload = await parseJsonResponse(response);

      if (!response.ok || !payload.success) {
        throw new Error(
          payload.message || "Error toggling sheet lock. Please try again.",
        );
      }

      applyLockToggle(
        form,
        payload.locked,
        payload.locked_by,
        payload.locked_at,
      );
      notify(payload.message || "Sheet lock toggled.", "success");
    } catch (error) {
      notify(
        error.message || "Error toggling sheet lock. Please try again.",
        "error",
      );
      console.error("Lock toggle error:", error);
      if (btn) {
        btn.disabled = false;
        btn.innerHTML = originalBtnHtml;
      }
    }
  });
}

/**
 * Enables edit mode for a single entry
 * @param {number} entryId - The entry ID to edit
 */
function editEntry(entryId) {
  if (isSheetLocked()) {
    return;
  }

  const elements = setEntryEditingState(entryId, true);
  if (!elements.exitInput) {
    return;
  }

  originalValues[entryId] = { exit: elements.exitInput.value };
  if (elements.startInput) {
    originalValues[entryId].start = elements.startInput.value;
  }

  if (typeof elements.exitInput.focus === "function") {
    elements.exitInput.focus();
  }
}

/**
 * Updates the display state for an entry after a successful save
 * @param {string|number} entryId - The entry ID
 * @param {object} entry - Saved entry payload
 */
function applyEntryUpdate(entryId, entry) {
  const elements = getEntryElements(entryId);
  if (elements.display) {
    if (entry.missing_exit_time) {
      elements.display.innerHTML =
        '<span class="text-warning"><i class="bi bi-exclamation-triangle-fill"></i> Exit time?</span>';
    } else {
      elements.display.innerHTML = escapeHtml(entry.exit_time_display || "");
    }
  }

  if (elements.exitCell) {
    elements.exitCell.classList.toggle("missing", entry.missing_exit_time);
  }

  if (elements.startDisplay) {
    elements.startDisplay.innerHTML = entry.start_time_display
      ? escapeHtml(entry.start_time_display)
      : '<span class="text-body-secondary">-</span>';
  }

  if (elements.overtimeDisplay) {
    elements.overtimeDisplay.textContent = entry.overtime_display;
  }

  if (elements.row) {
    elements.row.classList.toggle(
      "entry-missing-data",
      entry.missing_exit_time,
    );
  }

  if (elements.exitInput) {
    elements.exitInput.value = entry.exit_time || "";
  }

  if (elements.startInput) {
    elements.startInput.value = entry.start_time || "";
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
  const rows = getEntryRows();

  rows.forEach((row) => {
    const overtimeText =
      row.querySelector(".overtime-cell span")?.textContent || "";
    const overtimeMatch = overtimeText.match(OVERTIME_VALUE_REGEX);
    if (overtimeMatch) {
      total += parseFloat(overtimeMatch[0]);
    }
  });

  const totalElement = document.querySelector("tfoot .overtime-cell strong");
  if (totalElement) {
    totalElement.textContent = `${total.toFixed(2)} hrs`;
  }

  const summaryElement = document.getElementById("summary-total-overtime");
  if (summaryElement) {
    summaryElement.textContent = total.toFixed(2);
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
  const controls = getEntryEditControls(entryId);
  const { form } = controls;
  if (!form) {
    return false;
  }

  const originalSaveHtml = controls.saveButton?.innerHTML;
  const formData = new FormData(form);
  const csrfToken = getCsrfTokenFromInputs(controls.formInputs);

  if (controls.saveButton) {
    controls.saveButton.innerHTML =
      '<span class="spinner-border spinner-border-sm" role="status" aria-hidden="true"></span>';
  }
  setEntryControlsDisabled(controls, true);

  try {
    const response = await fetch(form.action, {
      method: "POST",
      body: formData,
      credentials: "same-origin",
      headers: {
        "Accept": "application/json",
        "X-CSRFToken": csrfToken,
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
    setEntryControlsDisabled(controls, false);
    if (controls.saveButton) {
      controls.saveButton.innerHTML = originalSaveHtml;
    }
  }
}

/**
 * Cancels edit mode for a single entry
 * @param {number} entryId - The entry ID to cancel
 */
function cancelEdit(entryId) {
  const elements = getEntryElements(entryId);
  if (originalValues[entryId] !== undefined) {
    if (elements.exitInput) {
      elements.exitInput.value = originalValues[entryId].exit || "";
    }
    if (elements.startInput && originalValues[entryId].start !== undefined) {
      elements.startInput.value = originalValues[entryId].start;
    }
  }

  setEntryEditingState(entryId, false);
}

/**
 * Toggles edit mode for all entries at once
 */
function toggleEditAll() {
  editAllMode = !editAllMode;
  setEditAllControls(editAllMode);

  getEntryRows().forEach((row) => {
    const entryId = row.dataset.entryId;
    if (editAllMode) {
      editEntry(entryId);
      return;
    }
    cancelEdit(entryId);
  });
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
    const controlsForEntry = getEntryEditControls(entryId);
    const { form, exitInput, startInput, formInputs } = controlsForEntry;
    if (!form) {
      return;
    }

    if (!csrfToken) {
      csrfToken = getCsrfTokenFromInputs(formInputs);
    }

    entries.push({
      id: entryId,
      exit_time: exitInput?.value || "",
      ...(startInput ? { start_time: startInput.value || "" } : {}),
    });
    controls.push(controlsForEntry);
  });

  return { csrfToken, entries, controls };
}

/**
 * Saves all entries asynchronously
 */
async function saveAll() {
  const rows = getEntryRows();
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
  if (saveAllBtn) {
    saveAllBtn.disabled = true;
    saveAllBtn.innerHTML =
      '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Saving...';
  }
  if (editAllBtn) {
    editAllBtn.disabled = true;
  }
  controls.forEach((controlsForEntry) => {
    setEntryControlsDisabled(controlsForEntry, true);
  });

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
    setEditAllControls(false);
    notify(payload.message || "All entries updated successfully.", "success");
  } catch (error) {
    notify(error.message || "Error saving entries. Please try again.", "error");
    console.error("Save all error:", error);
  } finally {
    controls.forEach((controlsForEntry) => {
      setEntryControlsDisabled(controlsForEntry, false);
    });
    if (saveAllBtn) {
      saveAllBtn.disabled = false;
      saveAllBtn.innerHTML = '<i class="bi bi-check-all me-1"></i>Save All';
    }
    if (editAllBtn) {
      editAllBtn.disabled = false;
    }
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

  let minutes = parseInt(timer.dataset.minutes, 10);
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
window.initializeAddEntryForm = initializeAddEntryForm;
window.initializeAsyncDelete = initializeAsyncDelete;
window.initializeDuplicateEntryWarning = initializeDuplicateEntryWarning;
window.removeEntryRow = removeEntryRow;
window.getExistingEntryKeys = getExistingEntryKeys;
window.initializeLockForm = initializeLockForm;
window.applyLockToggle = applyLockToggle;
window.initializeEntryKeySet = initializeEntryKeySet;

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

/**
 * Determines whether a weekend/holiday start-time column is present in the table
 * @returns {boolean}
 */
function isWeekendOrHoliday() {
  const pageValue = getBooleanDatasetValue(
    getDailySheetPage(),
    "weekendOrHoliday",
  );
  if (pageValue !== null) {
    return pageValue;
  }

  return document.querySelector(".start-time-cell") !== null;
}

/**
 * Returns whether the sheet is currently locked.
 * @returns {boolean}
 */
function isSheetLocked() {
  const pageValue = getBooleanDatasetValue(getDailySheetPage(), "sheetLocked");
  if (pageValue !== null) {
    return pageValue;
  }

  if (!document.getElementById("lock-sheet-form")) {
    return false;
  }

  return document.querySelector(".add-entry-form") === null;
}

/**
 * Builds the full table structure when the entries card is empty.
 * Replaces the "no entries" placeholder with a proper table+tbody+tfoot.
 * @param {boolean} canEdit - Whether the current user can edit entries
 * @param {boolean} weekend - Whether the sheet is a weekend/holiday
 * @returns {HTMLElement} The newly created tbody element
 */
function buildEmptyTable(canEdit, weekend) {
  const cardBody = document.querySelector(".entries-table .card-body");
  if (!cardBody) {
    return null;
  }

  // Remove the "no entries" placeholder
  const noEntries = cardBody.querySelector(".no-entries");
  if (noEntries) {
    noEntries.remove();
  }

  const wrapper = document.createElement("div");
  wrapper.className = "table-responsive";

  const table = document.createElement("table");
  table.className = "table table-striped table-hover mb-0";

  const thead = document.createElement("thead");
  thead.className = "table-light";
  let headHtml = "<tr>";
  headHtml += '<th class="col-2">Role</th>';
  headHtml += '<th class="col-2">Name</th>';
  if (weekend) {
    headHtml += '<th class="col-3">Start Time</th>';
  }
  headHtml += '<th class="col-1">Anes Stop</th>';
  headHtml += '<th class="col-2">Exit Time</th>';
  headHtml += '<th class="col-1">Overtime</th>';
  if (canEdit) {
    headHtml += '<th class="col-1 lock-hidden-when-locked">Actions</th>';
  }
  headHtml += "</tr>";
  thead.innerHTML = headHtml;

  const newTbody = document.createElement("tbody");

  const tfoot = document.createElement("tfoot");
  tfoot.className = "table-light";
  const colSpan = weekend ? 5 : 4;
  tfoot.innerHTML = `<tr>
    <td colspan="${colSpan}"><strong>Total Overtime:</strong></td>
    <td class="overtime-cell"><strong>0.00 hrs</strong></td>
    ${canEdit ? '<td class="lock-hidden-when-locked"></td>' : ""}
  </tr>`;

  table.appendChild(thead);
  table.appendChild(newTbody);
  table.appendChild(tfoot);
  wrapper.appendChild(table);
  cardBody.appendChild(wrapper);

  return newTbody;
}

/**
 * Inserts a new entry row into the entries table after a successful add.
 * @param {object} entry - Entry payload from the server
 * @param {boolean} canEdit - Whether the current user can edit entries
 */
function insertEntryRow(entry, canEdit) {
  const weekend = isWeekendOrHoliday();

  let tbody = document.querySelector(".entries-table tbody");
  if (tbody) {
    // Table exists — remove no-entries placeholder if somehow still present
    const noEntries = document.querySelector(".no-entries");
    if (noEntries) {
      noEntries.remove();
    }
  } else {
    // Table not yet present (empty sheet) — build the full table structure
    tbody = buildEmptyTable(canEdit, weekend);
    if (!tbody) {
      return;
    }
  }

  // Track in in-memory Set
  const residentId = String(entry.resident_id);
  const roleId = String(entry.role_id);
  existingEntryKeys.add(`${residentId}:${roleId}`);

  const isBackup = entry.role_is_backup;
  const missingExit = entry.missing_exit_time;
  const exitTimeDisplay = missingExit
    ? '<span class="text-warning"><i class="bi bi-exclamation-triangle-fill"></i> Exit time?</span>'
    : escapeHtml(entry.exit_time_display || "");
  const startTimeDisplay = entry.start_time_display
    ? escapeHtml(entry.start_time_display)
    : '<span class="text-body-secondary">-</span>';

  let startTimeCell = "";
  if (weekend) {
    if (isBackup) {
      startTimeCell = `
        <td class="start-time-cell" id="start-cell-${entry.id}">
          <span id="start-display-${entry.id}"
            onclick="editEntry(${entry.id})"
            title="Click to edit time">
            ${startTimeDisplay}
          </span>
          <input type="time" name="start_time" form="form-${entry.id}"
            id="start-input-${entry.id}"
            value="${escapeHtml(entry.start_time || "")}"
            step="300" enterkeyhint="done"
            class="form-control" style="display: none; width: 150px;" />
        </td>`;
    } else {
      startTimeCell = `<td class="start-time-cell"><span class="text-body-secondary">-</span></td>`;
    }
  }

  let actionsCell = "";
  if (canEdit) {
    actionsCell = `
      <td id="actions-${entry.id}" class="lock-hidden-when-locked">
        <div class="btn-group action-buttons" role="group"
          id="edit-controls-${entry.id}" style="display: none;">
          <button type="button" onclick="saveEntry(${entry.id})"
            class="btn btn-outline-success save-btn">
            <i class="bi bi-check fs-6"></i>
          </button>
          <button type="button" onclick="cancelEdit(${entry.id})"
            class="btn btn-outline-secondary cancel-btn">
            <i class="bi bi-x fs-6"></i>
          </button>
        </div>
        <div class="btn-group action-buttons" role="group"
          id="action-buttons-${entry.id}">
          <div class="btn-group">
            <button type="button" onclick="editEntry(${entry.id})"
              class="btn btn-outline-primary edit-btn">
              <i class="bi bi-pencil fs-6"></i>
            </button>
          </div>
          <form method="POST" action="/entries/${entry.id}/delete"
            class="btn-group delete-form async-delete-form"
            data-entry-id="${entry.id}"
            data-confirm-title="Delete Entry?"
            data-confirm-message="Delete this entry?"
            data-confirm-label="Delete"
            data-confirm-variant="danger">
            <input type="hidden" name="csrf_token"
              value="${escapeHtml(document.querySelector('[name="csrf_token"]')?.value || "")}" />
            <button type="submit" class="btn btn-outline-danger">
              <i class="bi bi-trash fs-6"></i>
            </button>
          </form>
        </div>
      </td>`;
  }

  const tr = document.createElement("tr");
  tr.className = `align-middle${missingExit ? " entry-missing-data" : ""}`;
  tr.id = `entry-row-${entry.id}`;
  tr.dataset.entryId = String(entry.id);
  tr.dataset.residentId = String(entry.resident_id);
  tr.dataset.roleId = String(entry.role_id);
  tr.dataset.roleIsBackup = String(isBackup);

  tr.innerHTML = `
    <td>
      <span class="badge bg-secondary">${escapeHtml(entry.role_name)}</span>
    </td>
    <td>
      <a href="/residents/${entry.resident_id}"
        class="text-decoration-none text-body">
        ${escapeHtml(entry.resident_name)}
      </a>
    </td>
    ${startTimeCell}
    <td class="anesthesia-stop-time-cell">
      <span class="text-body-secondary fw-lighter fs-6">-</span>
    </td>
    <td class="exit-time-cell${missingExit ? " missing" : ""}"
      id="cell-${entry.id}">
      <span class="time-display" id="display-${entry.id}"
        onclick="editEntry(${entry.id})"
        title="Click to edit time">
        ${exitTimeDisplay}
      </span>
      <form method="POST" action="/entries/${entry.id}/update"
        class="time-edit-form" id="form-${entry.id}"
        data-entry-id="${entry.id}" style="display: none;">
        <input type="hidden" name="csrf_token"
          value="${escapeHtml(document.querySelector('[name="csrf_token"]')?.value || "")}" />
        <input type="time" name="exit_time" id="input-${entry.id}"
          value="${escapeHtml(entry.exit_time || "")}"
          step="300" enterkeyhint="done"
          class="form-control" style="width: 150px;" />
        <button type="submit" class="visually-hidden" tabindex="-1"
          aria-hidden="true">Save</button>
      </form>
    </td>
    <td class="overtime-cell">
      <span id="overtime-${entry.id}">${escapeHtml(entry.overtime_display)}</span>
    </td>
    ${actionsCell}`;

  tbody.appendChild(tr);

  // Wire up the new row's inline editor and delete handler
  const newForm = tr.querySelector(".time-edit-form");
  if (newForm) {
    const entryId = entry.id;
    newForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      await saveEntry(entryId);
    });
  }
  bindAsyncDeleteForm(tr.querySelector(".async-delete-form"));
}

/**
 * Updates the missing-exit-time warning banner after an insert or delete.
 * Reads resident names from all rows with the entry-missing-data class.
 */
function updateMissingExitWarning() {
  const missingRows = document.querySelectorAll("tr.entry-missing-data");
  const missingCount = missingRows.length;

  // Collect names from the name cell (td:nth-child(2) anchor text)
  const names = Array.from(missingRows).map((row) => {
    const anchor = row.querySelector("td:nth-child(2) a");
    return anchor ? anchor.textContent.trim() : "";
  });

  // Find or create the missing-exit alert
  const alert = document.querySelector(
    ".alert.alert-warning:not(.auto-lock-warning)",
  );

  if (missingCount === 0) {
    if (alert) {
      alert.style.display = "none";
    }
    return;
  }

  if (alert) {
    alert.style.display = "";
    const strong = alert.querySelector("strong");
    if (strong) {
      const label =
        missingCount === 1
          ? "entry missing exit time:"
          : "entries missing exit times:";
      strong.textContent = `${missingCount} ${label}`;
    }
    const childNodes = Array.from(alert.childNodes);
    childNodes.forEach((node) => {
      if (node.nodeType === 3 /* TEXT_NODE */) {
        node.textContent = ` ${names.join(", ")} `;
      }
    });
  }

  // Keep the lock form's data attributes in sync
  const lockForm = document.getElementById("lock-sheet-form");
  if (lockForm) {
    if (missingCount > 0) {
      lockForm.dataset.missingCount = String(missingCount);
      lockForm.dataset.missingResidents = JSON.stringify(names);
    } else {
      delete lockForm.dataset.missingCount;
      delete lockForm.dataset.missingResidents;
    }
  }
}

/**
 * Updates the summary entry count shown below the Entries header.
 */
function updateEntrySummaryCount() {
  const rows = getEntryRows();
  const count = rows.length;
  const summaryEl = document.getElementById("sheet-summary");
  if (!summaryEl) {
    return;
  }
  const countEl = summaryEl.querySelector(".entry-count");
  if (countEl) {
    countEl.textContent = `${count} ${count === 1 ? "entry" : "entries"}`;
  }
}

/**
 * Handles async submission of the "Add New Entry" form.
 * On success, inserts the new row directly without a page reload.
 */
function initializeAddEntryForm() {
  const card = document.querySelector(".add-entry-form");
  if (!card) return;
  const form = card.querySelector("form");
  if (!form) return;

  // Determine whether the current user has edit rights (add form is only
  // rendered when can_edit && !locked, so its presence implies canEdit=true).
  const canEdit = true;

  form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const submitBtn = form.querySelector('button[type="submit"]');
    const originalHtml = submitBtn ? submitBtn.innerHTML : "";
    if (submitBtn) {
      submitBtn.disabled = true;
      submitBtn.innerHTML =
        '<span class="spinner-border spinner-border-sm me-1" role="status" aria-hidden="true"></span>Adding...';
    }

    try {
      const csrfToken = form.querySelector('[name="csrf_token"]')?.value || "";
      const response = await fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: {
          "Accept": "application/json",
          "X-CSRFToken": csrfToken,
          "X-Expect-JSON": "1",
          "X-Requested-With": "XMLHttpRequest",
        },
      });

      const payload = await parseJsonResponse(response);

      if (!response.ok || !payload.success) {
        throw new Error(payload.message || "Failed to add entry.");
      }

      // Insert the new row directly into the DOM
      insertEntryRow(payload.entry, canEdit);
      updateTotalOvertime();
      updateEntrySummaryCount();
      updateMissingExitWarning();

      notify(payload.message || "Entry added successfully.", "success");

      // Reset variable fields; keep role selected for rapid repeat-entry
      const residentSelect = form.querySelector('[name="resident_id"]');
      const exitTimeInput = form.querySelector('[name="exit_time"]');
      const startTimeInput = form.querySelector('[name="start_time"]');
      if (residentSelect) residentSelect.value = "";
      if (exitTimeInput) exitTimeInput.value = "";
      if (startTimeInput) startTimeInput.value = "";
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalHtml;
      }
      if (residentSelect) residentSelect.focus();
    } catch (error) {
      notify(error.message || "Error adding entry. Please try again.", "error");
      if (submitBtn) {
        submitBtn.disabled = false;
        submitBtn.innerHTML = originalHtml;
      }
    }
  });
}

/**
 * Initializes the keyboard shortcut to focus the Add Entry form.
 * Pressing n or + focuses the first input of the add-entry form.
 */
function initializeAddEntryShortcut() {
  const card = document.querySelector(".add-entry-form");
  if (!card) return; // Sheet is locked or user cannot edit

  document.addEventListener("keydown", (event) => {
    if (event.key !== "n" && event.key !== "+") return;
    if (isSheetLocked()) return;

    // Do not trigger when focus is inside an interactive element
    const active = document.activeElement;
    if (active) {
      const tag = active.tagName.toLowerCase();
      if (
        tag === "input" ||
        tag === "select" ||
        tag === "textarea" ||
        tag === "button" ||
        active.isContentEditable
      ) {
        return;
      }
    }

    event.preventDefault();
    const firstInput = card.querySelector("select, input");
    if (firstInput && typeof firstInput.focus === "function") {
      firstInput.focus();
    }
  });
}

// Expose for testing
window.insertEntryRow = insertEntryRow;
window.updateMissingExitWarning = updateMissingExitWarning;
window.updateEntrySummaryCount = updateEntrySummaryCount;
window.initializeAddEntryShortcut = initializeAddEntryShortcut;
window.isSheetLocked = isSheetLocked;

/**
 * Removes an entry row from the DOM and updates totals
 * @param {string|number} entryId - The entry ID to remove
 */
function removeEntryRow(entryId) {
  const row = document.getElementById(`entry-row-${entryId}`);
  if (row) {
    const residentId = row.dataset.residentId;
    const roleId = row.dataset.roleId;
    if (residentId && roleId) {
      existingEntryKeys.delete(`${residentId}:${roleId}`);
    }
    row.remove();
  }
  updateTotalOvertime();
  updateEntrySummaryCount();
}

/**
 * Sends an async delete request for a confirmed delete form.
 * @param {HTMLFormElement} form - Delete form
 * @returns {Promise<void>}
 */
async function submitAsyncDelete(form) {
  const entryId = form.dataset.entryId;
  const csrfToken = form.querySelector('[name="csrf_token"]')?.value || "";

  try {
    const response = await fetch(form.action, {
      method: "POST",
      body: new FormData(form),
      headers: {
        "Accept": "application/json",
        "X-CSRFToken": csrfToken,
        "X-Expect-JSON": "1",
        "X-Requested-With": "XMLHttpRequest",
      },
    });
    const payload = await parseJsonResponse(response);

    if (!response.ok || !payload.success) {
      throw new Error(payload.message || "Failed to delete entry.");
    }

    removeEntryRow(entryId);
    notify(payload.message || "Entry deleted successfully.", "success");
  } catch (error) {
    notify(error.message || "Error deleting entry. Please try again.", "error");
    console.error("Delete entry error:", error);
  }
}

/**
 * Attaches async delete handling to one delete form.
 * Defers the first submit to the global confirmation handler when the form
 * declares confirmation data, then handles the confirmed bypass submit via AJAX.
 * @param {HTMLFormElement|null} form - Delete form
 */
function bindAsyncDeleteForm(form) {
  if (!form || form.dataset.asyncDeleteBound === "true") {
    return;
  }

  form.dataset.asyncDeleteBound = "true";
  form.addEventListener("submit", async (event) => {
    if (form.dataset.confirmMessage && form.dataset.confirmBypass !== "true") {
      return;
    }

    event.preventDefault();
    event.stopImmediatePropagation();

    await submitAsyncDelete(form);
  });
}

/**
 * Attaches async delete handlers to all delete forms on the page.
 */
function initializeAsyncDelete() {
  document.querySelectorAll(".async-delete-form").forEach(bindAsyncDeleteForm);
}

/**
 * Returns the in-memory set of "residentId:roleId" keys.
 * @returns {Set<string>}
 */
function getExistingEntryKeys() {
  return existingEntryKeys;
}

/**
 * Populates the in-memory entry key Set from current DOM rows.
 * Called once on page load.
 */
function initializeEntryKeySet() {
  existingEntryKeys.clear();
  document.querySelectorAll("tr[data-entry-id]").forEach((row) => {
    const residentId = row.dataset.residentId;
    const roleId = row.dataset.roleId;
    if (residentId && roleId) {
      existingEntryKeys.add(`${residentId}:${roleId}`);
    }
  });
}

/**
 * Wires up a duplicate-entry warning on the Add Entry form.
 * Shows an inline warning (without blocking submit) when the
 * selected resident+role combo already has a row on this sheet.
 */
function initializeDuplicateEntryWarning() {
  const card = document.querySelector(".add-entry-form");
  if (!card) {
    return;
  }
  const form = card.querySelector("form");
  const roleSelect = form?.querySelector('[name="role_id"]');
  const residentSelect = form?.querySelector('[name="resident_id"]');
  if (!form || !roleSelect || !residentSelect) {
    return;
  }

  // Create the warning element
  const warning = document.createElement("div");
  warning.id = "duplicate-entry-warning";
  warning.className = "alert alert-warning py-1 px-2 mt-2 mb-0 small";
  warning.style.display = "none";
  warning.setAttribute("role", "alert");
  warning.innerHTML =
    '<i class="bi bi-exclamation-triangle-fill me-1"></i>' +
    "This resident already has an entry for this role today.";
  form.querySelector(".mt-3")?.before(warning);

  function checkDuplicate() {
    const residentId = residentSelect.value;
    const roleId = roleSelect.value;
    if (!residentId || !roleId) {
      warning.style.display = "none";
      return;
    }
    const isDuplicate = getExistingEntryKeys().has(`${residentId}:${roleId}`);
    warning.style.display = isDuplicate ? "block" : "none";
  }

  roleSelect.addEventListener("change", checkDuplicate);
  residentSelect.addEventListener("change", checkDuplicate);
}

// Initialize when DOM is ready
function initializePage() {
  initializeEntryKeySet();
  initializeCountdown();
  initializeRoleSelect();
  initializeLockConfirmation();
  initializeLockForm();
  initializeInlineEditors();
  initializeAddEntryForm();
  initializeAsyncDelete();
  initializeDuplicateEntryWarning();
  initializeAddEntryShortcut();
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializePage);
} else {
  initializePage();
}
