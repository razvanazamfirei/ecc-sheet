/**
 * ECC Sheet Frontend - Vanilla JavaScript
 * Handles form interactions, validation, and UI enhancements
 */

/**
 * Rounds a time string to the nearest 5-minute increment using Luxon
 * @param {string} time - Time string in HH:MM format
 * @returns {string} Rounded time string in HH:MM format
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
 * Shows a confirmation dialog for destructive actions
 * @param {string} [message] - Optional custom message
 * @returns {boolean} User's confirmation choice
 */
function confirmDelete(message) {
  return confirm(message || "Are you sure you want to delete this?");
}

/**
 * Auto-hides flash messages after a delay
 */
function initializeAlerts() {
  const alerts = document.querySelectorAll(".alert");

  alerts.forEach((alert) => {
    setTimeout(() => {
      alert.style.transition = "opacity 0.5s";
      alert.style.opacity = "0";
      setTimeout(() => alert.remove(), 500);
    }, 5000);
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
 * Shows a notification message to the user
 * @param {string} message - Message to display
 * @param {string} [type='success'] - Type of notification (success, error, warning)
 */
function showNotification(message, type = "success") {
  const notification = document.createElement("div");
  notification.className = `alert alert-${type}`;
  notification.textContent = message;

  const container = document.querySelector(".container");
  if (container) {
    container.insertBefore(notification, container.firstChild);

    // Auto-remove after 5 seconds
    setTimeout(() => {
      notification.style.transition = "opacity 0.5s";
      notification.style.opacity = "0";
      setTimeout(() => notification.remove(), 500);
    }, 5000);
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
  // Initialize time input rounding
  initializeTimeInputs();

  // Initialize flash message auto-hide
  initializeAlerts();

  // Load residents if on daily sheet page
  if (document.getElementById("resident_id")) {
    loadActiveResidents().catch(console.error);
  }

  // Add form validation
  const forms = document.querySelectorAll("form");
  forms.forEach((form) => {
    form.addEventListener("submit", function (e) {
      if (!validateForm(this)) {
        e.preventDefault();
        showNotification("Please fill in all required fields", "error");
      }
    });
  });

  // Expose global functions
  window.confirmDelete = confirmDelete;
  window.printReport = printReport;
  window.getToday = getToday;
  window.getDateDaysAgo = getDateDaysAgo;
  window.goToToday = goToToday;
  window.formatDate = formatDate;
  window.updateDisplayedDate = updateDisplayedDate;
}

// Initialize when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initialize);
} else {
  initialize();
}
