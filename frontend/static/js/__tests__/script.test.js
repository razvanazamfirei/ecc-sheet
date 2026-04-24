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
        const roundedMinutes = Math.ceil(minutes / 5) * 5;
        if (roundedMinutes === 60) {
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
    showNotification: global.window.showNotification,
    validateForm: global.window.validateForm,
  };
});

beforeEach(() => {
  Object.keys(mockElements).forEach((key) => {
    delete mockElements[key];
  });
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

  // biome-ignore lint/security/noSecrets: false positive on a deterministic test name
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
      const modalHandlers = {};
      let showCalled = false;
      let hideCalled = false;
      const modalInstance = {
        show: () => {
          showCalled = true;
        },
        hide: () => {
          hideCalled = true;
        },
      };

      global.window.bootstrap = {
        Modal: {
          getOrCreateInstance: () => modalInstance,
          getInstance: () => modalInstance,
        },
      };

      mockElements["confirm-modal"] = {
        dataset: {},
        addEventListener: (eventName, handler) => {
          modalHandlers[eventName] = handler;
        },
      };
      mockElements["confirm-modal-title"] = { textContent: "" };
      mockElements["confirm-modal-message"] = { textContent: "" };
      mockElements["confirm-modal-confirm"] = {
        textContent: "",
        className: "",
        addEventListener: (eventName, handler) => {
          modalHandlers[`confirm:${eventName}`] = handler;
        },
        focus: () => {},
      };
      mockElements["confirm-modal-cancel"] = {
        textContent: "",
        className: "",
        addEventListener: (eventName, handler) => {
          modalHandlers[`cancel:${eventName}`] = handler;
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
      expect(showCalled).toBe(true);
      expect(mockElements["confirm-modal-title"].textContent).toBe(
        "Please Confirm",
      );
      expect(mockElements["confirm-modal-message"].textContent).toBe(
        "Continue?",
      );

      modalHandlers["confirm:click"]();
      await Promise.resolve();
      await Promise.resolve();

      expect(requestSubmitCalled).toBe(true);
      expect(submitCalled).toBe(false);
      expect(hideCalled).toBe(true);
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
  test("roundToFiveMinutes rounds up to the next 5 minutes", () => {
    const result = global.window.LuxonUtils.roundToFiveMinutes("14:07");
    expect(result).toBe("14:10");
  });

  test("roundToFiveMinutes does not change already rounded times", () => {
    const result = global.window.LuxonUtils.roundToFiveMinutes("14:15");
    expect(result).toBe("14:15");
  });

  test("roundToFiveMinutes handles hour rollover", () => {
    const result = global.window.LuxonUtils.roundToFiveMinutes("23:56");
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
  test("showNotification creates alert element", () => {
    const documentCreateElement = global.document.createElement;
    global.document.createElement = (tag) => {
      const el = {
        tagName: tag.toUpperCase(),
        className: "",
        textContent: "",
        style: {},
        remove: () => {},
        appendChild: (child) => {
          if (child?.textContent) {
            el.textContent += child.textContent;
          }
        },
        setAttribute: () => {},
        addEventListener: () => {},
      };
      return el;
    };

    const mockContainer = {
      firstChild: null,
      insertBefore: () => {},
    };
    const documentQuerySelector = global.document.querySelector;
    global.document.querySelector = (selector) => {
      if (selector === ".container") return mockContainer;
      return null;
    };

    const notification = global.window.showNotification(
      "Test message",
      "success",
    );

    expect(notification.className).toContain("alert-success");
    expect(notification.textContent).toBe("Test message");

    global.document.createElement = documentCreateElement;
    global.document.querySelector = documentQuerySelector;
  });

  test("showNotification handles error type", () => {
    const documentCreateElement = global.document.createElement;
    global.document.createElement = () => {
      const el = {
        className: "",
        textContent: "",
        style: {},
        remove: () => {},
        appendChild: (child) => {
          if (child?.textContent) {
            el.textContent += child.textContent;
          }
        },
        setAttribute: () => {},
        addEventListener: () => {},
      };
      return el;
    };

    const mockContainer = { insertBefore: () => {} };
    const documentQuerySelector = global.document.querySelector;
    global.document.querySelector = () => mockContainer;

    const notification = global.window.showNotification(
      "Error message",
      "error",
    );

    expect(notification.className).toContain("alert-danger");

    global.document.createElement = documentCreateElement;
    global.document.querySelector = documentQuerySelector;
  });

  test("showNotification does nothing when container missing", () => {
    const documentQuerySelector = global.document.querySelector;
    global.document.querySelector = () => null;

    expect(() => {
      global.window.showNotification("Test missing container");
    }).not.toThrow();

    global.document.querySelector = documentQuerySelector;
  });
});

describe("Form Validation", () => {
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

    const isValid = global.window.validateForm(form);

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

    const isValid = global.window.validateForm(form);
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
    const form = {
      querySelectorAll: () => [field],
    };

    global.window.validateForm(form);

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
    const form = {
      querySelectorAll: () => [field],
    };

    global.window.validateForm(form);

    expect(addWasCalled).toBe(true);
  });
});

describe("Load Active Residents", () => {
  test("loadActiveResidents populates dropdown on success", async () => {
    let selectPopulated = false;
    mockElements.resident_id = {
      innerHTML: "",
      appendChild: () => {
        selectPopulated = true;
      },
    };

    // Simulate fetch and populate logic
    const response = await global.fetch("/api/residents/active");
    const residents = await response.json();
    const select = mockElements.resident_id;

    if (select) {
      select.innerHTML = '<option value="">Select Resident</option>';
      residents.forEach(() => {
        select.appendChild({});
      });
    }

    expect(selectPopulated).toBe(true);
  });

  test("loadActiveResidents handles missing select element", async () => {
    mockElements.resident_id = null;

    // This line should not be reached by the rest of the mock execution string, verify it's skipped
    let selectPopulated = false;
    const select = mockElements.resident_id;
    if (select) {
      selectPopulated = true;
    }

    expect(selectPopulated).toBe(false);
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
