/**
 * Tests for Reports Page JavaScript
 */

// Mock DOM elements storage
const mockElements = {};

// Store functions that will be exported
let exportedFunctions = {};

beforeAll(async () => {
  // Pre-populate mock elements needed during module initialization
  mockElements["start_date"] = { value: "" };
  mockElements["end_date"] = { value: "" };
  mockElements["report-form"] = { submit: () => {} };
  mockElements["resident_filter"] = { innerHTML: "", appendChild: () => {} };

  // Set up mock elements storage
  global.document = {
    getElementById: (id) => mockElements[id] || null,
    readyState: "complete",
    addEventListener: () => {},
  };

  global.window = {
    LuxonUtils: {
      getDateRange: (period) => {
        const ranges = {
          week: { startDate: "2024-06-08", endDate: "2024-06-15" },
          month: { startDate: "2024-05-16", endDate: "2024-06-15" },
          quarter: { startDate: "2024-03-17", endDate: "2024-06-15" },
        };
        return ranges[period] || ranges.week;
      },
    },
  };

  global.fetch = () =>
    Promise.resolve({
      ok: true,
      json: () =>
        Promise.resolve([
          { id: 1, name: "John Doe" },
          { id: 2, name: "Jane Smith" },
        ]),
    });

  global.console = { error: () => {}, log: () => {} };

  // Load the module
  await import("../reports.js");

  // Capture exported functions
  exportedFunctions = {
    setDateRange: global.window.setDateRange,
  };
});

beforeEach(() => {
  Object.keys(mockElements).forEach((key) => delete mockElements[key]);
});

describe("Reports Functions", () => {
  describe("setDateRange", () => {
    test("sets date range for week period", () => {
      const startDateInput = { value: "" };
      const endDateInput = { value: "" };
      let formSubmitted = false;
      const reportForm = { submit: () => (formSubmitted = true) };

      mockElements["start_date"] = startDateInput;
      mockElements["end_date"] = endDateInput;
      mockElements["report-form"] = reportForm;

      exportedFunctions.setDateRange("week", false);

      expect(startDateInput.value).toBe("2024-06-08");
      expect(endDateInput.value).toBe("2024-06-15");
      expect(formSubmitted).toBe(false);
    });

    test("sets date range for month period", () => {
      const startDateInput = { value: "" };
      const endDateInput = { value: "" };
      const reportForm = { submit: () => {} };

      mockElements["start_date"] = startDateInput;
      mockElements["end_date"] = endDateInput;
      mockElements["report-form"] = reportForm;

      exportedFunctions.setDateRange("month", false);

      expect(startDateInput.value).toBe("2024-05-16");
      expect(endDateInput.value).toBe("2024-06-15");
    });

    test("sets date range for quarter period", () => {
      const startDateInput = { value: "" };
      const endDateInput = { value: "" };
      const reportForm = { submit: () => {} };

      mockElements["start_date"] = startDateInput;
      mockElements["end_date"] = endDateInput;
      mockElements["report-form"] = reportForm;

      exportedFunctions.setDateRange("quarter", false);

      expect(startDateInput.value).toBe("2024-03-17");
      expect(endDateInput.value).toBe("2024-06-15");
    });

    test("auto-submits form when autoSubmit is true (default)", () => {
      const startDateInput = { value: "" };
      const endDateInput = { value: "" };
      let formSubmitted = false;
      const reportForm = { submit: () => (formSubmitted = true) };

      mockElements["start_date"] = startDateInput;
      mockElements["end_date"] = endDateInput;
      mockElements["report-form"] = reportForm;

      exportedFunctions.setDateRange("week");

      expect(formSubmitted).toBe(true);
    });

    test("does not auto-submit when autoSubmit is false", () => {
      const startDateInput = { value: "" };
      const endDateInput = { value: "" };
      let formSubmitted = false;
      const reportForm = { submit: () => (formSubmitted = true) };

      mockElements["start_date"] = startDateInput;
      mockElements["end_date"] = endDateInput;
      mockElements["report-form"] = reportForm;

      exportedFunctions.setDateRange("week", false);

      expect(formSubmitted).toBe(false);
    });
  });

  describe("global function exposure", () => {
    test("exposes setDateRange globally", () => {
      expect(typeof exportedFunctions.setDateRange).toBe("function");
    });
  });
});
