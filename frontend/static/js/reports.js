/**
 * Reports Page JavaScript
 * Handles date range selection and resident filtering
 */

/**
 * Sets the date range for the report form
 * @param {string} period - The period to set ('week', 'month', 'quarter')
 * @param {boolean} autoSubmit - Whether to auto-submit the form (default: true)
 */
function setDateRange(period, autoSubmit = true) {
  // Use Luxon utilities for timezone-aware date calculations
  const dateRange = window.LuxonUtils.getDateRange(period);

  document.getElementById("start_date").value = dateRange.startDate;
  document.getElementById("end_date").value = dateRange.endDate;

  // Auto-submit the form if requested (for quick report buttons)
  if (autoSubmit) {
    document.getElementById("report-form").submit();
  }
}

/**
 * Loads active residents into the filter dropdown
 */
function loadResidentsForReport() {
  fetch("/api/residents/active")
    .then((response) => response.json())
    .then((residents) => {
      const select = document.getElementById("resident_filter");
      select.innerHTML = '<option value="">All Residents</option>';
      residents.forEach((resident) => {
        const option = document.createElement("option");
        option.value = resident.id;
        option.textContent = resident.name;
        select.appendChild(option);
      });
    })
    .catch((error) => {
      console.error("Error loading residents:", error);
    });
}

/**
 * Initializes the reports page
 */
function initializeReports() {
  // Set default to last 7 days (without auto-submit)
  setDateRange("week", false);
  // Load residents into dropdown
  loadResidentsForReport();
}

// Expose functions globally for onclick handlers
window.setDateRange = setDateRange;

// Initialize when DOM is ready
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initializeReports);
} else {
  initializeReports();
}
