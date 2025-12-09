/**
 * Luxon Date/Time Utilities for ECC Sheet
 * Provides timezone-aware date operations and formatting
 */

const { DateTime } = luxon;
const TIMEZONE = "America/New_York"; // Philadelphia timezone

/**
 * Gets current date in Philadelphia timezone
 * @returns {DateTime} Luxon DateTime object for today
 */
function getTodayPhilly() {
    return DateTime.now().setZone(TIMEZONE);
}

/**
 * Formats a date string or DateTime to display format
 * @param {string|DateTime} date - Date to format
 * @param {string} format - Luxon format string (default: 'MMMM dd, yyyy')
 * @returns {string} Formatted date string
 */
function formatDate(date, format = "MMMM dd, yyyy") {
    let dt;
    if (typeof date === "string") {
        dt = DateTime.fromISO(date, { zone: TIMEZONE });
    } else if (date instanceof DateTime) {
        dt = date;
    } else {
        dt = DateTime.fromJSDate(date, { zone: TIMEZONE });
    }
    return dt.toFormat(format);
}

/**
 * Formats a time string to display format
 * @param {string} time - Time in HH:mm format
 * @param {string} format - Luxon format string (default: 'HH:mm')
 * @returns {string} Formatted time string
 */
function formatTime(time, format = "HH:mm") {
    if (!time) {
        return "-";
    }
    const dt = DateTime.fromFormat(time, "HH:mm", { zone: TIMEZONE });
    return dt.toFormat(format);
}

/**
 * Gets date N days ago from today
 * @param {number} days - Number of days to go back
 * @returns {DateTime} Luxon DateTime object
 */
function getDaysAgo(days) {
    return getTodayPhilly().minus({ days });
}

/**
 * Gets date N days from today
 * @param {number} days - Number of days forward
 * @returns {DateTime} Luxon DateTime object
 */
function getDaysFromNow(days) {
    return getTodayPhilly().plus({ days });
}

/**
 * Converts DateTime to YYYY-MM-DD format for forms
 * @param {DateTime} dt - Luxon DateTime object
 * @returns {string} Date string in YYYY-MM-DD format
 */
function toISODate(dt) {
    return dt.toISODate();
}

/**
 * Calculates date range for quick reports
 * @param {string} period - 'week', 'month', 'quarter', 'year'
 * @returns {Object} Object with startDate and endDate as ISO strings
 */
function getDateRange(period) {
    const end = getTodayPhilly();
    let start;

    switch (period) {
        case "week":
            start = end.minus({ days: 7 });
            break;
        case "month":
            start = end.minus({ days: 30 });
            break;
        case "quarter":
            start = end.minus({ days: 90 });
            break;
        case "year":
            start = end.minus({ years: 1 });
            break;
        default:
            start = end.minus({ days: 7 });
    }

    return {
        startDate: toISODate(start),
        endDate: toISODate(end),
    };
}

/**
 * Rounds time UP to next 15-minute increment
 * @param {string} time - Time string in HH:mm format
 * @returns {string} Rounded time string in HH:mm format
 */
function roundToQuarterHour(time) {
    if (!time) {
        return time;
    }

    const [hours, minutes] = time.split(":").map(Number);
    const dt = DateTime.fromObject({ hour: hours, minute: minutes }, { zone: TIMEZONE });

    // Round minutes UP to next 15-minute increment
    const roundedMinutes = Math.ceil(minutes / 15) * 15;

    let finalDt;
    if (roundedMinutes === 60) {
        finalDt = dt.plus({ hours: 1 }).set({ minute: 0 });
    } else {
        finalDt = dt.set({ minute: roundedMinutes });
    }

    return finalDt.toFormat("HH:mm");
}

/**
 * Validates if a date is within a reasonable range
 * @param {string|DateTime} date - Date to validate
 * @param {number} yearsBack - Years back allowed (default: 1)
 * @param {number} yearsForward - Years forward allowed (default: 1)
 * @returns {boolean} Whether date is valid
 */
function isValidDateRange(date, yearsBack = 1, yearsForward = 1) {
    let dt;
    if (typeof date === "string") {
        dt = DateTime.fromISO(date, { zone: TIMEZONE });
    } else {
        dt = date;
    }

    const today = getTodayPhilly();
    const minDate = today.minus({ years: yearsBack });
    const maxDate = today.plus({ years: yearsForward });

    return dt >= minDate && dt <= maxDate;
}

/**
 * Converts DateTime to human-readable relative format
 * @param {string|DateTime} date - Date to format
 * @returns {string} Relative format (e.g., "2 days ago", "in 3 days")
 */
function toRelative(date) {
    let dt;
    if (typeof date === "string") {
        dt = DateTime.fromISO(date, { zone: TIMEZONE });
    } else {
        dt = date;
    }
    return dt.toRelative();
}

// Export functions for use in other modules
window.LuxonUtils = {
    DateTime,
    TIMEZONE,
    getTodayPhilly,
    formatDate,
    formatTime,
    getDaysAgo,
    getDaysFromNow,
    toISODate,
    getDateRange,
    roundToQuarterHour,
    isValidDateRange,
    toRelative,
};
