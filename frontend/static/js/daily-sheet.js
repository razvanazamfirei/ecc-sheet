/**
 * Daily Sheet Page JavaScript
 * Handles entry editing, bulk save, and auto-lock countdown
 */

let editAllMode = false;
const originalValues = {};

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
  // Store original value
  const input = document.getElementById("input-" + entryId);
  originalValues[entryId] = input.value;

  // Toggle visibility
  document.getElementById("display-" + entryId).style.display = "none";
  document.getElementById("form-" + entryId).style.display = "inline";

  // Toggle buttons
  const actionsCell = document.getElementById("actions-" + entryId);
  actionsCell.querySelector(".edit-btn").style.display = "none";
  actionsCell.querySelector(".save-btn").style.display = "inline-block";
  actionsCell.querySelector(".cancel-btn").style.display = "inline-block";
  actionsCell.querySelector(".delete-form").style.display = "none";

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
  // Restore original value
  if (originalValues[entryId] !== undefined) {
    document.getElementById("input-" + entryId).value = originalValues[entryId];
  }

  // Toggle visibility
  document.getElementById("display-" + entryId).style.display = "inline";
  document.getElementById("form-" + entryId).style.display = "none";

  // Toggle buttons
  const actionsCell = document.getElementById("actions-" + entryId);
  actionsCell.querySelector(".edit-btn").style.display = "inline-block";
  actionsCell.querySelector(".save-btn").style.display = "none";
  actionsCell.querySelector(".cancel-btn").style.display = "none";
  actionsCell.querySelector(".delete-form").style.display = "inline";
}

/**
 * Toggles edit mode for all entries at once
 */
function toggleEditAll() {
  editAllMode = !editAllMode;
  const editAllBtn = document.getElementById("edit-all-btn");
  const saveAllBtn = document.getElementById("save-all-btn");

  if (editAllMode) {
    // Enable edit mode for all entries
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

// Initialize countdown when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializeCountdown);
} else {
  initializeCountdown();
}
