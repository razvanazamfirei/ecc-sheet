/**
 * Tests for Daily Sheet Page JavaScript
 */

// Mock DOM elements storage
const mockElements = {};

// Set up DOM mocks
const mockGetElementById = (id) => mockElements[id] || null;
const mockQuerySelectorAll = () => [];

// Set up window mocks
let confirmReturnValue = true;
const mockConfirm = (msg) => confirmReturnValue;
const mockReload = () => {};
const mockAlert = () => {};

// Store functions that will be exported
let exportedFunctions = {};

beforeAll(async () => {
  // Set up global mocks
  global.document = {
    getElementById: mockGetElementById,
    querySelectorAll: mockQuerySelectorAll,
    readyState: "complete",
    addEventListener: () => {},
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
  global.FormData = function () {};
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
  };
});

beforeEach(() => {
  // Reset mock elements
  Object.keys(mockElements).forEach((key) => delete mockElements[key]);
  confirmReturnValue = true;
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
      const mockActionsCell = {
        querySelector: (selector) => {
          if (selector === ".edit-btn") return { style: { display: "" } };
          if (selector === ".save-btn") return { style: { display: "" } };
          if (selector === ".cancel-btn") return { style: { display: "" } };
          if (selector === ".delete-form") return { style: { display: "" } };
          return null;
        },
      };

      mockElements["input-1"] = mockInput;
      mockElements["display-1"] = mockDisplay;
      mockElements["form-1"] = mockForm;
      mockElements["actions-1"] = mockActionsCell;

      exportedFunctions.editEntry(1);

      expect(mockDisplay.style.display).toBe("none");
      expect(mockForm.style.display).toBe("inline");
    });
  });

  describe("saveEntry", () => {
    test("submits the form for the entry", () => {
      let submitted = false;
      const mockForm = { submit: () => (submitted = true) };
      mockElements["form-1"] = mockForm;

      exportedFunctions.saveEntry(1);

      expect(submitted).toBe(true);
    });
  });

  describe("cancelEdit", () => {
    test("restores original value and toggles visibility", () => {
      const mockInput = { value: "19:00", focus: () => {} };
      const mockDisplay = { style: { display: "none" } };
      const mockForm = { style: { display: "inline" } };
      const editBtn = { style: { display: "none" } };
      const saveBtn = { style: { display: "inline-block" } };
      const cancelBtn = { style: { display: "inline-block" } };
      const deleteForm = { style: { display: "none" } };
      const mockActionsCell = {
        querySelector: (selector) => {
          if (selector === ".edit-btn") return editBtn;
          if (selector === ".save-btn") return saveBtn;
          if (selector === ".cancel-btn") return cancelBtn;
          if (selector === ".delete-form") return deleteForm;
          return null;
        },
      };

      mockElements["input-2"] = mockInput;
      mockElements["display-2"] = mockDisplay;
      mockElements["form-2"] = mockForm;
      mockElements["actions-2"] = mockActionsCell;

      // First edit to store original value
      exportedFunctions.editEntry(2);
      // Then cancel
      exportedFunctions.cancelEdit(2);

      expect(mockDisplay.style.display).toBe("inline");
      expect(mockForm.style.display).toBe("none");
      expect(editBtn.style.display).toBe("inline-block");
      expect(saveBtn.style.display).toBe("none");
      expect(cancelBtn.style.display).toBe("none");
      expect(deleteForm.style.display).toBe("inline");
    });
  });

  describe("toggleEditAll", () => {
    test("enables edit mode for all entries when toggled on", () => {
      const editAllBtn = {
        innerHTML: '<i class="bi bi-pencil-square me-1"></i>Edit All',
        classList: {
          remove: () => {},
          add: () => {},
        },
      };
      const saveAllBtn = { style: { display: "none" } };

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
        mockElements[`actions-${id}`] = {
          querySelector: () => ({ style: { display: "" } }),
        };
      });

      exportedFunctions.toggleEditAll();

      expect(editAllBtn.innerHTML).toContain("Cancel All");
      expect(saveAllBtn.style.display).toBe("inline-block");
    });
  });

  describe("saveAll", () => {
    test("submits all forms via fetch and reloads on success", async () => {
      const editAllBtn = { disabled: false };
      const saveAllBtn = {
        disabled: false,
        innerHTML: '<i class="bi bi-check-all me-1"></i>Save All',
      };

      mockElements["edit-all-btn"] = editAllBtn;
      mockElements["save-all-btn"] = saveAllBtn;

      global.document.querySelectorAll = () => [{ dataset: { entryId: "1" } }];

      mockElements["form-1"] = {
        action: "/update_entry/1",
      };

      let fetchCalled = false;
      global.fetch = () => {
        fetchCalled = true;
        return Promise.resolve({ ok: true });
      };

      await exportedFunctions.saveAll();

      expect(saveAllBtn.disabled).toBe(true);
      expect(editAllBtn.disabled).toBe(true);
      expect(saveAllBtn.innerHTML).toContain("Saving");
      expect(fetchCalled).toBe(true);
    });

    test("re-enables buttons and shows error on failure", async () => {
      const editAllBtn = { disabled: false };
      const saveAllBtn = {
        disabled: false,
        innerHTML: '<i class="bi bi-check-all me-1"></i>Save All',
      };

      mockElements["edit-all-btn"] = editAllBtn;
      mockElements["save-all-btn"] = saveAllBtn;

      global.document.querySelectorAll = () => [{ dataset: { entryId: "1" } }];

      mockElements["form-1"] = {
        action: "/update_entry/1",
      };

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
    });
  });
});
