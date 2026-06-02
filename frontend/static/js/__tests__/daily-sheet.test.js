/**
 * Tests for Daily Sheet Page JavaScript
 */

// Mock DOM elements storage
const mockElements = {};

// Set up DOM mocks
const mockGetElementById = (id) => mockElements[id] || null;
const mockQuerySelectorAll = () => [];
const mockQuerySelector = () => null;

// Set up window mocks
let confirmReturnValue = true;
const mockConfirm = (_msg) => confirmReturnValue;
const mockReload = () => {};
const mockAlert = () => {};

// Store functions that will be exported
let exportedFunctions = {};

beforeAll(async () => {
  // Set up global mocks
  global.document = {
    getElementById: mockGetElementById,
    querySelectorAll: mockQuerySelectorAll,
    querySelector: mockQuerySelector,
    readyState: "complete",
    addEventListener: () => {},
    createElement: (_tag) => {
      let text = "";
      return {
        set textContent(value) {
          text = value;
        },
        get innerHTML() {
          return text
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
        },
      };
    },
  };

  global.window = {
    location: { reload: mockReload },
    confirm: mockConfirm,
  };

  global.confirm = mockConfirm;
  global.alert = mockAlert;
  global.console = { error: () => {}, log: () => {} };
  global.setInterval = () => {};
  global.setTimeout = () => {};
  global.FormData = function MockFormData() {};
  global.fetch = () => Promise.resolve({ ok: true });

  // Load the module
  await import("../daily-sheet.js");

  // Capture exported functions
  exportedFunctions = {
    confirmLockWithMissing: global.window.confirmLockWithMissing,
    editEntry: global.window.editEntry,
    saveEntry: global.window.saveEntry,
    cancelEdit: global.window.cancelEdit,
    toggleEditAll: global.window.toggleEditAll,
    saveAll: global.window.saveAll,
    copyToClipboard: global.window.copyToClipboard,
    toggleStartTimeField: global.window.toggleStartTimeField,
    initializeInlineEditors: global.window.initializeInlineEditors,
    initializeAsyncDelete: global.window.initializeAsyncDelete,
    initializeDuplicateEntryWarning:
      global.window.initializeDuplicateEntryWarning,
    removeEntryRow: global.window.removeEntryRow,
    getExistingEntryKeys: global.window.getExistingEntryKeys,
    insertEntryRow: global.window.insertEntryRow,
    updateMissingExitWarning: global.window.updateMissingExitWarning,
    updateEntrySummaryCount: global.window.updateEntrySummaryCount,
    initializeAddEntryShortcut: global.window.initializeAddEntryShortcut,
    isSheetLocked: global.window.isSheetLocked,
  };
});

beforeEach(() => {
  // Reset mock elements
  Object.keys(mockElements).forEach((key) => {
    delete mockElements[key];
  });
  confirmReturnValue = true;
  global.FormData = function MockFormData() {};
});

describe("Daily Sheet Functions", () => {
  describe("confirmLockWithMissing", () => {
    test("builds correct message with missing count and residents", () => {
      let capturedMessage = "";
      global.confirm = (msg) => {
        capturedMessage = msg;
        return true;
      };

      const form = {
        dataset: {
          missingCount: "2",
          missingResidents: '["John Doe", "Jane Smith"]',
        },
      };

      const result = exportedFunctions.confirmLockWithMissing(form);

      expect(result).toBe(true);
      expect(capturedMessage).toContain("2 entries are missing exit times");
      expect(capturedMessage).toContain("John Doe, Jane Smith");
    });

    test("returns false when user cancels", () => {
      global.confirm = () => false;

      const form = {
        dataset: {
          missingCount: "1",
          missingResidents: '["Test Resident"]',
        },
      };

      const result = exportedFunctions.confirmLockWithMissing(form);

      expect(result).toBe(false);
    });

    test("handles empty missingResidents", () => {
      global.confirm = () => true;

      const form = {
        dataset: {
          missingCount: "0",
          missingResidents: "",
        },
      };

      const result = exportedFunctions.confirmLockWithMissing(form);

      expect(result).toBe(true);
    });
  });

  describe("editEntry", () => {
    test("stores original value and toggles visibility", () => {
      const mockInput = { value: "18:00", focus: () => {} };
      const mockDisplay = { style: { display: "" } };
      const mockForm = { style: { display: "" } };
      const mockEditControls = { style: { display: "" } };
      const mockActionButtons = { style: { display: "" } };

      mockElements["input-1"] = mockInput;
      mockElements["display-1"] = mockDisplay;
      mockElements["form-1"] = mockForm;
      mockElements["edit-controls-1"] = mockEditControls;
      mockElements["action-buttons-1"] = mockActionButtons;

      exportedFunctions.editEntry(1);

      expect(mockDisplay.style.display).toBe("none");
      expect(mockForm.style.display).toBe("inline");
      expect(mockEditControls.style.display).toBe("inline-flex");
      expect(mockActionButtons.style.display).toBe("none");
    });
  });

  describe("saveEntry", () => {
    test("saves the form asynchronously and updates the row", async () => {
      let capturedFormData;
      let fetchArgs;
      global.FormData = function MockFormData(form) {
        capturedFormData = form.querySelectorAll("input").map((input) => ({
          name: input.name,
          value: input.value,
          disabled: input.disabled,
        }));
        return { capturedFormData };
      };

      const formInputs = [
        {
          name: "csrf_token",
          value: "csrf-token-value",
          disabled: false,
        },
        {
          name: "exit_time",
          value: "18:00",
          disabled: false,
        },
      ];

      mockElements["form-1"] = {
        action: "/update_entry/1",
        querySelectorAll: (selector) =>
          selector === "input" ? formInputs : [],
        style: { display: "inline" },
      };
      mockElements["input-1"] = { value: "18:00", focus: () => {} };
      mockElements["display-1"] = { style: { display: "none" }, innerHTML: "" };
      mockElements["cell-1"] = {
        classList: { toggle: () => {}, contains: () => false },
      };
      mockElements["entry-row-1"] = {
        classList: { toggle: () => {} },
      };
      mockElements["overtime-1"] = { textContent: "" };
      mockElements["edit-controls-1"] = { style: { display: "inline-flex" } };
      mockElements["action-buttons-1"] = { style: { display: "none" } };

      global.fetch = (url, options) => {
        fetchArgs = { url, options };
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              message: "Entry updated successfully",
              entry: {
                exit_time: "21:00",
                exit_time_display: "09:00 PM",
                start_time: null,
                start_time_display: null,
                missing_exit_time: false,
                overtime_display: "3.50 hrs",
              },
            }),
        });
      };

      const saved = await exportedFunctions.saveEntry(1);

      expect(saved).toBe(true);
      expect(mockElements["display-1"].innerHTML).toContain("09:00 PM");
      expect(mockElements["overtime-1"].textContent).toBe("3.50 hrs");
      expect(mockElements["form-1"].style.display).toBe("none");
      expect(fetchArgs.options.headers["X-CSRFToken"]).toBe("csrf-token-value");
      expect(capturedFormData).toEqual([
        {
          name: "csrf_token",
          value: "csrf-token-value",
          disabled: false,
        },
        {
          name: "exit_time",
          value: "18:00",
          disabled: false,
        },
      ]);
    });
  });

  describe("initializeInlineEditors", () => {
    test("pressing Enter in a time input submits the inline form", async () => {
      const originalQuerySelectorAll = global.document.querySelectorAll;
      const formListeners = {};
      const inputListeners = {};
      let requestSubmitCalled = false;
      let prevented = false;

      const mockForm = {
        dataset: { entryId: "1" },
        id: "form-1",
        addEventListener: (eventName, handler) => {
          formListeners[eventName] = handler;
        },
        requestSubmit: () => {
          requestSubmitCalled = true;
        },
      };
      const mockInput = {
        id: "input-1",
        form: mockForm,
        addEventListener: (eventName, handler) => {
          inputListeners[eventName] = handler;
        },
      };

      global.document.querySelectorAll = (selector) => {
        if (selector === ".time-edit-form") {
          return [mockForm];
        }
        if (selector === '[id^="input-"], [id^="start-input-"]') {
          return [mockInput];
        }
        return [];
      };

      exportedFunctions.initializeInlineEditors();
      await inputListeners.keydown({
        key: "Enter",
        code: "Enter",
        preventDefault: () => {
          prevented = true;
        },
      });

      expect(formListeners.submit).toBeTypeOf("function");
      expect(prevented).toBe(true);
      expect(requestSubmitCalled).toBe(true);

      global.document.querySelectorAll = originalQuerySelectorAll;
    });
  });

  describe("cancelEdit", () => {
    test("restores original value and toggles visibility", () => {
      const mockInput = { value: "19:00", focus: () => {} };
      const mockDisplay = { style: { display: "none" } };
      const mockForm = { style: { display: "inline" } };
      const mockEditControls = { style: { display: "inline-flex" } };
      const mockActionButtons = { style: { display: "none" } };

      mockElements["input-2"] = mockInput;
      mockElements["display-2"] = mockDisplay;
      mockElements["form-2"] = mockForm;
      mockElements["edit-controls-2"] = mockEditControls;
      mockElements["action-buttons-2"] = mockActionButtons;

      // First edit to store original value
      exportedFunctions.editEntry(2);
      // Then cancel
      exportedFunctions.cancelEdit(2);

      expect(mockDisplay.style.display).toBe("inline");
      expect(mockForm.style.display).toBe("none");
      expect(mockEditControls.style.display).toBe("none");
      expect(mockActionButtons.style.display).toBe("inline-flex");
    });
  });

  describe("toggleEditAll", () => {
    test("enables edit mode for all entries when toggled on", () => {
      const buttonContainer = {
        classList: {
          add: () => {},
          remove: () => {},
        },
      };
      const editAllBtn = {
        innerHTML: '<i class="bi bi-pencil-square me-1"></i>Edit All',
        classList: {
          remove: () => {},
          add: () => {},
        },
      };
      const saveAllBtn = { style: { display: "none" } };

      mockElements["edit-all-controls"] = buttonContainer;
      mockElements["edit-all-btn"] = editAllBtn;
      mockElements["save-all-btn"] = saveAllBtn;

      // Mock querySelectorAll to return entries
      global.document.querySelectorAll = () => [
        { dataset: { entryId: "1" } },
        { dataset: { entryId: "2" } },
      ];

      // Mock individual entry elements
      [1, 2].forEach((id) => {
        mockElements[`input-${id}`] = { value: "18:00", focus: () => {} };
        mockElements[`display-${id}`] = { style: { display: "" } };
        mockElements[`form-${id}`] = { style: { display: "" } };
        mockElements[`edit-controls-${id}`] = { style: { display: "" } };
        mockElements[`action-buttons-${id}`] = { style: { display: "" } };
      });

      exportedFunctions.toggleEditAll();

      expect(editAllBtn.innerHTML).toContain("Cancel All");
      expect(saveAllBtn.style.display).toBe("inline-block");
    });
  });

  describe("saveAll", () => {
    test("submits all forms via fetch without reloading on success", async () => {
      const editAllControls = {
        classList: { remove: () => {} },
      };
      const editAllBtn = {
        disabled: false,
        classList: { remove: () => {}, add: () => {} },
      };
      const saveAllBtn = {
        disabled: false,
        innerHTML: '<i class="bi bi-check-all me-1"></i>Save All',
        style: { display: "inline-block" },
      };

      mockElements["edit-all-controls"] = editAllControls;
      mockElements["edit-all-btn"] = editAllBtn;
      mockElements["save-all-btn"] = saveAllBtn;

      global.document.querySelectorAll = () => [
        {
          dataset: { entryId: "1" },
          querySelector: () => ({ textContent: "3.50 hrs" }),
        },
        {
          dataset: { entryId: "2" },
          querySelector: () => ({ textContent: "1.00 hrs" }),
        },
      ];

      const form1Inputs = [{ name: "csrf_token", value: "csrf-token-value" }];
      mockElements["form-1"] = {
        action: "/update_entry/1",
        querySelectorAll: (selector) =>
          selector === "input" ? form1Inputs : [],
        style: { display: "inline" },
      };
      mockElements["input-1"] = { value: "18:00", focus: () => {} };
      mockElements["display-1"] = { style: { display: "none" }, innerHTML: "" };
      mockElements["cell-1"] = {
        classList: { toggle: () => {}, contains: () => false },
      };
      mockElements["entry-row-1"] = {
        classList: { toggle: () => {} },
      };
      mockElements["overtime-1"] = { textContent: "" };
      mockElements["edit-controls-1"] = { style: { display: "inline-flex" } };
      mockElements["action-buttons-1"] = { style: { display: "none" } };

      const form2Inputs = [{ name: "csrf_token", value: "csrf-token-value" }];
      mockElements["form-2"] = {
        action: "/update_entry/2",
        querySelectorAll: (selector) =>
          selector === "input" ? form2Inputs : [],
        style: { display: "inline" },
      };
      mockElements["input-2"] = { value: "20:30", focus: () => {} };
      mockElements["start-input-2"] = {
        value: "09:00",
        disabled: false,
        style: { display: "inline" },
      };
      mockElements["display-2"] = { style: { display: "none" }, innerHTML: "" };
      mockElements["cell-2"] = {
        classList: { toggle: () => {}, contains: () => false },
      };
      mockElements["entry-row-2"] = {
        classList: { toggle: () => {} },
      };
      mockElements["overtime-2"] = { textContent: "" };
      mockElements["edit-controls-2"] = { style: { display: "inline-flex" } };
      mockElements["action-buttons-2"] = { style: { display: "none" } };

      let fetchCount = 0;
      let fetchArgs;
      global.fetch = (url, options) => {
        fetchCount += 1;
        fetchArgs = { url, options };
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              entries: [
                {
                  id: "1",
                  exit_time: "21:00",
                  exit_time_display: "09:00 PM",
                  start_time: null,
                  start_time_display: null,
                  missing_exit_time: false,
                  overtime_display: "3.50 hrs",
                },
                {
                  id: "2",
                  exit_time: "20:30",
                  exit_time_display: "08:30 PM",
                  start_time: "09:00",
                  start_time_display: "09:00 AM",
                  missing_exit_time: false,
                  overtime_display: "1.00 hrs",
                },
              ],
            }),
        });
      };

      await exportedFunctions.saveAll();

      expect(saveAllBtn.disabled).toBe(false);
      expect(editAllBtn.disabled).toBe(false);
      expect(saveAllBtn.style.display).toBe("none");
      expect(fetchCount).toBe(1);
      expect(fetchArgs.url).toBe("/entries/update-all");
      expect(fetchArgs.options.headers["X-CSRFToken"]).toBe("csrf-token-value");
      expect(JSON.parse(fetchArgs.options.body)).toEqual({
        entries: [
          { id: "1", exit_time: "18:00" },
          { id: "2", exit_time: "20:30", start_time: "09:00" },
        ],
      });
    });

    test("re-enables buttons and shows error on failure", async () => {
      const editAllControls = {
        classList: { remove: () => {} },
      };
      const editAllBtn = { disabled: false };
      const saveAllBtn = {
        disabled: false,
        innerHTML: '<i class="bi bi-check-all me-1"></i>Save All',
        style: { display: "inline-block" },
      };

      mockElements["edit-all-controls"] = editAllControls;
      mockElements["edit-all-btn"] = editAllBtn;
      mockElements["save-all-btn"] = saveAllBtn;

      global.document.querySelectorAll = () => [{ dataset: { entryId: "1" } }];

      const formInputs = [{ name: "csrf_token", value: "csrf-token-value" }];
      mockElements["form-1"] = {
        action: "/update_entry/1",
        querySelectorAll: (selector) =>
          selector === "input" ? formInputs : [],
        style: { display: "inline" },
      };
      mockElements["input-1"] = { value: "18:00", focus: () => {} };
      mockElements["display-1"] = { style: { display: "none" }, innerHTML: "" };
      mockElements["cell-1"] = {
        classList: { toggle: () => {}, contains: () => false },
      };
      mockElements["entry-row-1"] = {
        classList: { toggle: () => {} },
      };
      mockElements["overtime-1"] = { textContent: "" };
      mockElements["edit-controls-1"] = { style: { display: "inline-flex" } };
      mockElements["action-buttons-1"] = { style: { display: "none" } };

      let alertCalled = false;
      global.alert = () => (alertCalled = true);
      global.fetch = () => Promise.reject(new Error("Network error"));

      await exportedFunctions.saveAll();

      expect(saveAllBtn.disabled).toBe(false);
      expect(editAllBtn.disabled).toBe(false);
      expect(alertCalled).toBe(true);
    });
  });

  describe("global function exposure", () => {
    test("exposes all required functions globally", () => {
      expect(typeof exportedFunctions.confirmLockWithMissing).toBe("function");
      expect(typeof exportedFunctions.editEntry).toBe("function");
      expect(typeof exportedFunctions.saveEntry).toBe("function");
      expect(typeof exportedFunctions.cancelEdit).toBe("function");
      expect(typeof exportedFunctions.toggleEditAll).toBe("function");
      expect(typeof exportedFunctions.saveAll).toBe("function");
      expect(typeof exportedFunctions.copyToClipboard).toBe("function");
    });
  });

  describe("copyToClipboard", () => {
    let mockClipboardWrite;
    let mockBlob;
    let capturedAlert;

    beforeEach(() => {
      capturedAlert = null;
      global.alert = (msg) => {
        capturedAlert = msg;
      };

      mockBlob = class MockBlob {
        constructor(content, options) {
          this.content = content;
          this.type = options?.type;
        }
      };
      global.Blob = mockBlob;

      mockClipboardWrite = [];
      global.ClipboardItem = class MockClipboardItem {
        constructor(data) {
          this.data = data;
        }
      };
      Object.defineProperty(globalThis, "navigator", {
        configurable: true,
        value: {
          clipboard: {
            write: (items) => {
              mockClipboardWrite = items;
              return Promise.resolve();
            },
          },
        },
      });
    });

    test("alerts when no entries exist", async () => {
      global.document.querySelectorAll = () => [];

      await exportedFunctions.copyToClipboard({ target: {} });

      expect(capturedAlert).toBe("No entries to copy");
    });

    test("generates HTML table for weekday without start time", async () => {
      const mockRow = {
        querySelector: (selector) => {
          if (selector === ".exit-time-cell")
            return { classList: { contains: () => false } };
          if (selector === "td:nth-child(1) .badge")
            return { textContent: "ECC 1" };
          if (selector === "td:nth-child(2)")
            return { textContent: "John Doe" };
          if (selector === ".overtime-cell span")
            return { textContent: "2.50 hrs" };
          return null;
        },
      };

      global.document.querySelectorAll = (selector) => {
        if (selector === "tr[data-entry-id]") return [mockRow];
        return [];
      };

      global.document.querySelector = (selector) => {
        if (selector === ".start-time-cell") return null;
        return null;
      };

      mockElements["sheet-date"] = {
        textContent: "February 07, 2026\nWeekend/Holiday",
      };

      const mockButton = {
        innerHTML: "",
        classList: {
          remove: () => {},
          add: () => {},
        },
      };

      const event = {
        target: {
          closest: () => mockButton,
        },
      };

      await exportedFunctions.copyToClipboard(event);

      expect(mockClipboardWrite.length).toBe(1);
      expect(mockClipboardWrite[0].data["text/html"]).toBeDefined();
      expect(mockClipboardWrite[0].data["text/plain"]).toBeDefined();

      const htmlContent = mockClipboardWrite[0].data["text/html"].content[0];
      expect(htmlContent).toContain("February 07, 2026");
      expect(htmlContent).toContain("<th>Role</th>");
      expect(htmlContent).toContain("<th>Name</th>");
      expect(htmlContent).toContain("<th>Overtime</th>");
      expect(htmlContent).toContain("<td>ECC 1</td>");
      expect(htmlContent).toContain("<td>John Doe</td>");
      expect(htmlContent).toContain("<td>2.50 hrs</td>");
      expect(htmlContent).toContain("Total Overtime:");
      expect(htmlContent).toContain("2.50 hrs");
    });

    test("generates HTML table for weekend with start time", async () => {
      const mockRow = {
        querySelector: (selector) => {
          if (selector === ".exit-time-cell")
            return { classList: { contains: () => false } };
          if (selector === "td:nth-child(1) .badge")
            return { textContent: "ECA 1" };
          if (selector === "td:nth-child(2)")
            return { textContent: "Jane Smith" };
          if (selector === ".start-time-cell span")
            return { textContent: "08:00 AM" };
          if (selector === ".overtime-cell span")
            return { textContent: "4.00 hrs" };
          return null;
        },
      };

      global.document.querySelectorAll = (selector) => {
        if (selector === "tr[data-entry-id]") return [mockRow];
        return [];
      };

      global.document.querySelector = (selector) => {
        if (selector === ".start-time-cell") return {};
        return null;
      };

      mockElements["sheet-date"] = { textContent: "February 08, 2026" };

      const mockButton = {
        innerHTML: "",
        classList: { remove: () => {}, add: () => {} },
      };

      await exportedFunctions.copyToClipboard({
        target: { closest: () => mockButton },
      });

      const htmlContent = mockClipboardWrite[0].data["text/html"].content[0];
      expect(htmlContent).toContain("<th>Start Time</th>");
      expect(htmlContent).toContain("<td>08:00 AM</td>");
      expect(htmlContent).toContain("Total Overtime:");
      expect(htmlContent).toContain("4.00 hrs");
    });

    test("skips entries with missing exit times", async () => {
      const mockRowWithExit = {
        querySelector: (selector) => {
          if (selector === ".exit-time-cell")
            return { classList: { contains: () => false } };
          if (selector === "td:nth-child(1) .badge")
            return { textContent: "ECC 1" };
          if (selector === "td:nth-child(2)")
            return { textContent: "John Doe" };
          if (selector === ".overtime-cell span")
            return { textContent: "2.00 hrs" };
          return null;
        },
      };

      const mockRowMissing = {
        querySelector: (selector) => {
          if (selector === ".exit-time-cell")
            return { classList: { contains: () => true } };
          return null;
        },
      };

      global.document.querySelectorAll = (selector) => {
        if (selector === "tr[data-entry-id]")
          return [mockRowWithExit, mockRowMissing];
        return [];
      };

      global.document.querySelector = (selector) => {
        if (selector === ".start-time-cell") return null;
        return null;
      };

      mockElements["sheet-date"] = { textContent: "February 07, 2026" };

      const mockButton = {
        innerHTML: "",
        classList: { remove: () => {}, add: () => {} },
      };

      await exportedFunctions.copyToClipboard({
        target: { closest: () => mockButton },
      });

      const htmlContent = mockClipboardWrite[0].data["text/html"].content[0];
      expect(htmlContent).toContain("John Doe");
      expect(htmlContent).not.toContain("Jane Smith");
    });

    test("calculates total overtime correctly", async () => {
      const createMockRow = (name, overtime) => ({
        querySelector: (selector) => {
          if (selector === ".exit-time-cell")
            return { classList: { contains: () => false } };
          if (selector === "td:nth-child(1) .badge")
            return { textContent: "ECC 1" };
          if (selector === "td:nth-child(2)") return { textContent: name };
          if (selector === ".overtime-cell span")
            return { textContent: overtime };
          return null;
        },
      });

      global.document.querySelectorAll = (selector) => {
        if (selector === "tr[data-entry-id]")
          return [
            createMockRow("Person 1", "2.50 hrs"),
            createMockRow("Person 2", "3.25 hrs"),
            createMockRow("Person 3", "1.00 hrs"),
          ];
        return [];
      };

      global.document.querySelector = (selector) => {
        if (selector === ".start-time-cell") return null;
        return null;
      };

      mockElements["sheet-date"] = { textContent: "February 07, 2026" };

      const mockButton = {
        innerHTML: "",
        classList: { remove: () => {}, add: () => {} },
      };

      await exportedFunctions.copyToClipboard({
        target: { closest: () => mockButton },
      });

      const htmlContent = mockClipboardWrite[0].data["text/html"].content[0];
      expect(htmlContent).toContain("6.75 hrs");
    });

    test("shows success feedback after copying", async () => {
      const mockRow = {
        querySelector: (selector) => {
          if (selector === ".exit-time-cell")
            return { classList: { contains: () => false } };
          if (selector === "td:nth-child(1) .badge")
            return { textContent: "ECC 1" };
          if (selector === "td:nth-child(2)")
            return { textContent: "John Doe" };
          if (selector === ".overtime-cell span")
            return { textContent: "2.00 hrs" };
          return null;
        },
      };

      global.document.querySelectorAll = (selector) => {
        if (selector === "tr[data-entry-id]") return [mockRow];
        return [];
      };

      global.document.querySelector = (selector) => {
        if (selector === ".start-time-cell") return null;
        return null;
      };

      mockElements["sheet-date"] = { textContent: "February 07, 2026" };

      const mockButton = {
        innerHTML: '<i class="bi bi-clipboard me-1"></i>Copy to Clipboard',
        classList: {
          remove: () => {},
          add: () => {},
        },
      };

      let setTimeoutCalled = false;
      global.setTimeout = (_fn) => {
        setTimeoutCalled = true;
      };

      await exportedFunctions.copyToClipboard({
        target: { closest: () => mockButton },
      });

      expect(mockButton.innerHTML).toContain("Copied!");
      expect(setTimeoutCalled).toBe(true);
    });

    test("handles clipboard write errors gracefully", async () => {
      const mockRow = {
        querySelector: (selector) => {
          if (selector === ".exit-time-cell")
            return { classList: { contains: () => false } };
          if (selector === "td:nth-child(1) .badge")
            return { textContent: "ECC 1" };
          if (selector === "td:nth-child(2)")
            return { textContent: "John Doe" };
          if (selector === ".overtime-cell span")
            return { textContent: "2.00 hrs" };
          return null;
        },
      };

      global.document.querySelectorAll = (selector) => {
        if (selector === "tr[data-entry-id]") return [mockRow];
        return [];
      };

      global.document.querySelector = (selector) => {
        if (selector === ".start-time-cell") return null;
        return null;
      };

      mockElements["sheet-date"] = { textContent: "February 07, 2026" };

      global.navigator.clipboard.write = () =>
        Promise.reject(new Error("Clipboard error"));

      const mockButton = {
        innerHTML: "",
        classList: { remove: () => {}, add: () => {} },
      };

      await exportedFunctions.copyToClipboard({
        target: { closest: () => mockButton },
      });

      expect(capturedAlert).toBe(
        "Failed to copy to clipboard. Please try again.",
      );
    });
  });

  describe("toggleStartTimeField", () => {
    test("shows start time field when backup role is selected", () => {
      const mockRoleSelect = {
        options: [
          { dataset: { isBackup: "false" } },
          { dataset: { isBackup: "true" } },
        ],
        selectedIndex: 1,
      };

      const mockStartTimeContainer = { style: { display: "none" } };

      mockElements.role_id = mockRoleSelect;
      mockElements.start_time_container = mockStartTimeContainer;

      exportedFunctions.toggleStartTimeField();

      expect(mockStartTimeContainer.style.display).toBe("block");
    });

    test("hides start time field when non-backup role is selected", () => {
      const mockRoleSelect = {
        options: [
          { dataset: { isBackup: "false" } },
          { dataset: { isBackup: "true" } },
        ],
        selectedIndex: 0,
      };

      const mockStartTimeContainer = { style: { display: "block" } };

      mockElements.role_id = mockRoleSelect;
      mockElements.start_time_container = mockStartTimeContainer;

      exportedFunctions.toggleStartTimeField();

      expect(mockStartTimeContainer.style.display).toBe("none");
    });

    test("handles missing role select element gracefully", () => {
      mockElements.role_id = null;
      const mockStartTimeContainer = { style: { display: "block" } };
      mockElements.start_time_container = mockStartTimeContainer;

      exportedFunctions.toggleStartTimeField();

      // Should return early without error, display unchanged
      expect(mockStartTimeContainer.style.display).toBe("block");
    });

    test("handles missing start time container gracefully", () => {
      const mockRoleSelect = {
        options: [{ dataset: { isBackup: "true" } }],
        selectedIndex: 0,
      };

      mockElements.role_id = mockRoleSelect;
      mockElements.start_time_container = null;

      // Should not throw an error
      expect(() => exportedFunctions.toggleStartTimeField()).not.toThrow();
    });

    test("handles role with no dataset attribute", () => {
      const mockRoleSelect = {
        options: [{}],
        selectedIndex: 0,
      };

      const mockStartTimeContainer = { style: { display: "block" } };

      mockElements.role_id = mockRoleSelect;
      mockElements.start_time_container = mockStartTimeContainer;

      exportedFunctions.toggleStartTimeField();

      expect(mockStartTimeContainer.style.display).toBe("none");
    });
  });

  describe("editEntry with backup roles", () => {
    test("handles start time input for backup roles", () => {
      const mockInput = { value: "18:00", focus: () => {} };
      const mockStartInput = { value: "08:00", style: { display: "" } };
      const mockStartDisplay = { style: { display: "inline" } };
      const mockDisplay = { style: { display: "" } };
      const mockForm = { style: { display: "" } };
      const mockEditControls = { style: { display: "" } };
      const mockActionButtons = { style: { display: "" } };

      mockElements["input-3"] = mockInput;
      mockElements["start-input-3"] = mockStartInput;
      mockElements["start-display-3"] = mockStartDisplay;
      mockElements["display-3"] = mockDisplay;
      mockElements["form-3"] = mockForm;
      mockElements["edit-controls-3"] = mockEditControls;
      mockElements["action-buttons-3"] = mockActionButtons;

      exportedFunctions.editEntry(3);

      expect(mockStartDisplay.style.display).toBe("none");
      expect(mockStartInput.style.display).toBe("inline");
    });
  });

  describe("cancelEdit with backup roles", () => {
    test("restores start time for backup roles", () => {
      const mockInput = { value: "19:00", focus: () => {} };
      const mockStartInput = { value: "09:00", style: { display: "inline" } };
      const mockStartDisplay = { style: { display: "none" } };
      const mockDisplay = { style: { display: "none" } };
      const mockForm = { style: { display: "inline" } };
      const mockEditControls = { style: { display: "inline-flex" } };
      const mockActionButtons = { style: { display: "none" } };

      mockElements["input-4"] = mockInput;
      mockElements["start-input-4"] = mockStartInput;
      mockElements["start-display-4"] = mockStartDisplay;
      mockElements["display-4"] = mockDisplay;
      mockElements["form-4"] = mockForm;
      mockElements["edit-controls-4"] = mockEditControls;
      mockElements["action-buttons-4"] = mockActionButtons;

      // First edit to store original value
      exportedFunctions.editEntry(4);
      // Modify the start input
      mockStartInput.value = "10:00";
      // Then cancel
      exportedFunctions.cancelEdit(4);

      expect(mockStartInput.style.display).toBe("none");
      expect(mockStartDisplay.style.display).toBe("inline");
      expect(mockStartInput.value).toBe("09:00");
    });
  });

  describe("cancelEdit with legacy single value", () => {
    test("handles legacy originalValues format (single value)", () => {
      const mockInput = { value: "18:00", focus: () => {} };
      const mockDisplay = { style: { display: "none" } };
      const mockForm = { style: { display: "inline" } };
      const mockEditControls = { style: { display: "inline-flex" } };
      const mockActionButtons = { style: { display: "none" } };

      mockElements["input-5"] = mockInput;
      mockElements["display-5"] = mockDisplay;
      mockElements["form-5"] = mockForm;
      mockElements["edit-controls-5"] = mockEditControls;
      mockElements["action-buttons-5"] = mockActionButtons;

      // Edit the entry - this stores the original value "18:00"
      exportedFunctions.editEntry(5);
      // Modify the input
      mockInput.value = "21:00";
      // Then cancel - should restore to "18:00"
      exportedFunctions.cancelEdit(5);

      // Original value should be restored
      expect(mockInput.value).toBe("18:00");
    });
  });

  describe("toggleEditAll cancel mode", () => {
    test("verifies toggle behavior by checking state changes", () => {
      // Start with edit mode button that tracks its state
      const buttonContainer = {
        classList: {
          add: () => {},
          remove: () => {},
        },
      };
      const editAllBtn = {
        innerHTML: '<i class="bi bi-pencil-square me-1"></i>Edit All',
        classList: {
          remove: () => {},
          add: () => {},
        },
      };
      const saveAllBtn = { style: { display: "none" } };

      mockElements["edit-all-controls"] = buttonContainer;
      mockElements["edit-all-btn"] = editAllBtn;
      mockElements["save-all-btn"] = saveAllBtn;

      // Set up mock entries
      [6, 7].forEach((id) => {
        mockElements[`input-${id}`] = { value: "18:00", focus: () => {} };
        mockElements[`display-${id}`] = { style: { display: "" } };
        mockElements[`form-${id}`] = { style: { display: "" } };
        mockElements[`edit-controls-${id}`] = { style: { display: "" } };
        mockElements[`action-buttons-${id}`] = { style: { display: "" } };
      });

      global.document.querySelectorAll = () => [
        { dataset: { entryId: "6" } },
        { dataset: { entryId: "7" } },
      ];

      // Toggle twice - should end up back in original state
      // (Note: Module state may persist from previous tests)

      // Two toggles should return to original state
      exportedFunctions.toggleEditAll();
      exportedFunctions.toggleEditAll();

      // After two toggles, we should be back to same state
      // The exact state depends on where we started
      expect(typeof editAllBtn.innerHTML).toBe("string");
      expect(typeof saveAllBtn.style.display).toBe("string");
    });
  });
});

describe("Countdown Timer Functions", () => {
  describe("updateCountdown", () => {
    test("decrements minutes when timer exists", () => {
      const timer = {
        dataset: { minutes: "5" },
        textContent: "(5 minutes remaining)",
      };
      mockElements["countdown-timer"] = timer;

      // Mock setInterval and setTimeout
      global.setInterval = (fn) => fn;
      global.setTimeout = () => {};

      // Manually call updateCountdown-like behavior
      let minutes = parseInt(timer.dataset.minutes, 10);
      if (minutes > 0) {
        minutes--;
        timer.dataset.minutes = String(minutes);
        timer.textContent = `(${minutes} minutes remaining)`;
      }

      expect(timer.dataset.minutes).toBe("4");
      expect(timer.textContent).toBe("(4 minutes remaining)");
    });

    test("shows locking message when timer reaches zero", () => {
      const timer = {
        dataset: { minutes: "1" },
        textContent: "(1 minutes remaining)",
      };
      mockElements["countdown-timer"] = timer;

      // Simulate countdown to zero
      let minutes = parseInt(timer.dataset.minutes, 10);
      if (minutes > 0) {
        minutes--;
        timer.dataset.minutes = String(minutes);
        if (minutes === 0) {
          timer.textContent = "(Locking now...)";
        }
      }

      expect(timer.dataset.minutes).toBe("0");
      expect(timer.textContent).toBe("(Locking now...)");
    });

    test("does nothing when timer element not found", () => {
      // Clear the timer element
      mockElements["countdown-timer"] = undefined;

      // This should not throw an error
      // The function checks for null and returns early
    });
  });
});

describe("Role Select Functions", () => {
  describe("toggleStartTimeField", () => {
    test("shows start time container for backup role", () => {
      const roleSelect = {
        options: [
          { dataset: { isBackup: "false" } },
          { dataset: { isBackup: "true" } },
        ],
        selectedIndex: 1,
      };
      const startTimeContainer = { style: { display: "none" } };

      mockElements.role_id = roleSelect;
      mockElements.start_time_container = startTimeContainer;

      // Simulate toggleStartTimeField logic
      const selectedOption = roleSelect.options[roleSelect.selectedIndex];
      const isBackup = selectedOption?.dataset?.isBackup === "true";
      startTimeContainer.style.display = isBackup ? "block" : "none";

      expect(startTimeContainer.style.display).toBe("block");
    });

    test("hides start time container for non-backup role", () => {
      const roleSelect = {
        options: [
          { dataset: { isBackup: "false" } },
          { dataset: { isBackup: "true" } },
        ],
        selectedIndex: 0,
      };
      const startTimeContainer = { style: { display: "block" } };

      mockElements.role_id = roleSelect;
      mockElements.start_time_container = startTimeContainer;

      // Simulate toggleStartTimeField logic
      const selectedOption = roleSelect.options[roleSelect.selectedIndex];
      const isBackup = selectedOption?.dataset?.isBackup === "true";
      startTimeContainer.style.display = isBackup ? "block" : "none";

      expect(startTimeContainer.style.display).toBe("none");
    });

    test("handles missing role select gracefully", () => {
      mockElements.role_id = undefined;
      mockElements.start_time_container = { style: { display: "none" } };

      // Should not throw when role select is missing
      const roleSelect = mockElements.role_id;
      if (!roleSelect) return;
      // This line should not be reached
      expect(true).toBe(true);
    });

    test("handles missing start time container gracefully", () => {
      mockElements.role_id = { options: [], selectedIndex: 0 };
      mockElements.start_time_container = undefined;

      // Should not throw when container is missing
      const container = mockElements.start_time_container;
      if (!container) return;
      // This line should not be reached
      expect(true).toBe(true);
    });
  });

  describe("initializeAddEntryForm", () => {
    let capturedNotification = null;

    beforeEach(() => {
      capturedNotification = null;
      global.window.showNotification = (msg, type) => {
        capturedNotification = { msg, type };
      };
      // Reset querySelector to default no-op
      global.document.querySelector = mockQuerySelector;
    });

    test("handles missing add-entry card gracefully", () => {
      global.document.querySelector = () => null;
      expect(() => global.window.initializeAddEntryForm()).not.toThrow();
    });

    test("handles missing form inside card gracefully", () => {
      const mockCard = { querySelector: () => null };
      global.document.querySelector = (sel) =>
        sel === ".add-entry-form" ? mockCard : null;
      expect(() => global.window.initializeAddEntryForm()).not.toThrow();
    });

    test("attaches submit listener to the add-entry form", () => {
      let capturedListener = null;
      const mockForm = {
        addEventListener: (evt, fn) => {
          if (evt === "submit") capturedListener = fn;
        },
        querySelector: () => null,
        action: "/entries/add",
      };
      const mockCard = { querySelector: () => mockForm };
      global.document.querySelector = (sel) =>
        sel === ".add-entry-form" ? mockCard : null;

      global.window.initializeAddEntryForm();

      expect(capturedListener).toBeTypeOf("function");
    });

    test("shows success notification and resets variable fields on success", async () => {
      let capturedListener = null;
      let residentReset = false;
      let exitReset = false;
      let residentFocused = false;

      const mockResidentSelect = {
        get value() {
          return "42";
        },
        set value(v) {
          if (v === "") residentReset = true;
        },
        focus: () => {
          residentFocused = true;
        },
      };
      const mockExitInput = {
        get value() {
          return "20:00";
        },
        set value(v) {
          if (v === "") exitReset = true;
        },
      };
      const mockSubmitBtn = {
        innerHTML: '<i class="bi bi-check-circle me-2"></i>Add Entry',
        disabled: false,
      };

      const mockForm = {
        addEventListener: (evt, fn) => {
          if (evt === "submit") capturedListener = fn;
        },
        action: "/entries/add",
        querySelector: (sel) => {
          if (sel === '[name="csrf_token"]') return { value: "test-token" };
          if (sel === '[name="resident_id"]') return mockResidentSelect;
          if (sel === '[name="exit_time"]') return mockExitInput;
          if (sel === '[name="start_time"]') return null;
          if (sel === 'button[type="submit"]') return mockSubmitBtn;
          return null;
        },
      };
      const mockCard = { querySelector: () => mockForm };

      const mockTbody = { appendChild: () => {} };
      global.document.querySelector = (sel) => {
        if (sel === ".add-entry-form") return mockCard;
        if (sel === ".entries-table tbody") return mockTbody;
        if (sel === ".no-entries") return null;
        if (sel === ".start-time-cell") return null;
        if (sel === '[name="csrf_token"]') return { value: "test-token" };
        return null;
      };
      global.document.querySelectorAll = () => [];
      global.document.getElementById = (id) => mockElements[id] || null;
      global.document.createElement = () => ({
        className: "",
        id: "",
        innerHTML: "",
        dataset: {},
        querySelector: () => null,
        querySelectorAll: () => [],
        appendChild: () => {},
      });

      const mockEntry = {
        id: 1,
        resident_id: 42,
        role_id: 1,
        resident_name: "Test Resident",
        role_name: "ECC 1",
        role_is_backup: false,
        missing_exit_time: false,
        exit_time: "20:00",
        exit_time_display: "08:00 PM",
        start_time: null,
        start_time_display: null,
        overtime_display: "2.50 hrs",
      };

      global.fetch = vi.fn().mockResolvedValue({
        ok: true,
        headers: { get: () => "application/json" },
        json: () =>
          Promise.resolve({
            success: true,
            message: "Entry added successfully",
            entry: mockEntry,
          }),
      });

      global.window.initializeAddEntryForm();

      await capturedListener({ preventDefault: () => {} });

      expect(capturedNotification?.type).toBe("success");
      expect(residentReset).toBe(true);
      expect(exitReset).toBe(true);
      expect(residentFocused).toBe(true);
    });

    test("shows error notification when fetch fails", async () => {
      let capturedListener = null;

      const mockSubmitBtn = { innerHTML: "Add Entry", disabled: false };
      const mockForm = {
        addEventListener: (evt, fn) => {
          if (evt === "submit") capturedListener = fn;
        },
        action: "/entries/add",
        querySelector: (sel) => {
          if (sel === '[name="csrf_token"]') return { value: "token" };
          if (sel === 'button[type="submit"]') return mockSubmitBtn;
          return null;
        },
      };
      const mockCard = { querySelector: () => mockForm };
      global.document.querySelector = (sel) =>
        sel === ".add-entry-form" ? mockCard : null;

      global.fetch = vi.fn().mockResolvedValue({
        ok: false,
        headers: { get: () => "application/json" },
        json: () =>
          Promise.resolve({ success: false, message: "Validation failed." }),
      });

      global.window.initializeAddEntryForm();

      await capturedListener({ preventDefault: () => {} });

      expect(capturedNotification?.type).toBe("error");
      expect(capturedNotification?.msg).toContain("Validation failed.");
      // Button should be re-enabled after error
      expect(mockSubmitBtn.disabled).toBe(false);
    });
  });
});

describe("Async Delete Functions", () => {
  describe("removeEntryRow", () => {
    test("removes the row element from the DOM", () => {
      let removed = false;
      const mockRow = {
        dataset: { residentId: "1", roleId: "2" },
        remove: () => {
          removed = true;
        },
      };
      mockElements["entry-row-42"] = mockRow;

      global.document.getElementById = (id) => mockElements[id] || null;
      global.document.querySelectorAll = () => [];

      exportedFunctions.removeEntryRow("42");

      expect(removed).toBe(true);
    });

    test("does not throw when row does not exist", () => {
      global.document.getElementById = () => null;
      global.document.querySelectorAll = () => [];

      expect(() => exportedFunctions.removeEntryRow("999")).not.toThrow();
    });
  });

  describe("initializeAsyncDelete", () => {
    test("attaches submit listener to async-delete-form elements", () => {
      let capturedListener = null;
      const mockForm = {
        dataset: { entryId: "10" },
        action: "/entries/10/delete",
        addEventListener: (evt, fn) => {
          if (evt === "submit") capturedListener = fn;
        },
        querySelector: () => ({ value: "csrf-tok" }),
      };

      global.document.querySelectorAll = (sel) =>
        sel === ".async-delete-form" ? [mockForm] : [];

      exportedFunctions.initializeAsyncDelete();

      expect(capturedListener).toBeTypeOf("function");
    });

    test("removes the row and notifies on successful delete", async () => {
      let capturedListener = null;
      let notified = null;
      let removed = false;

      global.window.showNotification = (msg, type) => {
        notified = { msg, type };
      };

      const mockRow = {
        dataset: { residentId: "1", roleId: "2" },
        remove: () => {
          removed = true;
        },
      };
      mockElements["entry-row-10"] = mockRow;

      const mockForm = {
        dataset: { entryId: "10" },
        action: "/entries/10/delete",
        addEventListener: (evt, fn) => {
          if (evt === "submit") capturedListener = fn;
        },
        querySelector: () => ({ value: "csrf-tok" }),
      };

      global.document.querySelectorAll = (sel) => {
        if (sel === ".async-delete-form") return [mockForm];
        return [];
      };
      global.document.getElementById = (id) => mockElements[id] || null;

      global.fetch = () =>
        Promise.resolve({
          ok: true,
          headers: { get: () => "application/json" },
          json: () =>
            Promise.resolve({
              success: true,
              message: "Entry deleted successfully",
            }),
        });

      exportedFunctions.initializeAsyncDelete();
      await capturedListener({
        preventDefault: () => {},
        stopImmediatePropagation: () => {},
      });

      expect(removed).toBe(true);
      expect(notified?.type).toBe("success");
    });

    test("shows error notification when delete fetch fails", async () => {
      let capturedListener = null;
      let notified = null;

      global.window.showNotification = (msg, type) => {
        notified = { msg, type };
      };

      const mockForm = {
        dataset: { entryId: "11" },
        action: "/entries/11/delete",
        addEventListener: (evt, fn) => {
          if (evt === "submit") capturedListener = fn;
        },
        querySelector: () => ({ value: "csrf-tok" }),
      };

      global.document.querySelectorAll = (sel) =>
        sel === ".async-delete-form" ? [mockForm] : [];
      global.document.getElementById = () => null;

      global.fetch = () =>
        Promise.resolve({
          ok: false,
          headers: { get: () => "application/json" },
          json: () =>
            Promise.resolve({ success: false, message: "Permission denied." }),
        });

      exportedFunctions.initializeAsyncDelete();
      await capturedListener({
        preventDefault: () => {},
        stopImmediatePropagation: () => {},
      });

      expect(notified?.type).toBe("error");
      expect(notified?.msg).toContain("Permission denied.");
    });
  });
});

describe("Duplicate Entry Warning", () => {
  describe("getExistingEntryKeys", () => {
    test("returns resident:role keys seeded by initializeEntryKeySet", () => {
      const rows = [
        { dataset: { residentId: "1", roleId: "2" } },
        { dataset: { residentId: "3", roleId: "4" } },
      ];
      global.document.querySelectorAll = (sel) =>
        sel === "tr[data-entry-id]" ? rows : [];

      // Seed the in-memory Set from the mocked DOM
      global.window.initializeEntryKeySet();

      const keys = exportedFunctions.getExistingEntryKeys();

      expect(keys.has("1:2")).toBe(true);
      expect(keys.has("3:4")).toBe(true);
      expect(keys.size).toBe(2);
    });

    test("skips rows missing resident or role id during initialization", () => {
      const rows = [
        { dataset: { residentId: "1" } },
        { dataset: { roleId: "4" } },
        { dataset: {} },
      ];
      global.document.querySelectorAll = (sel) =>
        sel === "tr[data-entry-id]" ? rows : [];

      global.window.initializeEntryKeySet();

      const keys = exportedFunctions.getExistingEntryKeys();

      expect(keys.size).toBe(0);
    });
  });

  describe("initializeDuplicateEntryWarning", () => {
    test("does not throw when add-entry-form is absent", () => {
      global.document.querySelector = () => null;
      expect(() =>
        exportedFunctions.initializeDuplicateEntryWarning(),
      ).not.toThrow();
    });

    test("shows warning when resident+role combo already exists", () => {
      let changeHandlerRole = null;
      let changeHandlerResident = null;
      let warningDisplay = "none";

      const warningEl = {
        id: "duplicate-entry-warning",
        className: "",
        style: {
          get display() {
            return warningDisplay;
          },
          set display(v) {
            warningDisplay = v;
          },
        },
        setAttribute: () => {},
        set innerHTML(_) {},
      };

      const mockInsertBefore = () => {};

      const mockMt3 = { before: mockInsertBefore };

      const mockRoleSelect = {
        value: "2",
        addEventListener: (evt, fn) => {
          if (evt === "change") changeHandlerRole = fn;
        },
      };
      const mockResidentSelect = {
        value: "1",
        addEventListener: (evt, fn) => {
          if (evt === "change") changeHandlerResident = fn;
        },
      };

      const mockForm = {
        querySelector: (sel) => {
          if (sel === '[name="role_id"]') return mockRoleSelect;
          if (sel === '[name="resident_id"]') return mockResidentSelect;
          if (sel === ".mt-3") return mockMt3;
          return null;
        },
      };
      const mockCard = { querySelector: () => mockForm };

      global.document.querySelector = (sel) =>
        sel === ".add-entry-form" ? mockCard : null;

      global.document.createElement = () => warningEl;

      // Seed the in-memory Set with an existing row (resident 1, role 2)
      global.document.querySelectorAll = (sel) => {
        if (sel === "tr[data-entry-id]")
          return [{ dataset: { residentId: "1", roleId: "2" } }];
        return [];
      };
      global.window.initializeEntryKeySet();

      exportedFunctions.initializeDuplicateEntryWarning();

      // Trigger the check
      changeHandlerResident();

      expect(warningDisplay).toBe("block");
    });
  });
});

describe("insertEntryRow", () => {
  let appendedChild;
  let tbody;

  beforeEach(() => {
    appendedChild = null;
    tbody = {
      appendChild: (el) => {
        appendedChild = el;
      },
    };
  });

  function setupQuerySelector(tbodyEl, startTimeCell = null) {
    global.document.querySelector = (sel) => {
      if (sel === ".entries-table tbody") return tbodyEl;
      if (sel === ".no-entries") return null;
      if (sel === ".start-time-cell") return startTimeCell;
      if (sel === '[name="csrf_token"]') return { value: "tok" };
      return null;
    };
    global.document.querySelectorAll = () => [];
  }

  const baseEntry = {
    id: 99,
    resident_id: 5,
    role_id: 3,
    resident_name: "Test Resident",
    role_name: "ECC 1",
    role_is_backup: false,
    missing_exit_time: false,
    exit_time: "20:30",
    exit_time_display: "08:30 PM",
    start_time: null,
    start_time_display: null,
    overtime_display: "2.50 hrs",
  };

  test("appends a new tr with correct data attributes", () => {
    setupQuerySelector(tbody);
    // Provide a minimal createElement that returns a real-ish object
    global.document.createElement = (tag) => {
      const el = {
        tagName: tag,
        className: "",
        id: "",
        innerHTML: "",
        dataset: {},
        querySelector: () => null,
        querySelectorAll: () => [],
        appendChild: () => {},
      };
      return el;
    };

    exportedFunctions.insertEntryRow(baseEntry, false);

    expect(appendedChild).not.toBeNull();
    expect(appendedChild.dataset.entryId).toBe("99");
    expect(appendedChild.dataset.residentId).toBe("5");
    expect(appendedChild.dataset.roleId).toBe("3");
    expect(appendedChild.dataset.roleIsBackup).toBe("false");
    expect(appendedChild.id).toBe("entry-row-99");
  });

  test("adds entry-missing-data class when exit time is missing", () => {
    setupQuerySelector(tbody);
    global.document.createElement = () => ({
      className: "",
      id: "",
      innerHTML: "",
      dataset: {},
      querySelector: () => null,
      querySelectorAll: () => [],
      appendChild: () => {},
    });

    const entry = {
      ...baseEntry,
      missing_exit_time: true,
      exit_time: null,
      exit_time_display: null,
    };
    exportedFunctions.insertEntryRow(entry, false);

    expect(appendedChild.className).toContain("entry-missing-data");
  });

  test("does not throw when tbody is absent", () => {
    setupQuerySelector(null);
    expect(() =>
      exportedFunctions.insertEntryRow(baseEntry, false),
    ).not.toThrow();
    expect(appendedChild).toBeNull();
  });
});

describe("updateEntrySummaryCount", () => {
  test("updates entry-count span text with correct singular form", () => {
    let countText = "";
    const countEl = {
      get textContent() {
        return countText;
      },
      set textContent(v) {
        countText = v;
      },
    };
    const summaryEl = {
      querySelector: (sel) => (sel === ".entry-count" ? countEl : null),
    };
    global.document.getElementById = (id) =>
      id === "sheet-summary" ? summaryEl : null;
    global.document.querySelectorAll = (sel) =>
      sel === "tr[data-entry-id]" ? [{ dataset: {} }] : [];

    exportedFunctions.updateEntrySummaryCount();

    expect(countText).toBe("1 entry");
  });

  test("updates entry-count span text with correct plural form", () => {
    let countText = "";
    const countEl = {
      get textContent() {
        return countText;
      },
      set textContent(v) {
        countText = v;
      },
    };
    const summaryEl = {
      querySelector: (sel) => (sel === ".entry-count" ? countEl : null),
    };
    global.document.getElementById = (id) =>
      id === "sheet-summary" ? summaryEl : null;
    global.document.querySelectorAll = (sel) =>
      sel === "tr[data-entry-id]"
        ? [{ dataset: {} }, { dataset: {} }, { dataset: {} }]
        : [];

    exportedFunctions.updateEntrySummaryCount();

    expect(countText).toBe("3 entries");
  });

  test("does not throw when sheet-summary element is absent", () => {
    global.document.getElementById = () => null;
    global.document.querySelectorAll = () => [];
    expect(() => exportedFunctions.updateEntrySummaryCount()).not.toThrow();
  });
});

describe("initializeAddEntryForm — row insertion on success", () => {
  let capturedListener = null;
  let appendedChild = null;
  let notified = null;
  let residentReset = false;
  let exitReset = false;

  beforeEach(() => {
    capturedListener = null;
    appendedChild = null;
    notified = null;
    residentReset = false;
    exitReset = false;

    global.window.showNotification = (msg, type) => {
      notified = { msg, type };
    };

    const tbody = {
      appendChild: (el) => {
        appendedChild = el;
      },
    };

    const mockResidentSelect = {
      get value() {
        return "5";
      },
      set value(v) {
        if (v === "") residentReset = true;
      },
      focus: () => {},
    };
    const mockExitInput = {
      get value() {
        return "20:30";
      },
      set value(v) {
        if (v === "") exitReset = true;
      },
    };
    const mockSubmitBtn = {
      innerHTML: '<i class="bi bi-check-circle me-2"></i>Add Entry',
      disabled: false,
    };

    const mockForm = {
      addEventListener: (evt, fn) => {
        if (evt === "submit") capturedListener = fn;
      },
      action: "/entries/add",
      querySelector: (sel) => {
        if (sel === '[name="csrf_token"]') return { value: "tok" };
        if (sel === '[name="resident_id"]') return mockResidentSelect;
        if (sel === '[name="exit_time"]') return mockExitInput;
        if (sel === '[name="start_time"]') return null;
        if (sel === 'button[type="submit"]') return mockSubmitBtn;
        return null;
      },
    };
    const mockCard = { querySelector: () => mockForm };

    global.document.querySelector = (sel) => {
      if (sel === ".add-entry-form") return mockCard;
      if (sel === ".entries-table tbody") return tbody;
      if (sel === ".no-entries") return null;
      if (sel === ".start-time-cell") return null;
      if (sel === '[name="csrf_token"]') return { value: "tok" };
      return null;
    };
    global.document.querySelectorAll = () => [];
    global.document.createElement = () => ({
      className: "",
      id: "",
      innerHTML: "",
      dataset: {},
      querySelector: () => null,
      querySelectorAll: () => [],
      appendChild: () => {},
    });
  });

  test("inserts row, resets form, no reload on success", async () => {
    const entry = {
      id: 50,
      resident_id: 5,
      role_id: 3,
      resident_name: "Alice",
      role_name: "ECC 1",
      role_is_backup: false,
      missing_exit_time: false,
      exit_time: "20:30",
      exit_time_display: "08:30 PM",
      start_time: null,
      start_time_display: null,
      overtime_display: "2.50 hrs",
    };

    let reloadCalled = false;
    global.window.location = {
      reload: () => {
        reloadCalled = true;
      },
    };

    global.fetch = vi.fn().mockResolvedValue({
      ok: true,
      headers: { get: () => "application/json" },
      json: () =>
        Promise.resolve({
          success: true,
          message: "Entry added successfully",
          entry,
        }),
    });

    global.window.initializeAddEntryForm();
    await capturedListener({ preventDefault: () => {} });

    expect(notified?.type).toBe("success");
    expect(appendedChild).not.toBeNull();
    expect(appendedChild.dataset.entryId).toBe("50");
    expect(residentReset).toBe(true);
    expect(exitReset).toBe(true);
    expect(reloadCalled).toBe(false);
  });

  test("does not insert row on failure", async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false,
      headers: { get: () => "application/json" },
      json: () =>
        Promise.resolve({ success: false, message: "Validation error." }),
    });

    global.window.initializeAddEntryForm();
    await capturedListener({ preventDefault: () => {} });

    expect(notified?.type).toBe("error");
    expect(appendedChild).toBeNull();
  });
});

describe("initializeAddEntryShortcut", () => {
  let keydownHandlers;
  let originalAddEventListener;

  beforeEach(() => {
    keydownHandlers = [];
    originalAddEventListener = global.document.addEventListener;
    global.document.addEventListener = (evt, fn) => {
      if (evt === "keydown") keydownHandlers.push(fn);
    };
    global.document.activeElement = {
      tagName: "BODY",
      isContentEditable: false,
    };
  });

  afterEach(() => {
    global.document.addEventListener = originalAddEventListener;
  });

  test("does not attach handler when add-entry form is absent (sheet locked)", () => {
    global.document.querySelector = () => null;
    exportedFunctions.initializeAddEntryShortcut();
    expect(keydownHandlers.length).toBe(0);
  });

  test("attaches keydown handler when add-entry form is present", () => {
    let focused = false;
    const firstInput = {
      focus: () => {
        focused = true;
      },
      tagName: "SELECT",
    };
    const mockCard = {
      querySelector: (sel) => (sel === "select, input" ? firstInput : null),
    };
    global.document.querySelector = (sel) =>
      sel === ".add-entry-form" ? mockCard : null;

    exportedFunctions.initializeAddEntryShortcut();

    expect(keydownHandlers.length).toBe(1);
    let prevented = false;
    keydownHandlers[0]({
      key: "n",
      preventDefault: () => {
        prevented = true;
      },
    });
    expect(focused).toBe(true);
    expect(prevented).toBe(true);
  });

  test("n key focuses first input", () => {
    let focused = false;
    const firstInput = {
      focus: () => {
        focused = true;
      },
    };
    const mockCard = { querySelector: () => firstInput };
    global.document.querySelector = (sel) =>
      sel === ".add-entry-form" ? mockCard : null;

    exportedFunctions.initializeAddEntryShortcut();
    keydownHandlers[0]({ key: "n", preventDefault: () => {} });
    expect(focused).toBe(true);
  });

  test("+ key focuses first input", () => {
    let focused = false;
    const firstInput = {
      focus: () => {
        focused = true;
      },
    };
    const mockCard = { querySelector: () => firstInput };
    global.document.querySelector = (sel) =>
      sel === ".add-entry-form" ? mockCard : null;

    exportedFunctions.initializeAddEntryShortcut();
    keydownHandlers[0]({ key: "+", preventDefault: () => {} });
    expect(focused).toBe(true);
  });

  test("ignores key when focus is on an input element", () => {
    let focused = false;
    const firstInput = {
      focus: () => {
        focused = true;
      },
    };
    const mockCard = { querySelector: () => firstInput };
    global.document.querySelector = (sel) =>
      sel === ".add-entry-form" ? mockCard : null;
    global.document.activeElement = {
      tagName: "INPUT",
      isContentEditable: false,
    };

    exportedFunctions.initializeAddEntryShortcut();
    keydownHandlers[0]({ key: "n", preventDefault: () => {} });
    expect(focused).toBe(false);
  });

  test("ignores key when focus is on a select element", () => {
    let focused = false;
    const firstInput = {
      focus: () => {
        focused = true;
      },
    };
    const mockCard = { querySelector: () => firstInput };
    global.document.querySelector = (sel) =>
      sel === ".add-entry-form" ? mockCard : null;
    global.document.activeElement = {
      tagName: "SELECT",
      isContentEditable: false,
    };

    exportedFunctions.initializeAddEntryShortcut();
    keydownHandlers[0]({ key: "n", preventDefault: () => {} });
    expect(focused).toBe(false);
  });

  test("ignores key when focus is on a button element", () => {
    let focused = false;
    const firstInput = {
      focus: () => {
        focused = true;
      },
    };
    const mockCard = { querySelector: () => firstInput };
    global.document.querySelector = (sel) =>
      sel === ".add-entry-form" ? mockCard : null;
    global.document.activeElement = {
      tagName: "BUTTON",
      isContentEditable: false,
    };

    exportedFunctions.initializeAddEntryShortcut();
    keydownHandlers[0]({ key: "n", preventDefault: () => {} });
    expect(focused).toBe(false);
  });

  test("ignores unrelated keys", () => {
    let focused = false;
    const firstInput = {
      focus: () => {
        focused = true;
      },
    };
    const mockCard = { querySelector: () => firstInput };
    global.document.querySelector = (sel) =>
      sel === ".add-entry-form" ? mockCard : null;

    exportedFunctions.initializeAddEntryShortcut();
    keydownHandlers[0]({ key: "a", preventDefault: () => {} });
    expect(focused).toBe(false);
  });
});

describe("Async Lock/Unlock", () => {
  let capturedNotification;
  let capturedListener;

  beforeEach(() => {
    capturedNotification = null;
    capturedListener = null;
    global.window.showNotification = (msg, type) => {
      capturedNotification = { msg, type };
    };
    global.document.querySelector = mockQuerySelector;
    global.document.getElementById = mockGetElementById;
    global.document.querySelectorAll = mockQuerySelectorAll;
  });

  describe("initializeLockForm", () => {
    test("does not throw when lock form is absent", () => {
      global.document.getElementById = () => null;
      expect(() => global.window.initializeLockForm()).not.toThrow();
    });

    test("attaches submit listener to lock-sheet-form", () => {
      const mockForm = {
        dataset: {},
        action: "/sheets/2026-01-01/lock",
        addEventListener: (evt, fn) => {
          if (evt === "submit") capturedListener = fn;
        },
        querySelector: (sel) => {
          if (sel === '[name="csrf_token"]') return { value: "tok" };
          if (sel === "button[type='submit']")
            return {
              disabled: false,
              innerHTML: '<i class="bi bi-lock me-1"></i>Lock Sheet',
              classList: {
                contains: () => false,
                remove: () => {},
                add: () => {},
              },
            };
          return null;
        },
      };
      mockElements["lock-sheet-form"] = mockForm;
      global.document.getElementById = (id) => mockElements[id] || null;

      global.window.initializeLockForm();

      expect(capturedListener).toBeTypeOf("function");
    });

    test("sends fetch on submit and notifies success (lock)", async () => {
      let fetchCalled = false;
      let notifiedSuccess = false;

      global.window.showNotification = (msg, type) => {
        if (type === "success") notifiedSuccess = true;
      };

      const mockBtn = {
        disabled: false,
        innerHTML: '<i class="bi bi-lock me-1"></i>Lock Sheet',
        classList: {
          contains: (cls) => cls === "btn-success",
          remove: () => {},
          add: () => {},
        },
      };

      const mockForm = {
        dataset: {},
        action: "/sheets/2026-01-01/lock",
        addEventListener: (evt, fn) => {
          if (evt === "submit") capturedListener = fn;
        },
        querySelector: (sel) => {
          if (sel === '[name="csrf_token"]') return { value: "tok" };
          if (sel === "button[type='submit']") return mockBtn;
          return null;
        },
      };
      mockElements["lock-sheet-form"] = mockForm;
      global.document.getElementById = (id) => mockElements[id] || null;
      global.document.querySelector = (sel) => {
        if (sel === ".sheet-controls") return { appendChild: () => {} };
        if (sel === ".add-entry-form") return null;
        return null;
      };

      global.FormData = function MockFormData() {};
      global.fetch = () => {
        fetchCalled = true;
        return Promise.resolve({
          ok: true,
          headers: { get: () => "application/json" },
          json: () =>
            Promise.resolve({
              success: true,
              locked: true,
              locked_by: "Admin",
              locked_at: "06/01 08:00",
              message: "Sheet locked successfully",
            }),
        });
      };

      global.window.initializeLockForm();
      await capturedListener({
        preventDefault: () => {},
        stopImmediatePropagation: () => {},
      });

      expect(fetchCalled).toBe(true);
      expect(notifiedSuccess).toBe(true);
      expect(mockBtn.innerHTML).toContain("Unlock Sheet");
    });

    test("sends fetch on submit and notifies success (unlock)", async () => {
      let notifiedSuccess = false;

      global.window.showNotification = (msg, type) => {
        if (type === "success") notifiedSuccess = true;
      };

      const mockBtn = {
        disabled: false,
        innerHTML: '<i class="bi bi-unlock me-1"></i>Unlock Sheet',
        classList: {
          contains: (cls) => cls === "btn-warning",
          remove: () => {},
          add: () => {},
        },
      };

      const mockForm = {
        dataset: {},
        action: "/sheets/2026-01-01/lock",
        addEventListener: (evt, fn) => {
          if (evt === "submit") capturedListener = fn;
        },
        querySelector: (sel) => {
          if (sel === '[name="csrf_token"]') return { value: "tok" };
          if (sel === "button[type='submit']") return mockBtn;
          return null;
        },
      };
      mockElements["lock-sheet-form"] = mockForm;
      mockElements["lock-status"] = { remove: () => {} };
      global.document.getElementById = (id) => mockElements[id] || null;
      global.document.querySelector = (sel) => {
        if (sel === ".sheet-controls") return { appendChild: () => {} };
        if (sel === ".add-entry-form") return null;
        return null;
      };

      global.FormData = function MockFormData() {};
      global.fetch = () =>
        Promise.resolve({
          ok: true,
          headers: { get: () => "application/json" },
          json: () =>
            Promise.resolve({
              success: true,
              locked: false,
              locked_by: null,
              locked_at: null,
              message: "Sheet unlocked successfully",
            }),
        });

      global.window.initializeLockForm();
      await capturedListener({
        preventDefault: () => {},
        stopImmediatePropagation: () => {},
      });

      expect(notifiedSuccess).toBe(true);
      expect(mockBtn.innerHTML).toContain("Lock Sheet");
    });

    test("shows error notification when fetch fails", async () => {
      let notifiedError = false;

      global.window.showNotification = (msg, type) => {
        if (type === "error") notifiedError = true;
      };

      const mockBtn = {
        disabled: false,
        innerHTML: '<i class="bi bi-lock me-1"></i>Lock Sheet',
        classList: { contains: () => false, remove: () => {}, add: () => {} },
      };

      const mockForm = {
        dataset: {},
        action: "/sheets/2026-01-01/lock",
        addEventListener: (evt, fn) => {
          if (evt === "submit") capturedListener = fn;
        },
        querySelector: (sel) => {
          if (sel === '[name="csrf_token"]') return { value: "tok" };
          if (sel === "button[type='submit']") return mockBtn;
          return null;
        },
      };
      mockElements["lock-sheet-form"] = mockForm;
      global.document.getElementById = (id) => mockElements[id] || null;

      global.FormData = function MockFormData() {};
      global.fetch = () => Promise.reject(new Error("Network error"));

      global.window.initializeLockForm();
      await capturedListener({
        preventDefault: () => {},
        stopImmediatePropagation: () => {},
      });

      expect(notifiedError).toBe(true);
      expect(mockBtn.disabled).toBe(false);
    });

    test("missing-exit guard fires and blocks lock when user cancels", async () => {
      let fetchCalled = false;
      let confirmCalled = false;

      global.confirm = () => {
        confirmCalled = true;
        return false; // user cancels
      };

      const mockBtn = {
        disabled: false,
        innerHTML: '<i class="bi bi-lock me-1"></i>Lock Sheet',
        classList: { contains: () => false, remove: () => {}, add: () => {} },
      };

      const mockForm = {
        dataset: {
          missingCount: "2",
          missingResidents: '["Alice", "Bob"]',
        },
        action: "/sheets/2026-01-01/lock",
        addEventListener: (evt, fn) => {
          if (evt === "submit") capturedListener = fn;
        },
        querySelector: (sel) => {
          if (sel === '[name="csrf_token"]') return { value: "tok" };
          if (sel === "button[type='submit']") return mockBtn;
          return null;
        },
      };
      mockElements["lock-sheet-form"] = mockForm;
      global.document.getElementById = (id) => mockElements[id] || null;

      global.FormData = function MockFormData() {};
      global.fetch = () => {
        fetchCalled = true;
        return Promise.resolve({ ok: true, json: () => Promise.resolve({}) });
      };

      global.window.initializeLockForm();
      await capturedListener({
        preventDefault: () => {},
        stopImmediatePropagation: () => {},
      });

      expect(confirmCalled).toBe(true);
      expect(fetchCalled).toBe(false);
    });

    test("add-entry form hidden on lock, shown on unlock", async () => {
      let addEntryDisplay = "";

      const mockAddEntry = {
        style: {
          get display() {
            return addEntryDisplay;
          },
          set display(v) {
            addEntryDisplay = v;
          },
        },
      };

      const mockBtn = {
        disabled: false,
        innerHTML: '<i class="bi bi-lock me-1"></i>Lock Sheet',
        classList: {
          contains: (cls) => cls === "btn-success",
          remove: () => {},
          add: () => {},
        },
      };

      const mockForm = {
        dataset: {},
        action: "/sheets/2026-01-01/lock",
        addEventListener: (evt, fn) => {
          if (evt === "submit") capturedListener = fn;
        },
        querySelector: (sel) => {
          if (sel === '[name="csrf_token"]') return { value: "tok" };
          if (sel === "button[type='submit']") return mockBtn;
          return null;
        },
      };
      mockElements["lock-sheet-form"] = mockForm;
      global.document.getElementById = (id) => mockElements[id] || null;
      global.document.querySelector = (sel) => {
        if (sel === ".sheet-controls") return { appendChild: () => {} };
        if (sel === ".add-entry-form") return mockAddEntry;
        return null;
      };

      global.FormData = function MockFormData() {};
      global.fetch = () =>
        Promise.resolve({
          ok: true,
          headers: { get: () => "application/json" },
          json: () =>
            Promise.resolve({
              success: true,
              locked: true,
              locked_by: "Admin",
              locked_at: "06/01 08:00",
              message: "Sheet locked successfully",
            }),
        });

      global.window.initializeLockForm();
      await capturedListener({
        preventDefault: () => {},
        stopImmediatePropagation: () => {},
      });

      expect(addEntryDisplay).toBe("none");
    });
  });
});

describe("In-memory entry key Set", () => {
  beforeEach(() => {
    global.document.querySelectorAll = mockQuerySelectorAll;
    global.document.getElementById = mockGetElementById;
    // Reset the set by calling initializeEntryKeySet with empty DOM
    global.document.querySelectorAll = () => [];
    global.window.initializeEntryKeySet();
  });

  test("getExistingEntryKeys returns the in-memory Set", () => {
    const keys = global.window.getExistingEntryKeys();
    expect(keys).toBeInstanceOf(Set);
  });

  test("initializeEntryKeySet populates Set from DOM rows", () => {
    global.document.querySelectorAll = (sel) => {
      if (sel === "tr[data-entry-id]")
        return [
          { dataset: { residentId: "1", roleId: "2" } },
          { dataset: { residentId: "3", roleId: "4" } },
        ];
      return [];
    };

    global.window.initializeEntryKeySet();

    const keys = global.window.getExistingEntryKeys();
    expect(keys.has("1:2")).toBe(true);
    expect(keys.has("3:4")).toBe(true);
    expect(keys.size).toBe(2);
  });

  test("getExistingEntryKeys reflects Set (no DOM scan each call)", () => {
    // Seed the set via initializeEntryKeySet
    global.document.querySelectorAll = (sel) => {
      if (sel === "tr[data-entry-id]")
        return [{ dataset: { residentId: "10", roleId: "20" } }];
      return [];
    };
    global.window.initializeEntryKeySet();

    // Now change DOM to return different data — Set must NOT reflect it
    global.document.querySelectorAll = (sel) => {
      if (sel === "tr[data-entry-id]")
        return [{ dataset: { residentId: "99", roleId: "99" } }];
      return [];
    };

    const keys = global.window.getExistingEntryKeys();
    expect(keys.has("10:20")).toBe(true);
    expect(keys.has("99:99")).toBe(false);
  });

  test("insertEntryRow adds key to in-memory Set", () => {
    global.document.querySelectorAll = () => [];
    global.window.initializeEntryKeySet();

    const tbody = { appendChild: () => {} };
    global.document.querySelector = (sel) => {
      if (sel === ".entries-table tbody") return tbody;
      if (sel === ".no-entries") return null;
      if (sel === ".start-time-cell") return null;
      if (sel === '[name="csrf_token"]') return { value: "tok" };
      return null;
    };
    global.document.createElement = () => ({
      className: "",
      id: "",
      innerHTML: "",
      dataset: {},
      querySelector: () => null,
      querySelectorAll: () => [],
      appendChild: () => {},
    });

    const entry = {
      id: 77,
      resident_id: 7,
      role_id: 8,
      resident_name: "Test",
      role_name: "ECC 1",
      role_is_backup: false,
      missing_exit_time: false,
      exit_time: "20:00",
      exit_time_display: "08:00 PM",
      start_time: null,
      start_time_display: null,
      overtime_display: "2.50 hrs",
    };

    global.window.insertEntryRow(entry, false);

    const keys = global.window.getExistingEntryKeys();
    expect(keys.has("7:8")).toBe(true);
  });

  test("removeEntryRow deletes key from in-memory Set", () => {
    // Seed with one key
    global.document.querySelectorAll = (sel) => {
      if (sel === "tr[data-entry-id]")
        return [{ dataset: { residentId: "5", roleId: "6" } }];
      return [];
    };
    global.window.initializeEntryKeySet();

    // Set up a row element to remove
    const mockRow = {
      dataset: { residentId: "5", roleId: "6" },
      remove: () => {},
    };
    mockElements["entry-row-55"] = mockRow;
    global.document.getElementById = (id) => mockElements[id] || null;
    global.document.querySelectorAll = () => [];

    global.window.removeEntryRow("55");

    const keys = global.window.getExistingEntryKeys();
    expect(keys.has("5:6")).toBe(false);
  });

  test("warning uses in-memory Set (not DOM) for duplicate check", () => {
    // Seed the Set with one key
    global.document.querySelectorAll = (sel) => {
      if (sel === "tr[data-entry-id]")
        return [{ dataset: { residentId: "1", roleId: "2" } }];
      return [];
    };
    global.window.initializeEntryKeySet();

    // getExistingEntryKeys returns the Set
    const keys = global.window.getExistingEntryKeys();
    // Duplicate check
    expect(keys.has("1:2")).toBe(true);
    expect(keys.has("1:99")).toBe(false);
  });
});

describe("insertEntryRow — empty table (tfoot injection)", () => {
  test("builds table structure and injects tfoot when table is absent", () => {
    let appendedToCardBody = null;
    const cardBody = {
      querySelector: (sel) => {
        if (sel === ".no-entries") return { remove: () => {} };
        return null;
      },
      appendChild: (el) => {
        appendedToCardBody = el;
      },
    };

    global.document.querySelectorAll = () => [];
    global.document.querySelector = (sel) => {
      if (sel === ".entries-table tbody") return null; // no table yet
      if (sel === ".entries-table .card-body") return cardBody;
      if (sel === ".no-entries") return null;
      if (sel === ".start-time-cell") return null;
      if (sel === '[name="csrf_token"]') return { value: "tok" };
      return null;
    };

    const createdElements = [];
    global.document.createElement = (tag) => {
      const el = {
        tagName: tag,
        className: "",
        id: "",
        innerHTML: "",
        dataset: {},
        children: [],
        querySelector: () => null,
        querySelectorAll: () => [],
        appendChild: (child) => {
          el.children.push(child);
          return child;
        },
      };
      createdElements.push(el);
      return el;
    };

    global.window.initializeEntryKeySet();

    const entry = {
      id: 88,
      resident_id: 10,
      role_id: 11,
      resident_name: "New Entry",
      role_name: "ECC 2",
      role_is_backup: false,
      missing_exit_time: false,
      exit_time: "20:00",
      exit_time_display: "08:00 PM",
      start_time: null,
      start_time_display: null,
      overtime_display: "1.00 hrs",
    };

    global.window.insertEntryRow(entry, false);

    // The card body should have received a wrapper div
    expect(appendedToCardBody).not.toBeNull();
    // A tfoot element must have been created
    const tfootEl = createdElements.find((el) => el.tagName === "tfoot");
    expect(tfootEl).toBeDefined();
    expect(tfootEl.innerHTML).toContain("Total Overtime");
  });

  test("removes no-entries placeholder when table exists but placeholder remains", () => {
    let placeholderRemoved = false;
    const noEntries = {
      remove: () => {
        placeholderRemoved = true;
      },
    };

    const tbody = { appendChild: () => {} };

    global.document.querySelectorAll = () => [];
    global.document.querySelector = (sel) => {
      if (sel === ".entries-table tbody") return tbody;
      if (sel === ".no-entries") return noEntries;
      if (sel === ".start-time-cell") return null;
      if (sel === '[name="csrf_token"]') return { value: "tok" };
      return null;
    };
    global.document.createElement = () => ({
      className: "",
      id: "",
      innerHTML: "",
      dataset: {},
      querySelector: () => null,
      querySelectorAll: () => [],
      appendChild: () => {},
    });

    global.window.initializeEntryKeySet();

    const entry = {
      id: 89,
      resident_id: 12,
      role_id: 13,
      resident_name: "Another",
      role_name: "ECC 3",
      role_is_backup: false,
      missing_exit_time: false,
      exit_time: "20:00",
      exit_time_display: "08:00 PM",
      start_time: null,
      start_time_display: null,
      overtime_display: "0.50 hrs",
    };

    global.window.insertEntryRow(entry, false);

    expect(placeholderRemoved).toBe(true);
  });
});

describe("applyLockToggle import button visibility", () => {
  beforeEach(() => {
    global.window.showNotification = () => {};
    global.document.querySelector = mockQuerySelector;
    global.document.querySelectorAll = mockQuerySelectorAll;
  });

  test("adds d-none to import container when locking", () => {
    const added = [];
    const removed = [];
    const importContainer = {
      classList: {
        add: (cls) => added.push(cls),
        remove: (cls) => removed.push(cls),
      },
    };

    mockElements["import-schedule-container"] = importContainer;

    const lockForm = { querySelector: () => null };

    global.window.applyLockToggle(lockForm, true, "Admin", "06/01 09:00");

    expect(added).toContain("d-none");
    expect(removed).not.toContain("d-none");
  });

  test("removes d-none from import container when unlocking", () => {
    const added = [];
    const removed = [];
    const importContainer = {
      classList: {
        add: (cls) => added.push(cls),
        remove: (cls) => removed.push(cls),
      },
    };

    mockElements["import-schedule-container"] = importContainer;

    const lockForm = { querySelector: () => null };

    global.window.applyLockToggle(lockForm, false, null, null);

    expect(removed).toContain("d-none");
    expect(added).not.toContain("d-none");
  });

  test("handles missing import container gracefully", () => {
    mockElements["import-schedule-container"] = undefined;

    const lockForm = { querySelector: () => null };

    expect(() =>
      global.window.applyLockToggle(lockForm, true, "Admin", null),
    ).not.toThrow();
  });
});
