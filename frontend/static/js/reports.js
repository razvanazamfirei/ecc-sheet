/**
 * Reports Page JavaScript
 * Handles date range selection and resident filtering
 */

import { PayrollPeriodError } from "./luxon-utils.js";

/**
 * Returns the report form elements when present
 * @returns {object}
 */
function getReportElements() {
  return {
    startDateInput: document.getElementById("start_date"),
    endDateInput: document.getElementById("end_date"),
    reportForm: document.getElementById("report-form"),
  };
}

/**
 * Sets the date range for the report form
 * @param {string} period - The period to set ('week', 'month', 'quarter', 'payroll_half', 'payroll_month')
 * @param {boolean} autoSubmit - Whether to auto-submit the form (default: true)
 */
function setDateRange(period, autoSubmit = true) {
  const { startDateInput, endDateInput, reportForm } = getReportElements();
  if (!startDateInput || !endDateInput || !reportForm) {
    return;
  }

  let dateRange;

  try {
    if (period === "payroll_half") {
      dateRange = window.LuxonUtils.getPayrollRange("half");
    } else if (period === "payroll_month") {
      dateRange = window.LuxonUtils.getPayrollRange("month");
    } else {
      // Use Luxon utilities for relative date calculations
      dateRange = window.LuxonUtils.getDateRange(period);
    }
  } catch (error) {
    if (error instanceof PayrollPeriodError) {
      console.error("Payroll period calculation failed:", error.message);
      // Fallback or alert user
      window.alert(`Could not calculate payroll range: ${error.message}`);
      return;
    }
    throw error;
  }

  startDateInput.value = dateRange.startDate;
  endDateInput.value = dateRange.endDate;

  // Auto-submit the form if requested (for quick report buttons)
  if (autoSubmit) {
    reportForm.submit();
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
  const { startDateInput, endDateInput, reportForm } = getReportElements();
  if (!startDateInput || !endDateInput || !reportForm) {
    return;
  }

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
