/**
 * Reports Page JavaScript
 * Handles date range selection and resident filtering
 */

/**
 * Sets the date range for the report form
 * @param {string} period - The period to set ('week', 'month', 'quarter', 'payroll_half', 'payroll_month')
 * @param {boolean} autoSubmit - Whether to auto-submit the form (default: true)
 */
function setDateRange(period, autoSubmit = true) {
  let dateRange;

  if (period === "payroll_half") {
    dateRange = window.LuxonUtils.getPayrollRange("half");
  } else if (period === "payroll_month") {
    dateRange = window.LuxonUtils.getPayrollRange("month");
  } else {
    // Use Luxon utilities for relative date calculations
    dateRange = window.LuxonUtils.getDateRange(period);
  }

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
async function loadResidentsForReport() {
  if (!document.getElementById("resident_filter")) {
    return;
  }

  try {
    await window.loadResidentsIntoSelect("resident_filter", "All Residents");
  } catch (error) {
    console.error("Error loading residents:", error);
  }
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
