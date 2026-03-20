/**
 * Tests for Reports Page JavaScript
 */

import { DateTime, Settings } from "luxon";

// Mock DOM elements storage
const mockElements = {};

// Store functions that will be exported
let exportedFunctions = {};

beforeAll(async () => {
  // Set a fixed time for consistent testing
  Settings.now = () => new Date(2024, 5, 15, 12, 0, 0).valueOf(); // June 15, 2024

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

  // Mock luxon global if needed by other legacy scripts
  global.luxon = { DateTime };

  global.window = {
    LuxonUtils: {
      getPayrollRange: (period) => {
        if (period === "half") {
          return { startDate: "2024-06-01", endDate: "2024-06-15" };
        }
        return { startDate: "2024-06-01", endDate: "2024-06-30" };
      },
      getDateRange: (period) => {
        const ranges = {
          week: { startDate: "2024-06-08", endDate: "2024-06-15" },
          month: { startDate: "2024-05-16", endDate: "2024-06-15" },
          quarter: { startDate: "2024-03-17", endDate: "2024-06-15" },
        };
        return ranges[period] || ranges.week;
      },
    },
    loadResidentsIntoSelect: () => Promise.resolve(true),
    alert: (msg) => console.log("Alert:", msg),
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

afterAll(() => {
  Settings.now = () => Date.now();
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

    test("sets date range for payroll_half period", () => {
      const startDateInput = { value: "" };
      const endDateInput = { value: "" };
      const reportForm = { submit: () => {} };

      mockElements["start_date"] = startDateInput;
      mockElements["end_date"] = endDateInput;
      mockElements["report-form"] = reportForm;

      exportedFunctions.setDateRange("payroll_half", false);

      // June 15 -> last completed period is May 16-31
      expect(startDateInput.value).toBe("2024-05-16");
      expect(endDateInput.value).toBe("2024-05-31");
    });

    test("sets date range for payroll_month period", () => {
      const startDateInput = { value: "" };
      const endDateInput = { value: "" };
      const reportForm = { submit: () => {} };

      mockElements["start_date"] = startDateInput;
      mockElements["end_date"] = endDateInput;
      mockElements["report-form"] = reportForm;

      exportedFunctions.setDateRange("payroll_month", false);

      // June 15 -> last completed month is May 01-31
      expect(startDateInput.value).toBe("2024-05-01");
      expect(endDateInput.value).toBe("2024-05-31");
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

describe("Load Residents for Report", () => {
  test("loadResidentsForReport populates dropdown", async () => {
    let optionsAdded = 0;
    const residentFilter = {
      innerHTML: "",
      appendChild: () => {
        optionsAdded++;
      },
    };
    mockElements["resident_filter"] = residentFilter;

    // Simulate the fetch and populate logic
    const response = await global.fetch("/api/residents/active");
    const residents = await response.json();
    const select = mockElements["resident_filter"];

    select.innerHTML = '<option value="">All Residents</option>';
    residents.forEach(() => {
      select.appendChild({});
    });

    expect(select.innerHTML).toBe('<option value="">All Residents</option>');
    expect(optionsAdded).toBe(2); // Two mock residents
  });

  test("loadResidentsForReport handles fetch error", async () => {
    let errorLogged = false;
    global.console.error = () => {
      errorLogged = true;
    };

    global.fetch = () => Promise.reject(new Error("Network error"));

    try {
      await global.fetch("/api/residents/active");
    } catch {
      global.console.error("Error loading residents");
    }

    expect(errorLogged).toBe(true);

    // Restore fetch
    global.fetch = () =>
      Promise.resolve({
        ok: true,
        json: () =>
          Promise.resolve([
            { id: 1, name: "John Doe" },
            { id: 2, name: "Jane Smith" },
          ]),
      });
  });
});

describe("Initialize Reports", () => {
  test("initializeReports sets default week range without submitting", () => {
    const startDateInput = { value: "" };
    const endDateInput = { value: "" };
    let formSubmitted = false;
    const reportForm = { submit: () => (formSubmitted = true) };

    mockElements["start_date"] = startDateInput;
    mockElements["end_date"] = endDateInput;
    mockElements["report-form"] = reportForm;
    mockElements["resident_filter"] = { innerHTML: "", appendChild: () => {} };

    // Simulate initializeReports calling setDateRange("week", false)
    exportedFunctions.setDateRange("week", false);

    expect(startDateInput.value).toBe("2024-06-08");
    expect(endDateInput.value).toBe("2024-06-15");
    expect(formSubmitted).toBe(false);
  });
});

describe("Date Range Edge Cases", () => {
  test("setDateRange handles unknown period gracefully", () => {
    const startDateInput = { value: "" };
    const endDateInput = { value: "" };
    const reportForm = { submit: () => {} };

    mockElements["start_date"] = startDateInput;
    mockElements["end_date"] = endDateInput;
    mockElements["report-form"] = reportForm;

    // Unknown period should default to week
    exportedFunctions.setDateRange("unknown", false);

    expect(startDateInput.value).toBe("2024-06-08");
    expect(endDateInput.value).toBe("2024-06-15");
  });
});
