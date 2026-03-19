/**
 * Tests for Luxon Date/Time Utilities
 */

import { DateTime, Settings } from "luxon";

// Mock window and luxon globals before importing the module
global.window = {};
global.luxon = { DateTime };

// Now load the module (side effect: populates window.LuxonUtils)
await import("../luxon-utils.js");

const LuxonUtils = global.window.LuxonUtils;

describe("LuxonUtils", () => {
  describe("roundToFiveMinutes", () => {
    test("returns null/undefined for empty input", () => {
      expect(LuxonUtils.roundToFiveMinutes(null)).toBeNull();
      expect(LuxonUtils.roundToFiveMinutes(undefined)).toBeUndefined();
      expect(LuxonUtils.roundToFiveMinutes("")).toBe("");
    });

    test("returns same time for times already on 5-minute mark", () => {
      expect(LuxonUtils.roundToFiveMinutes("10:00")).toBe("10:00");
      expect(LuxonUtils.roundToFiveMinutes("10:05")).toBe("10:05");
      expect(LuxonUtils.roundToFiveMinutes("10:10")).toBe("10:10");
      expect(LuxonUtils.roundToFiveMinutes("10:15")).toBe("10:15");
      expect(LuxonUtils.roundToFiveMinutes("10:20")).toBe("10:20");
      expect(LuxonUtils.roundToFiveMinutes("10:25")).toBe("10:25");
      expect(LuxonUtils.roundToFiveMinutes("10:30")).toBe("10:30");
      expect(LuxonUtils.roundToFiveMinutes("10:35")).toBe("10:35");
      expect(LuxonUtils.roundToFiveMinutes("10:40")).toBe("10:40");
      expect(LuxonUtils.roundToFiveMinutes("10:45")).toBe("10:45");
      expect(LuxonUtils.roundToFiveMinutes("10:50")).toBe("10:50");
      expect(LuxonUtils.roundToFiveMinutes("10:55")).toBe("10:55");
    });

    test("rounds UP to next 5-minute increment", () => {
      expect(LuxonUtils.roundToFiveMinutes("10:01")).toBe("10:05");
      expect(LuxonUtils.roundToFiveMinutes("10:02")).toBe("10:05");
      expect(LuxonUtils.roundToFiveMinutes("10:03")).toBe("10:05");
      expect(LuxonUtils.roundToFiveMinutes("10:04")).toBe("10:05");
      expect(LuxonUtils.roundToFiveMinutes("10:06")).toBe("10:10");
      expect(LuxonUtils.roundToFiveMinutes("10:07")).toBe("10:10");
      expect(LuxonUtils.roundToFiveMinutes("10:11")).toBe("10:15");
      expect(LuxonUtils.roundToFiveMinutes("10:14")).toBe("10:15");
      expect(LuxonUtils.roundToFiveMinutes("10:16")).toBe("10:20");
      expect(LuxonUtils.roundToFiveMinutes("10:19")).toBe("10:20");
      expect(LuxonUtils.roundToFiveMinutes("10:21")).toBe("10:25");
      expect(LuxonUtils.roundToFiveMinutes("10:29")).toBe("10:30");
      expect(LuxonUtils.roundToFiveMinutes("10:31")).toBe("10:35");
      expect(LuxonUtils.roundToFiveMinutes("10:44")).toBe("10:45");
      expect(LuxonUtils.roundToFiveMinutes("10:46")).toBe("10:50");
      expect(LuxonUtils.roundToFiveMinutes("10:56")).toBe("11:00");
      expect(LuxonUtils.roundToFiveMinutes("10:59")).toBe("11:00");
    });

    test("handles hour rollover correctly", () => {
      expect(LuxonUtils.roundToFiveMinutes("09:56")).toBe("10:00");
      expect(LuxonUtils.roundToFiveMinutes("23:56")).toBe("00:00");
    });

    test("handles midnight correctly", () => {
      expect(LuxonUtils.roundToFiveMinutes("00:00")).toBe("00:00");
      expect(LuxonUtils.roundToFiveMinutes("00:01")).toBe("00:05");
      expect(LuxonUtils.roundToFiveMinutes("00:04")).toBe("00:05");
    });
  });

  describe("formatTime", () => {
    test("returns dash for empty time", () => {
      expect(LuxonUtils.formatTime(null)).toBe("-");
      expect(LuxonUtils.formatTime(undefined)).toBe("-");
      expect(LuxonUtils.formatTime("")).toBe("-");
    });

    test("formats valid time correctly", () => {
      expect(LuxonUtils.formatTime("09:30")).toBe("09:30");
      expect(LuxonUtils.formatTime("14:00")).toBe("14:00");
      expect(LuxonUtils.formatTime("00:00")).toBe("00:00");
      expect(LuxonUtils.formatTime("23:59")).toBe("23:59");
    });
  });

  describe("getDateRange", () => {
    beforeEach(() => {
      // Set a fixed time for consistent testing (noon to avoid timezone issues)
      Settings.now = () => new Date(2024, 5, 15, 12, 0, 0).valueOf(); // June 15, 2024 at noon
    });

    afterEach(() => {
      Settings.now = () => Date.now();
    });

    test("returns correct range for week", () => {
      const range = LuxonUtils.getDateRange("week");
      expect(range.endDate).toBe("2024-06-15");
      expect(range.startDate).toBe("2024-06-08");
    });

    test("returns correct range for month", () => {
      const range = LuxonUtils.getDateRange("month");
      expect(range.endDate).toBe("2024-06-15");
      expect(range.startDate).toBe("2024-05-16");
    });

    test("returns correct range for quarter", () => {
      const range = LuxonUtils.getDateRange("quarter");
      expect(range.endDate).toBe("2024-06-15");
      expect(range.startDate).toBe("2024-03-17");
    });

    test("returns correct range for year", () => {
      const range = LuxonUtils.getDateRange("year");
      expect(range.endDate).toBe("2024-06-15");
      expect(range.startDate).toBe("2023-06-15");
    });

    test("defaults to week for unknown period", () => {
      const range = LuxonUtils.getDateRange("invalid");
      expect(range.endDate).toBe("2024-06-15");
      expect(range.startDate).toBe("2024-06-08");
    });
  });

  describe("getPayrollRange", () => {
    test("returns last half of February when today is March 12, 2024", () => {
      Settings.now = () => new Date(2024, 2, 12, 12, 0, 0).valueOf(); // March 12, 2024
      const range = LuxonUtils.getPayrollRange("half");
      expect(range.startDate).toBe("2024-02-16");
      expect(range.endDate).toBe("2024-02-29"); // 2024 is a leap year
    });

    test("returns first half of March when today is March 20, 2024", () => {
      Settings.now = () => new Date(2024, 2, 20, 12, 0, 0).valueOf(); // March 20, 2024
      const range = LuxonUtils.getPayrollRange("half");
      expect(range.startDate).toBe("2024-03-01");
      expect(range.endDate).toBe("2024-03-15");
    });

    test("returns entire month of February when today is March 20, 2024", () => {
      Settings.now = () => new Date(2024, 2, 20, 12, 0, 0).valueOf(); // March 20, 2024
      const range = LuxonUtils.getPayrollRange("month");
      expect(range.startDate).toBe("2024-02-01");
      expect(range.endDate).toBe("2024-02-29");
    });

    test("handles year rollover (January 5, 2024)", () => {
      Settings.now = () => new Date(2024, 0, 5, 12, 0, 0).valueOf(); // Jan 5, 2024
      const halfRange = LuxonUtils.getPayrollRange("half");
      expect(halfRange.startDate).toBe("2023-12-16");
      expect(halfRange.endDate).toBe("2023-12-31");

      const monthRange = LuxonUtils.getPayrollRange("month");
      expect(monthRange.startDate).toBe("2023-12-01");
      expect(monthRange.endDate).toBe("2023-12-31");
    });

    afterEach(() => {
      Settings.now = () => Date.now();
    });
  });

  describe("getTodayPhilly", () => {
    test("returns DateTime object", () => {
      const today = LuxonUtils.getTodayPhilly();
      expect(today).toBeInstanceOf(DateTime);
    });

    test("uses America/New_York timezone", () => {
      const today = LuxonUtils.getTodayPhilly();
      expect(today.zoneName).toBe("America/New_York");
    });
  });

  describe("formatDate", () => {
    test("formats ISO string correctly", () => {
      const result = LuxonUtils.formatDate("2024-06-15");
      expect(result).toBe("June 15, 2024");
    });

    test("formats DateTime correctly", () => {
      const dt = DateTime.fromISO("2024-06-15", {
        zone: "America/New_York",
      });
      const result = LuxonUtils.formatDate(dt);
      expect(result).toBe("June 15, 2024");
    });

    test("formats JavaScript Date object correctly", () => {
      const jsDate = new Date(2024, 5, 15, 12, 0, 0); // June 15, 2024
      const result = LuxonUtils.formatDate(jsDate);
      expect(result).toBe("June 15, 2024");
    });

    test("accepts custom format", () => {
      const result = LuxonUtils.formatDate("2024-06-15", "yyyy-MM-dd");
      expect(result).toBe("2024-06-15");
    });
  });

  describe("getDaysAgo", () => {
    beforeEach(() => {
      Settings.now = () => new Date(2024, 5, 15, 12, 0, 0).valueOf();
    });

    afterEach(() => {
      Settings.now = () => Date.now();
    });

    test("returns correct date for days ago", () => {
      const result = LuxonUtils.getDaysAgo(7);
      expect(result.toISODate()).toBe("2024-06-08");
    });
  });

  describe("getDaysFromNow", () => {
    beforeEach(() => {
      Settings.now = () => new Date(2024, 5, 15, 12, 0, 0).valueOf();
    });

    afterEach(() => {
      Settings.now = () => Date.now();
    });

    test("returns correct date for days from now", () => {
      const result = LuxonUtils.getDaysFromNow(7);
      expect(result.toISODate()).toBe("2024-06-22");
    });
  });

  describe("toISODate", () => {
    test("converts DateTime to ISO date string", () => {
      const dt = DateTime.fromISO("2024-06-15T10:30:00", {
        zone: "America/New_York",
      });
      expect(LuxonUtils.toISODate(dt)).toBe("2024-06-15");
    });
  });

  describe("isValidDateRange", () => {
    beforeEach(() => {
      Settings.now = () => new Date(2024, 5, 15, 12, 0, 0).valueOf();
    });

    afterEach(() => {
      Settings.now = () => Date.now();
    });

    test("returns true for date within range", () => {
      expect(LuxonUtils.isValidDateRange("2024-06-01")).toBe(true);
      expect(LuxonUtils.isValidDateRange("2024-01-01")).toBe(true);
      expect(LuxonUtils.isValidDateRange("2024-12-31")).toBe(true);
    });

    test("returns false for date outside range", () => {
      expect(LuxonUtils.isValidDateRange("2020-01-01")).toBe(false);
      expect(LuxonUtils.isValidDateRange("2030-01-01")).toBe(false);
    });

    test("accepts custom range parameters", () => {
      expect(LuxonUtils.isValidDateRange("2020-06-15", 5, 1)).toBe(true);
      expect(LuxonUtils.isValidDateRange("2028-06-15", 1, 5)).toBe(true);
    });

    test("accepts DateTime object instead of string", () => {
      const dt = DateTime.fromISO("2024-06-01", { zone: "America/New_York" });
      expect(LuxonUtils.isValidDateRange(dt)).toBe(true);
    });

    test("returns false for DateTime object outside range", () => {
      const dt = DateTime.fromISO("2020-01-01", { zone: "America/New_York" });
      expect(LuxonUtils.isValidDateRange(dt)).toBe(false);
    });
  });

  describe("toRelative", () => {
    beforeEach(() => {
      Settings.now = () => new Date(2024, 5, 15, 12, 0, 0).valueOf();
    });

    afterEach(() => {
      Settings.now = () => Date.now();
    });

    test("returns relative string for past date", () => {
      const result = LuxonUtils.toRelative("2024-06-14");
      expect(result).toContain("day");
    });

    test("returns relative string for future date", () => {
      const result = LuxonUtils.toRelative("2024-06-20");
      expect(result).toContain("day");
    });
  });

  describe("TIMEZONE constant", () => {
    test("is set to America/New_York", () => {
      expect(LuxonUtils.TIMEZONE).toBe("America/New_York");
    });
  });

  describe("DateTime export", () => {
    test("exports Luxon DateTime class", () => {
      expect(LuxonUtils.DateTime).toBe(DateTime);
    });
  });
});
