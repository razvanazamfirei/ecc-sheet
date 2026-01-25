/**
 * Tests for Main Application Script
 */

import { DateTime, Settings } from "luxon";

// Mock DOM elements storage
const mockElements = {};

// Store functions that will be exported
let exportedFunctions = {};

beforeAll(async () => {
  // Set up DOM mocks
  global.document = {
    getElementById: (id) => mockElements[id] || null,
    querySelectorAll: () => [],
    querySelector: () => null,
    createElement: () => ({
      tagName: "",
      value: "",
      textContent: "",
      className: "",
      style: {},
      classList: { add: () => {}, remove: () => {} },
      addEventListener: () => {},
      remove: () => {},
      appendChild: () => {},
      insertBefore: () => {},
      querySelectorAll: () => [],
      querySelector: () => null,
    }),
    readyState: "complete",
    addEventListener: () => {},
  };

  global.window = {
    location: { href: "/" },
    print: () => {},
    LuxonUtils: {
      roundToQuarterHour: (time) => {
        if (!time) return time;
        const [hours, minutes] = time.split(":").map(Number);
        const remainder = minutes % 15;
        if (remainder === 0) return time;
        const roundedMinutes = minutes + (15 - remainder);
        if (roundedMinutes >= 60) {
          const newHours = (hours + 1) % 24;
          return `${String(newHours).padStart(2, "0")}:00`;
        }
        return `${String(hours).padStart(2, "0")}:${String(roundedMinutes).padStart(2, "0")}`;
      },
      getTodayPhilly: () => DateTime.now().setZone("America/New_York"),
      toISODate: (dt) => dt.toISODate(),
      getDaysAgo: (days) =>
        DateTime.now().setZone("America/New_York").minus({ days }),
      formatDate: (date, format) => {
        if (typeof date === "string") {
          return DateTime.fromISO(date).toFormat(format || "MMMM dd, yyyy");
        }
        return date.toFormat(format || "MMMM dd, yyyy");
      },
    },
  };

  global.luxon = { DateTime };
  global.fetch = () =>
    Promise.resolve({
      ok: true,
      json: () =>
        Promise.resolve([
          { id: 1, name: "John Doe" },
          { id: 2, name: "Jane Smith" },
        ]),
    });
  global.confirm = () => true;
  global.console = { error: () => {}, log: () => {} };
  global.setTimeout = (fn) => fn();

  // Load the module
  await import("../script.js");

  // Capture exported functions
  exportedFunctions = {
    confirmDelete: global.window.confirmDelete,
    printReport: global.window.printReport,
    getToday: global.window.getToday,
    getDateDaysAgo: global.window.getDateDaysAgo,
    goToToday: global.window.goToToday,
    formatDate: global.window.formatDate,
    updateDisplayedDate: global.window.updateDisplayedDate,
  };
});

beforeEach(() => {
  Object.keys(mockElements).forEach((key) => delete mockElements[key]);
  Settings.now = () => new Date(2024, 5, 15, 12, 0, 0).valueOf();
});

afterEach(() => {
  Settings.now = () => Date.now();
});

describe("Script Functions", () => {
  describe("confirmDelete", () => {
    test("shows default message when no message provided", () => {
      let capturedMessage = "";
      global.confirm = (msg) => {
        capturedMessage = msg;
        return true;
      };

      exportedFunctions.confirmDelete();

      expect(capturedMessage).toBe("Are you sure you want to delete this?");
    });

    test("shows custom message when provided", () => {
      let capturedMessage = "";
      global.confirm = (msg) => {
        capturedMessage = msg;
        return true;
      };

      exportedFunctions.confirmDelete("Delete this item?");

      expect(capturedMessage).toBe("Delete this item?");
    });

    test("returns user confirmation result", () => {
      global.confirm = () => true;
      expect(exportedFunctions.confirmDelete()).toBe(true);

      global.confirm = () => false;
      expect(exportedFunctions.confirmDelete()).toBe(false);
    });
  });

  describe("printReport", () => {
    test("calls window.print", () => {
      let printCalled = false;
      global.window.print = () => (printCalled = true);

      exportedFunctions.printReport();

      expect(printCalled).toBe(true);
    });
  });

  describe("goToToday", () => {
    test("navigates to root URL", () => {
      global.window.location = { href: "/some-page" };

      exportedFunctions.goToToday();

      expect(global.window.location.href).toBe("/");
    });
  });

  describe("getToday", () => {
    test("returns today in ISO format", () => {
      const result = exportedFunctions.getToday();
      expect(result).toBe("2024-06-15");
    });
  });

  describe("getDateDaysAgo", () => {
    test("returns date N days ago", () => {
      const result = exportedFunctions.getDateDaysAgo(7);
      expect(result).toBe("2024-06-08");
    });
  });

  describe("formatDate", () => {
    test("formats date using LuxonUtils", () => {
      const result = exportedFunctions.formatDate("2024-06-15");
      expect(result).toBe("June 15, 2024");
    });

    test("accepts custom format", () => {
      const result = exportedFunctions.formatDate("2024-06-15", "yyyy-MM-dd");
      expect(result).toBe("2024-06-15");
    });
  });

  describe("updateDisplayedDate", () => {
    test("updates sheet-date element when it exists", () => {
      const dateElement = { textContent: "" };
      mockElements["sheet-date"] = dateElement;

      exportedFunctions.updateDisplayedDate("2024-06-15");

      expect(dateElement.textContent).toBe("June 15, 2024");
    });

    test("does nothing when sheet-date element does not exist", () => {
      mockElements["sheet-date"] = null;

      // Should not throw
      expect(() =>
        exportedFunctions.updateDisplayedDate("2024-06-15"),
      ).not.toThrow();
    });
  });

  describe("global function exposure", () => {
    test("exposes all required functions globally", () => {
      expect(typeof exportedFunctions.confirmDelete).toBe("function");
      expect(typeof exportedFunctions.printReport).toBe("function");
      expect(typeof exportedFunctions.getToday).toBe("function");
      expect(typeof exportedFunctions.getDateDaysAgo).toBe("function");
      expect(typeof exportedFunctions.goToToday).toBe("function");
      expect(typeof exportedFunctions.formatDate).toBe("function");
      expect(typeof exportedFunctions.updateDisplayedDate).toBe("function");
    });
  });
});
