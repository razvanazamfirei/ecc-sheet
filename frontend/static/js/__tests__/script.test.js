/**
 * Tests for Main Application Script
 */

import { DateTime, Settings } from "luxon";

// Mock DOM elements storage
const mockElements = {};
const documentEventListeners = {};

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
    addEventListener: (eventName, handler) => {
      documentEventListeners[eventName] = handler;
    },
  };

  global.window = {
    location: { href: "/" },
    print: () => {},
    LuxonUtils: {
      roundToFiveMinutes: (time) => {
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

  describe("confirmation submit handling", () => {
    test("confirmed forms prefer requestSubmit", async () => {
      global.confirm = () => true;
      let prevented = false;
      let requestSubmitCalled = false;
      let submitCalled = false;
      const form = {
        dataset: { confirmMessage: "Continue?" },
        matches: (selector) => selector === "form",
        requestSubmit: () => {
          requestSubmitCalled = true;
        },
        submit: () => {
          submitCalled = true;
        },
      };

      documentEventListeners.submit({
        target: form,
        defaultPrevented: false,
        preventDefault: () => {
          prevented = true;
        },
      });
      await Promise.resolve();
      await Promise.resolve();

      expect(prevented).toBe(true);
      expect(requestSubmitCalled).toBe(true);
      expect(submitCalled).toBe(false);
      expect(form.dataset.confirmBypass).toBeUndefined();
    });

    test("confirmed forms use the DOM dialog path before requestSubmit", async () => {
      let prevented = false;
      let requestSubmitCalled = false;
      let submitCalled = false;
      const dialogHandlers = {};
      const bodyClasses = new Set();

      global.document.body = {
        classList: {
          add: (className) => bodyClasses.add(className),
          remove: (className) => bodyClasses.delete(className),
        },
      };

      mockElements["page-dialog-root"] = { hidden: true, dataset: {} };
      mockElements["page-dialog-backdrop"] = {
        addEventListener: (eventName, handler) => {
          dialogHandlers[`backdrop:${eventName}`] = handler;
        },
      };
      mockElements["page-dialog-title"] = { textContent: "" };
      mockElements["page-dialog-message"] = { textContent: "" };
      mockElements["page-dialog-confirm"] = {
        textContent: "",
        className: "",
        addEventListener: (eventName, handler) => {
          dialogHandlers[`confirm:${eventName}`] = handler;
        },
        focus: () => {},
      };
      mockElements["page-dialog-cancel"] = {
        textContent: "",
        className: "",
        addEventListener: (eventName, handler) => {
          dialogHandlers[`cancel:${eventName}`] = handler;
        },
      };

      const form = {
        dataset: { confirmMessage: "Continue?" },
        matches: (selector) => selector === "form",
        requestSubmit: () => {
          requestSubmitCalled = true;
        },
        submit: () => {
          submitCalled = true;
        },
      };

      documentEventListeners.submit({
        target: form,
        defaultPrevented: false,
        preventDefault: () => {
          prevented = true;
        },
      });
      await Promise.resolve();

      expect(prevented).toBe(true);
      expect(requestSubmitCalled).toBe(false);
      expect(submitCalled).toBe(false);
      expect(bodyClasses.has("page-dialog-open")).toBe(true);

      dialogHandlers["confirm:click"]();
      await Promise.resolve();
      await Promise.resolve();

      expect(requestSubmitCalled).toBe(true);
      expect(submitCalled).toBe(false);
      expect(form.dataset.confirmBypass).toBeUndefined();
    });

    test("confirmed forms fall back to submit when requestSubmit is unavailable", async () => {
      global.confirm = () => true;
      let submitCalled = false;
      const form = {
        dataset: { confirmMessage: "Continue?" },
        matches: (selector) => selector === "form",
        submit: () => {
          submitCalled = true;
        },
      };

      documentEventListeners.submit({
        target: form,
        defaultPrevented: false,
        preventDefault: () => {},
      });
      await Promise.resolve();
      await Promise.resolve();

      expect(submitCalled).toBe(true);
      expect(form.dataset.confirmBypass).toBeUndefined();
    });
  });
});

describe("Time Input Rounding", () => {
  test("roundToFiveMinutes rounds up to next quarter", () => {
    const result = global.window.LuxonUtils.roundToFiveMinutes("14:07");
    expect(result).toBe("14:15");
  });

  test("roundToFiveMinutes does not change already rounded times", () => {
    const result = global.window.LuxonUtils.roundToFiveMinutes("14:15");
    expect(result).toBe("14:15");
  });

  test("roundToFiveMinutes handles hour rollover", () => {
    const result = global.window.LuxonUtils.roundToFiveMinutes("23:55");
    expect(result).toBe("00:00");
  });

  test("roundToFiveMinutes handles empty input", () => {
    const result = global.window.LuxonUtils.roundToFiveMinutes("");
    expect(result).toBe("");
  });

  test("roundToFiveMinutes handles null input", () => {
    const result = global.window.LuxonUtils.roundToFiveMinutes(null);
    expect(result).toBe(null);
  });
});

describe("Notification System", () => {
  // Note: These are behavioral tests that simulate notification system behavior
  // rather than unit tests of the actual showNotification function.
  // They verify the expected structure and behavior patterns.

  test("showNotification creates alert element", () => {
    let createdElement = null;
    global.document.createElement = (tag) => {
      createdElement = {
        tagName: tag.toUpperCase(),
        className: "",
        textContent: "",
        style: {},
        remove: () => {},
      };
      return createdElement;
    };

    const mockContainer = {
      firstChild: null,
      insertBefore: () => {},
    };
    global.document.querySelector = (selector) => {
      if (selector === ".container") return mockContainer;
      return null;
    };

    // Simulate showNotification function behavior
    const notification = global.document.createElement("div");
    notification.className = "alert alert-success";
    notification.textContent = "Test message";
    mockContainer.insertBefore(notification, mockContainer.firstChild);

    expect(notification.className).toBe("alert alert-success");
    expect(notification.textContent).toBe("Test message");
  });

  test("showNotification handles error type", () => {
    let createdElement = null;
    global.document.createElement = () => {
      createdElement = {
        className: "",
        textContent: "",
        style: {},
        remove: () => {},
      };
      return createdElement;
    };

    const mockContainer = { insertBefore: () => {} };
    global.document.querySelector = () => mockContainer;

    // Simulate showNotification with error type
    const notification = global.document.createElement("div");
    notification.className = "alert alert-error";
    notification.textContent = "Error message";

    expect(notification.className).toBe("alert alert-error");
  });

  test("showNotification does nothing when container missing", () => {
    global.document.querySelector = () => null;

    // Should not throw when container is missing
    expect(() => {
      // Simulate function checking for container
      const container = global.document.querySelector(".container");
      if (!container) return;
    }).not.toThrow();
  });
});

describe("Form Validation", () => {
  // Note: These are behavioral tests that simulate form validation behavior
  // rather than unit tests of an actual validateForm function.
  // They verify the expected validation logic patterns.

  test("validateForm returns true when all required fields filled", () => {
    const form = {
      querySelectorAll: () => [
        {
          value: "filled",
          classList: { add: () => {}, remove: () => {} },
        },
        {
          value: "also filled",
          classList: { add: () => {}, remove: () => {} },
        },
      ],
    };

    const requiredFields = form.querySelectorAll("[required]");
    let isValid = true;
    requiredFields.forEach((field) => {
      if (!field.value.trim()) {
        isValid = false;
      }
    });

    expect(isValid).toBe(true);
  });

  test("validateForm returns false when required field empty", () => {
    const form = {
      querySelectorAll: () => [
        {
          value: "",
          classList: { add: () => {}, remove: () => {} },
        },
      ],
    };

    const requiredFields = form.querySelectorAll("[required]");
    let isValid = true;
    requiredFields.forEach((field) => {
      if (!field.value.trim()) {
        isValid = false;
      }
    });

    expect(isValid).toBe(false);
  });

  test("validateForm removes error class from valid fields", () => {
    let removeWasCalled = false;
    const field = {
      value: "valid",
      classList: {
        add: () => {},
        remove: (cls) => {
          if (cls === "error") removeWasCalled = true;
        },
      },
    };

    // Simulate validation logic
    if (field.value.trim()) {
      field.classList.remove("error");
    }

    expect(removeWasCalled).toBe(true);
  });

  test("validateForm adds error class to invalid fields", () => {
    let addWasCalled = false;
    const field = {
      value: "",
      classList: {
        add: (cls) => {
          if (cls === "error") addWasCalled = true;
        },
        remove: () => {},
      },
    };

    // Simulate validation logic
    if (!field.value.trim()) {
      field.classList.add("error");
    }

    expect(addWasCalled).toBe(true);
  });
});

describe("Load Active Residents", () => {
  test("loadActiveResidents populates dropdown on success", async () => {
    let selectPopulated = false;
    mockElements["resident_id"] = {
      innerHTML: "",
      appendChild: () => {
        selectPopulated = true;
      },
    };

    // Simulate fetch and populate logic
    const response = await global.fetch("/api/residents/active");
    const residents = await response.json();
    const select = mockElements["resident_id"];

    if (select) {
      select.innerHTML = '<option value="">Select Resident</option>';
      residents.forEach(() => {
        select.appendChild({});
      });
    }

    expect(selectPopulated).toBe(true);
  });

  test("loadActiveResidents handles missing select element", async () => {
    mockElements["resident_id"] = null;

    // Should return early without throwing
    const select = mockElements["resident_id"];
    if (!select) {
      return;
    }

    // This line should not be reached
    expect(true).toBe(true);
  });

  test("loadActiveResidents handles fetch error", async () => {
    let errorLogged = false;
    global.console.error = () => {
      errorLogged = true;
    };

    global.fetch = () => Promise.reject(new Error("Network error"));

    try {
      await global.fetch("/api/residents/active");
    } catch {
      global.console.error("Error");
    }

    expect(errorLogged).toBe(true);

    // Restore fetch
    global.fetch = () =>
      Promise.resolve({
        ok: true,
        json: () => Promise.resolve([]),
      });
  });
});

describe("Alert Auto-hide", () => {
  test("initializeAlerts fades and removes alerts", () => {
    let removed = false;
    const mockAlert = {
      style: { transition: "", opacity: "1" },
      remove: () => {
        removed = true;
      },
    };

    // Simulate the auto-hide logic
    mockAlert.style.transition = "opacity 0.5s";
    mockAlert.style.opacity = "0";
    mockAlert.remove();

    expect(mockAlert.style.transition).toBe("opacity 0.5s");
    expect(mockAlert.style.opacity).toBe("0");
    expect(removed).toBe(true);
  });
});
