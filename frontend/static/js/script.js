/**
 * ECC Sheet Frontend - Vanilla JavaScript
 * Handles form interactions, validation, and shared page UI
 */

/**
 * Rounds a time string to the nearest 5-minute increment using Luxon
 * @param {string} time - Time string in HH:MM format
 * @returns {string} Rounded time string
 */
function roundToFiveMinutes(time) {
  return window.LuxonUtils.roundToFiveMinutes(time);
}

/**
 * Applies 5-minute rounding to all time inputs
 */
function initializeTimeInputs() {
  const timeInputs = document.querySelectorAll('input[type="time"]');

  timeInputs.forEach((input) => {
    input.addEventListener("change", function () {
      if (this.value) {
        this.value = roundToFiveMinutes(this.value);
      }
    });
  });
}

/**
 * Returns the container used for page notifications
 * @returns {HTMLElement|null}
 */
function getNotificationContainer() {
  return (
    document.getElementById("notification-container") ||
    document.querySelector(".flash-messages") ||
    document.querySelector(".container")
  );
}

/**
 * Auto-hides flash/notification messages after a delay
 * @param {HTMLElement} alert - Alert element to remove
 */
function scheduleAlertRemoval(alert) {
  setTimeout(() => {
    alert.style.transition = "opacity 0.5s";
    alert.style.opacity = "0";
    setTimeout(() => alert.remove(), 500);
  }, 5000);
}

/**
 * Shows a notification message to the user
 * @param {string} message - Message to display
 * @param {string} [type='success'] - success, error, warning, info
 * @returns {HTMLElement|null}
 */
function showNotification(message, type = "success") {
  const container = getNotificationContainer();
  if (!container) {
    return null;
  }

  const alertType =
    type === "error"
      ? "danger"
      : ["success", "warning", "info", "danger"].includes(type)
        ? type
        : "success";
  const icon =
    alertType === "success"
      ? "check-circle"
      : alertType === "warning"
        ? "exclamation-circle"
        : alertType === "info"
          ? "info-circle"
          : "exclamation-triangle";

  const notification = document.createElement("div");
  notification.className = `alert alert-${alertType} alert-dismissible fade show`;
  notification.role = "alert";

  const iconElement = document.createElement("i");
  iconElement.className = `bi bi-${icon} me-2`;
  notification.appendChild(iconElement);

  const messageElement = document.createElement("span");
  messageElement.textContent = message;
  notification.appendChild(messageElement);

  const closeButton = document.createElement("button");
  closeButton.type = "button";
  closeButton.className = "btn-close";
  closeButton.setAttribute("aria-label", "Close");
  closeButton.addEventListener("click", () => notification.remove());
  notification.appendChild(closeButton);

  container.insertBefore(notification, container.firstChild || null);
  scheduleAlertRemoval(notification);
  return notification;
}

/**
 * Initializes server-rendered alerts
 */
function initializeAlerts() {
  const alerts = document.querySelectorAll(".alert");
  alerts.forEach((alert) => {
    if (alert.dataset.autoDismiss === "false") {
      return;
    }
    scheduleAlertRemoval(alert);
  });
}

/**
 * Returns the shared confirmation dialog elements
 * @returns {object|null}
 */
function getDialogElements() {
  const root = document.getElementById("page-dialog-root");
  const backdrop = document.getElementById("page-dialog-backdrop");
  const title = document.getElementById("page-dialog-title");
  const message = document.getElementById("page-dialog-message");
  const confirmButton = document.getElementById("page-dialog-confirm");
  const cancelButton = document.getElementById("page-dialog-cancel");

  if (
    !root ||
    !backdrop ||
    !title ||
    !message ||
    !confirmButton ||
    !cancelButton
  ) {
    return null;
  }

  return {
    root,
    backdrop,
    title,
    message,
    confirmButton,
    cancelButton,
  };
}

let activeDialogResolver = null;

/**
 * Closes the shared confirmation dialog
 * @param {boolean} result - The confirmation result to resolve with
 */
function closeDialog(result) {
  const elements = getDialogElements();
  if (!elements || elements.root.hidden) {
    return;
  }

  elements.root.hidden = true;
  if (document.body?.classList) {
    document.body.classList.remove("page-dialog-open");
  }

  const resolver = activeDialogResolver;
  activeDialogResolver = null;
  if (resolver) {
    resolver(result);
  }
}

/**
 * Initializes the shared confirmation dialog
 */
function initializeDialog() {
  const elements = getDialogElements();
  if (!elements || elements.root.dataset.initialized === "true") {
    return;
  }

  elements.root.dataset.initialized = "true";
  elements.confirmButton.addEventListener("click", () => closeDialog(true));
  elements.cancelButton.addEventListener("click", () => closeDialog(false));
  elements.backdrop.addEventListener("click", () => closeDialog(false));
  document.addEventListener("keydown", (event) => {
    if (elements.root.hidden) {
      return;
    }

    if (event.key === "Escape") {
      event.preventDefault();
      closeDialog(false);
    }
  });
}

/**
 * Shows the shared confirmation dialog
 * @param {object} options - Dialog options
 * @returns {Promise<boolean>}
 */
function showConfirmationDialog(options = {}) {
  const message = options.message || "Are you sure?";
  const elements = getDialogElements();
  if (!elements) {
    const nativeConfirm = globalThis.confirm || window.confirm;
    return nativeConfirm ? nativeConfirm(message) : true;
  }

  initializeDialog();
  if (activeDialogResolver) {
    closeDialog(false);
  }

  return new Promise((resolve) => {
    activeDialogResolver = resolve;
    elements.title.textContent = options.title || "Please Confirm";
    elements.message.textContent = message;
    elements.confirmButton.textContent = options.confirmLabel || "Continue";
    elements.cancelButton.textContent = options.cancelLabel || "Cancel";
    elements.confirmButton.className = `btn btn-${options.confirmVariant || "primary"}`;
    elements.cancelButton.className =
      options.showCancel === false ? "btn d-none" : "btn btn-outline-secondary";
    elements.root.hidden = false;
    if (document.body?.classList) {
      document.body.classList.add("page-dialog-open");
    }
    if (typeof elements.confirmButton.focus === "function") {
      elements.confirmButton.focus();
    }
  });
}

/**
 * Shows a delete confirmation dialog
 * @param {string} [message] - Optional custom message
 * @returns {Promise<boolean>}
 */
function confirmDelete(message) {
  return showConfirmationDialog({
    title: "Delete Item?",
    message: message || "Are you sure you want to delete this?",
    confirmLabel: "Delete",
    confirmVariant: "danger",
  });
}

/**
 * Handles forms that declare confirmation requirements via data attributes
 * @param {SubmitEvent} event - Submit event
 */
async function handleConfirmSubmit(event) {
  const form = event.target;
  if (!form || typeof form.matches !== "function" || !form.matches("form")) {
    return;
  }

  if (event.defaultPrevented || form.dataset.confirmBypass === "true") {
    return;
  }

  const message = form.dataset.confirmMessage;
  if (!message) {
    return;
  }

  event.preventDefault();
  const confirmed = await showConfirmationDialog({
    title: form.dataset.confirmTitle || "Please Confirm",
    message,
    confirmLabel: form.dataset.confirmLabel || "Continue",
    cancelLabel: form.dataset.confirmCancelLabel || "Cancel",
    confirmVariant: form.dataset.confirmVariant || "primary",
  });

  if (confirmed) {
    form.dataset.confirmBypass = "true";
    try {
      if (typeof form.requestSubmit === "function") {
        form.requestSubmit();
      } else {
        form.submit();
      }
    } finally {
      delete form.dataset.confirmBypass;
    }
  }
}

/**
 * Registers document-level confirmation handling
 */
function initializeConfirmations() {
  document.addEventListener("submit", (event) => {
    handleConfirmSubmit(event).catch((error) => {
      console.error("Confirmation dialog error:", error);
      showNotification("Unable to confirm this action.", "error");
    });
  });
}

/**
 * Triggers the browser's print dialog
 */
function printReport() {
  window.print();
}

/**
 * Formats a date for display using Luxon
 * @param {string|DateTime} date - Date to format
 * @param {string} format - Format string (default: 'MMMM dd, yyyy')
 * @returns {string} Formatted date string
 */
function formatDate(date, format = "MMMM dd, yyyy") {
  return window.LuxonUtils.formatDate(date, format);
}

/**
 * Gets today's date as a formatted string
 * @returns {string} Today's date in YYYY-MM-DD format
 */
function getToday() {
  const today = window.LuxonUtils.getTodayPhilly();
  return window.LuxonUtils.toISODate(today);
}

/**
 * Gets a date N days ago as a formatted string
 * @param {number} days - Number of days to go back
 * @returns {string} Date string in YYYY-MM-DD format
 */
function getDateDaysAgo(days) {
  const date = window.LuxonUtils.getDaysAgo(days);
  return window.LuxonUtils.toISODate(date);
}

/**
 * Navigates to today's sheet
 */
function goToToday() {
  window.location.href = "/";
}

/**
 * Updates the displayed date in the header (if element exists)
 * @param {string} dateString - ISO date string
 */
function updateDisplayedDate(dateString) {
  const dateElement = document.getElementById("sheet-date");
  if (dateElement) {
    dateElement.textContent = window.LuxonUtils.formatDate(dateString);
  }
}

/**
 * Loads active residents from API and populates dropdown
 * @returns {Promise<void>}
 */
async function loadActiveResidents() {
  try {
    const response = await fetch("/api/residents/active");
    if (!response.ok) {
      throw new Error("Failed to fetch residents");
    }

    const residents = await response.json();
    const select = document.getElementById("resident_id");

    if (!select) {
      return;
    }

    select.innerHTML = '<option value="">Select Resident</option>';
    residents.forEach((resident) => {
      const option = document.createElement("option");
      option.value = resident.id.toString();
      option.textContent = resident.name;
      select.appendChild(option);
    });
  } catch (error) {
    console.error("Error loading residents:", error);
    showNotification("Failed to load residents", "error");
  }
}

/**
 * Validates form inputs before submission
 * @param {HTMLFormElement} form - Form element to validate
 * @returns {boolean} Whether form is valid
 */
function validateForm(form) {
  const requiredFields = form.querySelectorAll("[required]");
  let isValid = true;

  requiredFields.forEach((field) => {
    if (field.value.trim()) {
      field.classList.remove("error");
    } else {
      field.classList.add("error");
      isValid = false;
    }
  });

  return isValid;
}

/**
 * Initializes all frontend functionality
 */
function initialize() {
  initializeTimeInputs();
  initializeAlerts();
  initializeDialog();
  initializeConfirmations();

  if (document.getElementById("resident_id")) {
    loadActiveResidents().catch(console.error);
  }

  const forms = document.querySelectorAll("form");
  forms.forEach((form) => {
    form.addEventListener("submit", function (event) {
      if (!validateForm(this)) {
        event.preventDefault();
        showNotification("Please fill in all required fields", "error");
      }
    });
  });

  window.confirmDelete = confirmDelete;
  window.printReport = printReport;
  window.getToday = getToday;
  window.getDateDaysAgo = getDateDaysAgo;
  window.goToToday = goToToday;
  window.formatDate = formatDate;
  window.updateDisplayedDate = updateDisplayedDate;
  window.showNotification = showNotification;
  window.showConfirmationDialog = showConfirmationDialog;
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initialize);
} else {
  initialize();
}
