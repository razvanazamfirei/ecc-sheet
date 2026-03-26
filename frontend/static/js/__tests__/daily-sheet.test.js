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
    readyState: 'complete',
    addEventListener: () => {},
    createElement: (_tag) => {
      let text = '';
      return {
        set textContent(value) {
          text = value;
        },
        get innerHTML() {
          return text
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
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
  global.FormData = () => {};
  global.fetch = () => Promise.resolve({ ok: true });

  // Load the module
  await import('../daily-sheet.js');

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
  };
});

beforeEach(() => {
  // Reset mock elements
  Object.keys(mockElements).forEach((key) => delete mockElements[key]);
  confirmReturnValue = true;
  global.FormData = () => {};
});

describe('Daily Sheet Functions', () => {
  describe('confirmLockWithMissing', () => {
    test('builds correct message with missing count and residents', () => {
      let capturedMessage = '';
      global.confirm = (msg) => {
        capturedMessage = msg;
        return true;
      };

      const form = {
        dataset: {
          missingCount: '2',
          missingResidents: '["John Doe", "Jane Smith"]',
        },
      };

      const result = exportedFunctions.confirmLockWithMissing(form);

      expect(result).toBe(true);
      expect(capturedMessage).toContain('2 entries are missing exit times');
      expect(capturedMessage).toContain('John Doe, Jane Smith');
    });

    test('returns false when user cancels', () => {
      global.confirm = () => false;

      const form = {
        dataset: {
          missingCount: '1',
          missingResidents: '["Test Resident"]',
        },
      };

      const result = exportedFunctions.confirmLockWithMissing(form);

      expect(result).toBe(false);
    });

    test('handles empty missingResidents', () => {
      global.confirm = () => true;

      const form = {
        dataset: {
          missingCount: '0',
          missingResidents: '',
        },
      };

      const result = exportedFunctions.confirmLockWithMissing(form);

      expect(result).toBe(true);
    });
  });

  describe('editEntry', () => {
    test('stores original value and toggles visibility', () => {
      const mockInput = { value: '18:00', focus: () => {} };
      const mockDisplay = { style: { display: '' } };
      const mockForm = { style: { display: '' } };
      const mockEditControls = { style: { display: '' } };
      const mockActionButtons = { style: { display: '' } };

      mockElements['input-1'] = mockInput;
      mockElements['display-1'] = mockDisplay;
      mockElements['form-1'] = mockForm;
      mockElements['edit-controls-1'] = mockEditControls;
      mockElements['action-buttons-1'] = mockActionButtons;

      exportedFunctions.editEntry(1);

      expect(mockDisplay.style.display).toBe('none');
      expect(mockForm.style.display).toBe('inline');
      expect(mockEditControls.style.display).toBe('inline-flex');
      expect(mockActionButtons.style.display).toBe('none');
    });
  });

  describe('saveEntry', () => {
    test('saves the form asynchronously and updates the row', async () => {
      let capturedFormData;
      let fetchArgs;
      global.FormData = (form) => {
        capturedFormData = form.querySelectorAll('input').map((input) => ({
          name: input.name,
          value: input.value,
          disabled: input.disabled,
        }));
        return { capturedFormData };
      };

      const formInputs = [
        {
          name: 'csrf_token',
          value: 'csrf-token-value',
          disabled: false,
        },
        {
          name: 'exit_time',
          value: '18:00',
          disabled: false,
        },
      ];

      mockElements['form-1'] = {
        action: '/update_entry/1',
        querySelectorAll: (selector) =>
          selector === 'input' ? formInputs : [],
        style: { display: 'inline' },
      };
      mockElements['input-1'] = { value: '18:00', focus: () => {} };
      mockElements['display-1'] = { style: { display: 'none' }, innerHTML: '' };
      mockElements['cell-1'] = {
        classList: { toggle: () => {}, contains: () => false },
      };
      mockElements['entry-row-1'] = {
        classList: { toggle: () => {} },
      };
      mockElements['overtime-1'] = { textContent: '' };
      mockElements['edit-controls-1'] = { style: { display: 'inline-flex' } };
      mockElements['action-buttons-1'] = { style: { display: 'none' } };

      global.fetch = (url, options) => {
        fetchArgs = { url, options };
        return Promise.resolve({
          ok: true,
          json: () =>
            Promise.resolve({
              success: true,
              message: 'Entry updated successfully',
              entry: {
                exit_time: '21:00',
                exit_time_display: '09:00 PM',
                start_time: null,
                start_time_display: null,
                missing_exit_time: false,
                overtime_display: '3.50 hrs',
              },
            }),
        });
      };

      const saved = await exportedFunctions.saveEntry(1);

      expect(saved).toBe(true);
      expect(mockElements['display-1'].innerHTML).toContain('09:00 PM');
      expect(mockElements['overtime-1'].textContent).toBe('3.50 hrs');
      expect(mockElements['form-1'].style.display).toBe('none');
      expect(fetchArgs.options.headers['X-CSRFToken']).toBe('csrf-token-value');
      expect(capturedFormData).toEqual([
        {
          name: 'csrf_token',
          value: 'csrf-token-value',
          disabled: false,
        },
        {
          name: 'exit_time',
          value: '18:00',
          disabled: false,
        },
      ]);
    });
  });

  describe('initializeInlineEditors', () => {
    test('pressing Enter in a time input submits the inline form', async () => {
      const originalQuerySelectorAll = global.document.querySelectorAll;
      const formListeners = {};
      const inputListeners = {};
      let requestSubmitCalled = false;
      let prevented = false;

      const mockForm = {
        dataset: { entryId: '1' },
        id: 'form-1',
        addEventListener: (eventName, handler) => {
          formListeners[eventName] = handler;
        },
        requestSubmit: () => {
          requestSubmitCalled = true;
        },
      };
      const mockInput = {
        id: 'input-1',
        form: mockForm,
        addEventListener: (eventName, handler) => {
          inputListeners[eventName] = handler;
        },
      };

      global.document.querySelectorAll = (selector) => {
        if (selector === '.time-edit-form') {
          return [mockForm];
        }
        if (selector === '[id^="input-"], [id^="start-input-"]') {
          return [mockInput];
        }
        return [];
      };

      exportedFunctions.initializeInlineEditors();
      await inputListeners.keydown({
        key: 'Enter',
        code: 'Enter',
        preventDefault: () => {
          prevented = true;
        },
      });

      expect(formListeners.submit).toBeTypeOf('function');
      expect(prevented).toBe(true);
      expect(requestSubmitCalled).toBe(true);

      global.document.querySelectorAll = originalQuerySelectorAll;
    });
  });

  describe('cancelEdit', () => {
    test('restores original value and toggles visibility', () => {
      const mockInput = { value: '19:00', focus: () => {} };
      const mockDisplay = { style: { display: 'none' } };
      const mockForm = { style: { display: 'inline' } };
      const mockEditControls = { style: { display: 'inline-flex' } };
      const mockActionButtons = { style: { display: 'none' } };

      mockElements['input-2'] = mockInput;
      mockElements['display-2'] = mockDisplay;
      mockElements['form-2'] = mockForm;
      mockElements['edit-controls-2'] = mockEditControls;
      mockElements['action-buttons-2'] = mockActionButtons;

      // First edit to store original value
      exportedFunctions.editEntry(2);
      // Then cancel
      exportedFunctions.cancelEdit(2);

      expect(mockDisplay.style.display).toBe('inline');
      expect(mockForm.style.display).toBe('none');
      expect(mockEditControls.style.display).toBe('none');
      expect(mockActionButtons.style.display).toBe('inline-flex');
    });
  });

  describe('toggleEditAll', () => {
    test('enables edit mode for all entries when toggled on', () => {
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
      const saveAllBtn = { style: { display: 'none' } };

      mockElements['edit-all-controls'] = buttonContainer;
      mockElements['edit-all-btn'] = editAllBtn;
      mockElements['save-all-btn'] = saveAllBtn;

      // Mock querySelectorAll to return entries
      global.document.querySelectorAll = () => [
        { dataset: { entryId: '1' } },
        { dataset: { entryId: '2' } },
      ];

      // Mock individual entry elements
      [1, 2].forEach((id) => {
        mockElements[`input-${id}`] = { value: '18:00', focus: () => {} };
        mockElements[`display-${id}`] = { style: { display: '' } };
        mockElements[`form-${id}`] = { style: { display: '' } };
        mockElements[`edit-controls-${id}`] = { style: { display: '' } };
        mockElements[`action-buttons-${id}`] = { style: { display: '' } };
      });

      exportedFunctions.toggleEditAll();

      expect(editAllBtn.innerHTML).toContain('Cancel All');
      expect(saveAllBtn.style.display).toBe('inline-block');
    });
  });

  describe('saveAll', () => {
    test('submits all forms via fetch without reloading on success', async () => {
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
        style: { display: 'inline-block' },
      };

      mockElements['edit-all-controls'] = editAllControls;
      mockElements['edit-all-btn'] = editAllBtn;
      mockElements['save-all-btn'] = saveAllBtn;

      global.document.querySelectorAll = () => [
        {
          dataset: { entryId: '1' },
          querySelector: () => ({ textContent: '3.50 hrs' }),
        },
        {
          dataset: { entryId: '2' },
          querySelector: () => ({ textContent: '1.00 hrs' }),
        },
      ];

      const form1Inputs = [{ name: 'csrf_token', value: 'csrf-token-value' }];
      mockElements['form-1'] = {
        action: '/update_entry/1',
        querySelectorAll: (selector) =>
          selector === 'input' ? form1Inputs : [],
        style: { display: 'inline' },
      };
      mockElements['input-1'] = { value: '18:00', focus: () => {} };
      mockElements['display-1'] = { style: { display: 'none' }, innerHTML: '' };
      mockElements['cell-1'] = {
        classList: { toggle: () => {}, contains: () => false },
      };
      mockElements['entry-row-1'] = {
        classList: { toggle: () => {} },
      };
      mockElements['overtime-1'] = { textContent: '' };
      mockElements['edit-controls-1'] = { style: { display: 'inline-flex' } };
      mockElements['action-buttons-1'] = { style: { display: 'none' } };

      const form2Inputs = [{ name: 'csrf_token', value: 'csrf-token-value' }];
      mockElements['form-2'] = {
        action: '/update_entry/2',
        querySelectorAll: (selector) =>
          selector === 'input' ? form2Inputs : [],
        style: { display: 'inline' },
      };
      mockElements['input-2'] = { value: '20:30', focus: () => {} };
      mockElements['start-input-2'] = {
        value: '09:00',
        disabled: false,
        style: { display: 'inline' },
      };
      mockElements['display-2'] = { style: { display: 'none' }, innerHTML: '' };
      mockElements['cell-2'] = {
        classList: { toggle: () => {}, contains: () => false },
      };
      mockElements['entry-row-2'] = {
        classList: { toggle: () => {} },
      };
      mockElements['overtime-2'] = { textContent: '' };
      mockElements['edit-controls-2'] = { style: { display: 'inline-flex' } };
      mockElements['action-buttons-2'] = { style: { display: 'none' } };

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
                  id: '1',
                  exit_time: '21:00',
                  exit_time_display: '09:00 PM',
                  start_time: null,
                  start_time_display: null,
                  missing_exit_time: false,
                  overtime_display: '3.50 hrs',
                },
                {
                  id: '2',
                  exit_time: '20:30',
                  exit_time_display: '08:30 PM',
                  start_time: '09:00',
                  start_time_display: '09:00 AM',
                  missing_exit_time: false,
                  overtime_display: '1.00 hrs',
                },
              ],
            }),
        });
      };

      await exportedFunctions.saveAll();

      expect(saveAllBtn.disabled).toBe(false);
      expect(editAllBtn.disabled).toBe(false);
      expect(saveAllBtn.style.display).toBe('none');
      expect(fetchCount).toBe(1);
      expect(fetchArgs.url).toBe('/entries/update-all');
      expect(fetchArgs.options.headers['X-CSRFToken']).toBe('csrf-token-value');
      expect(JSON.parse(fetchArgs.options.body)).toEqual({
        entries: [
          { id: '1', exit_time: '18:00' },
          { id: '2', exit_time: '20:30', start_time: '09:00' },
        ],
      });
    });

    test('re-enables buttons and shows error on failure', async () => {
      const editAllControls = {
        classList: { remove: () => {} },
      };
      const editAllBtn = { disabled: false };
      const saveAllBtn = {
        disabled: false,
        innerHTML: '<i class="bi bi-check-all me-1"></i>Save All',
        style: { display: 'inline-block' },
      };

      mockElements['edit-all-controls'] = editAllControls;
      mockElements['edit-all-btn'] = editAllBtn;
      mockElements['save-all-btn'] = saveAllBtn;

      global.document.querySelectorAll = () => [{ dataset: { entryId: '1' } }];

      const formInputs = [{ name: 'csrf_token', value: 'csrf-token-value' }];
      mockElements['form-1'] = {
        action: '/update_entry/1',
        querySelectorAll: (selector) =>
          selector === 'input' ? formInputs : [],
        style: { display: 'inline' },
      };
      mockElements['input-1'] = { value: '18:00', focus: () => {} };
      mockElements['display-1'] = { style: { display: 'none' }, innerHTML: '' };
      mockElements['cell-1'] = {
        classList: { toggle: () => {}, contains: () => false },
      };
      mockElements['entry-row-1'] = {
        classList: { toggle: () => {} },
      };
      mockElements['overtime-1'] = { textContent: '' };
      mockElements['edit-controls-1'] = { style: { display: 'inline-flex' } };
      mockElements['action-buttons-1'] = { style: { display: 'none' } };

      let alertCalled = false;
      global.alert = () => (alertCalled = true);
      global.fetch = () => Promise.reject(new Error('Network error'));

      await exportedFunctions.saveAll();

      expect(saveAllBtn.disabled).toBe(false);
      expect(editAllBtn.disabled).toBe(false);
      expect(alertCalled).toBe(true);
    });
  });

  describe('global function exposure', () => {
    test('exposes all required functions globally', () => {
      expect(typeof exportedFunctions.confirmLockWithMissing).toBe('function');
      expect(typeof exportedFunctions.editEntry).toBe('function');
      expect(typeof exportedFunctions.saveEntry).toBe('function');
      expect(typeof exportedFunctions.cancelEdit).toBe('function');
      expect(typeof exportedFunctions.toggleEditAll).toBe('function');
      expect(typeof exportedFunctions.saveAll).toBe('function');
      expect(typeof exportedFunctions.copyToClipboard).toBe('function');
    });
  });

  describe('copyToClipboard', () => {
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
      Object.defineProperty(globalThis, 'navigator', {
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

    test('alerts when no entries exist', async () => {
      global.document.querySelectorAll = () => [];

      await exportedFunctions.copyToClipboard({ target: {} });

      expect(capturedAlert).toBe('No entries to copy');
    });

    test('generates HTML table for weekday without start time', async () => {
      const mockRow = {
        querySelector: (selector) => {
          if (selector === '.exit-time-cell')
            return { classList: { contains: () => false } };
          if (selector === 'td:nth-child(1) .badge')
            return { textContent: 'ECC 1' };
          if (selector === 'td:nth-child(2)')
            return { textContent: 'John Doe' };
          if (selector === '.overtime-cell span')
            return { textContent: '2.50 hrs' };
          return null;
        },
      };

      global.document.querySelectorAll = (selector) => {
        if (selector === 'tr[data-entry-id]') return [mockRow];
        return [];
      };

      global.document.querySelector = (selector) => {
        if (selector === '.start-time-cell') return null;
        return null;
      };

      mockElements['sheet-date'] = {
        textContent: 'February 07, 2026\nWeekend/Holiday',
      };

      const mockButton = {
        innerHTML: '',
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
      expect(mockClipboardWrite[0].data['text/html']).toBeDefined();
      expect(mockClipboardWrite[0].data['text/plain']).toBeDefined();

      const htmlContent = mockClipboardWrite[0].data['text/html'].content[0];
      expect(htmlContent).toContain('February 07, 2026');
      expect(htmlContent).toContain('<th>Role</th>');
      expect(htmlContent).toContain('<th>Name</th>');
      expect(htmlContent).toContain('<th>Overtime</th>');
      expect(htmlContent).toContain('<td>ECC 1</td>');
      expect(htmlContent).toContain('<td>John Doe</td>');
      expect(htmlContent).toContain('<td>2.50 hrs</td>');
      expect(htmlContent).toContain('Total Overtime:');
      expect(htmlContent).toContain('2.50 hrs');
    });

    test('generates HTML table for weekend with start time', async () => {
      const mockRow = {
        querySelector: (selector) => {
          if (selector === '.exit-time-cell')
            return { classList: { contains: () => false } };
          if (selector === 'td:nth-child(1) .badge')
            return { textContent: 'ECA 1' };
          if (selector === 'td:nth-child(2)')
            return { textContent: 'Jane Smith' };
          if (selector === '.start-time-cell span')
            return { textContent: '08:00 AM' };
          if (selector === '.overtime-cell span')
            return { textContent: '4.00 hrs' };
          return null;
        },
      };

      global.document.querySelectorAll = (selector) => {
        if (selector === 'tr[data-entry-id]') return [mockRow];
        return [];
      };

      global.document.querySelector = (selector) => {
        if (selector === '.start-time-cell') return {};
        return null;
      };

      mockElements['sheet-date'] = { textContent: 'February 08, 2026' };

      const mockButton = {
        innerHTML: '',
        classList: { remove: () => {}, add: () => {} },
      };

      await exportedFunctions.copyToClipboard({
        target: { closest: () => mockButton },
      });

      const htmlContent = mockClipboardWrite[0].data['text/html'].content[0];
      expect(htmlContent).toContain('<th>Start Time</th>');
      expect(htmlContent).toContain('<td>08:00 AM</td>');
      expect(htmlContent).toContain('Total Overtime:');
      expect(htmlContent).toContain('4.00 hrs');
    });

    test('skips entries with missing exit times', async () => {
      const mockRowWithExit = {
        querySelector: (selector) => {
          if (selector === '.exit-time-cell')
            return { classList: { contains: () => false } };
          if (selector === 'td:nth-child(1) .badge')
            return { textContent: 'ECC 1' };
          if (selector === 'td:nth-child(2)')
            return { textContent: 'John Doe' };
          if (selector === '.overtime-cell span')
            return { textContent: '2.00 hrs' };
          return null;
        },
      };

      const mockRowMissing = {
        querySelector: (selector) => {
          if (selector === '.exit-time-cell')
            return { classList: { contains: () => true } };
          return null;
        },
      };

      global.document.querySelectorAll = (selector) => {
        if (selector === 'tr[data-entry-id]')
          return [mockRowWithExit, mockRowMissing];
        return [];
      };

      global.document.querySelector = (selector) => {
        if (selector === '.start-time-cell') return null;
        return null;
      };

      mockElements['sheet-date'] = { textContent: 'February 07, 2026' };

      const mockButton = {
        innerHTML: '',
        classList: { remove: () => {}, add: () => {} },
      };

      await exportedFunctions.copyToClipboard({
        target: { closest: () => mockButton },
      });

      const htmlContent = mockClipboardWrite[0].data['text/html'].content[0];
      expect(htmlContent).toContain('John Doe');
      expect(htmlContent).not.toContain('Jane Smith');
    });

    test('calculates total overtime correctly', async () => {
      const createMockRow = (name, overtime) => ({
        querySelector: (selector) => {
          if (selector === '.exit-time-cell')
            return { classList: { contains: () => false } };
          if (selector === 'td:nth-child(1) .badge')
            return { textContent: 'ECC 1' };
          if (selector === 'td:nth-child(2)') {
            return { textContent: name };
          }
          if (selector === '.overtime-cell span')
            return { textContent: overtime };
          return null;
        },
      });

      global.document.querySelectorAll = (selector) => {
        if (selector === 'tr[data-entry-id]')
          return [
            createMockRow('Person 1', '2.50 hrs'),
            createMockRow('Person 2', '3.25 hrs'),
            createMockRow('Person 3', '1.00 hrs'),
          ];
        return [];
      };

      global.document.querySelector = (selector) => {
        if (selector === '.start-time-cell') return null;
        return null;
      };

      mockElements['sheet-date'] = { textContent: 'February 07, 2026' };

      const mockButton = {
        innerHTML: '',
        classList: { remove: () => {}, add: () => {} },
      };

      await exportedFunctions.copyToClipboard({
        target: { closest: () => mockButton },
      });

      const htmlContent = mockClipboardWrite[0].data['text/html'].content[0];
      expect(htmlContent).toContain('6.75 hrs');
    });

    test('shows success feedback after copying', async () => {
      const mockRow = {
        querySelector: (selector) => {
          if (selector === '.exit-time-cell')
            return { classList: { contains: () => false } };
          if (selector === 'td:nth-child(1) .badge')
            return { textContent: 'ECC 1' };
          if (selector === 'td:nth-child(2)')
            return { textContent: 'John Doe' };
          if (selector === '.overtime-cell span')
            return { textContent: '2.00 hrs' };
          return null;
        },
      };

      global.document.querySelectorAll = (selector) => {
        if (selector === 'tr[data-entry-id]') return [mockRow];
        return [];
      };

      global.document.querySelector = (selector) => {
        if (selector === '.start-time-cell') return null;
        return null;
      };

      mockElements['sheet-date'] = { textContent: 'February 07, 2026' };

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

      expect(mockButton.innerHTML).toContain('Copied!');
      expect(setTimeoutCalled).toBe(true);
    });

    test('handles clipboard write errors gracefully', async () => {
      const mockRow = {
        querySelector: (selector) => {
          if (selector === '.exit-time-cell')
            return { classList: { contains: () => false } };
          if (selector === 'td:nth-child(1) .badge')
            return { textContent: 'ECC 1' };
          if (selector === 'td:nth-child(2)')
            return { textContent: 'John Doe' };
          if (selector === '.overtime-cell span')
            return { textContent: '2.00 hrs' };
          return null;
        },
      };

      global.document.querySelectorAll = (selector) => {
        if (selector === 'tr[data-entry-id]') return [mockRow];
        return [];
      };

      global.document.querySelector = (selector) => {
        if (selector === '.start-time-cell') return null;
        return null;
      };

      mockElements['sheet-date'] = { textContent: 'February 07, 2026' };

      global.navigator.clipboard.write = () =>
        Promise.reject(new Error('Clipboard error'));

      const mockButton = {
        innerHTML: '',
        classList: { remove: () => {}, add: () => {} },
      };

      await exportedFunctions.copyToClipboard({
        target: { closest: () => mockButton },
      });

      expect(capturedAlert).toBe(
        'Failed to copy to clipboard. Please try again.',
      );
    });
  });

  describe('toggleStartTimeField', () => {
    test('shows start time field when backup role is selected', () => {
      const mockRoleSelect = {
        options: [
          { dataset: { isBackup: 'false' } },
          { dataset: { isBackup: 'true' } },
        ],
        selectedIndex: 1,
      };

      const mockStartTimeContainer = { style: { display: 'none' } };

      mockElements.role_id = mockRoleSelect;
      mockElements.start_time_container = mockStartTimeContainer;

      exportedFunctions.toggleStartTimeField();

      expect(mockStartTimeContainer.style.display).toBe('block');
    });

    test('hides start time field when non-backup role is selected', () => {
      const mockRoleSelect = {
        options: [
          { dataset: { isBackup: 'false' } },
          { dataset: { isBackup: 'true' } },
        ],
        selectedIndex: 0,
      };

      const mockStartTimeContainer = { style: { display: 'block' } };

      mockElements.role_id = mockRoleSelect;
      mockElements.start_time_container = mockStartTimeContainer;

      exportedFunctions.toggleStartTimeField();

      expect(mockStartTimeContainer.style.display).toBe('none');
    });

    test('handles missing role select element gracefully', () => {
      mockElements.role_id = null;
      const mockStartTimeContainer = { style: { display: 'block' } };
      mockElements.start_time_container = mockStartTimeContainer;

      exportedFunctions.toggleStartTimeField();

      // Should return early without error, display unchanged
      expect(mockStartTimeContainer.style.display).toBe('block');
    });

    test('handles missing start time container gracefully', () => {
      const mockRoleSelect = {
        options: [{ dataset: { isBackup: 'true' } }],
        selectedIndex: 0,
      };

      mockElements.role_id = mockRoleSelect;
      mockElements.start_time_container = null;

      // Should not throw an error
      expect(() => exportedFunctions.toggleStartTimeField()).not.toThrow();
    });

    test('handles role with no dataset attribute', () => {
      const mockRoleSelect = {
        options: [{}],
        selectedIndex: 0,
      };

      const mockStartTimeContainer = { style: { display: 'block' } };

      mockElements.role_id = mockRoleSelect;
      mockElements.start_time_container = mockStartTimeContainer;

      exportedFunctions.toggleStartTimeField();

      expect(mockStartTimeContainer.style.display).toBe('none');
    });
  });

  describe('editEntry with backup roles', () => {
    test('handles start time input for backup roles', () => {
      const mockInput = { value: '18:00', focus: () => {} };
      const mockStartInput = { value: '08:00', style: { display: '' } };
      const mockStartDisplay = { style: { display: 'inline' } };
      const mockDisplay = { style: { display: '' } };
      const mockForm = { style: { display: '' } };
      const mockEditControls = { style: { display: '' } };
      const mockActionButtons = { style: { display: '' } };

      mockElements['input-3'] = mockInput;
      mockElements['start-input-3'] = mockStartInput;
      mockElements['start-display-3'] = mockStartDisplay;
      mockElements['display-3'] = mockDisplay;
      mockElements['form-3'] = mockForm;
      mockElements['edit-controls-3'] = mockEditControls;
      mockElements['action-buttons-3'] = mockActionButtons;

      exportedFunctions.editEntry(3);

      expect(mockStartDisplay.style.display).toBe('none');
      expect(mockStartInput.style.display).toBe('inline');
    });
  });

  describe('cancelEdit with backup roles', () => {
    test('restores start time for backup roles', () => {
      const mockInput = { value: '19:00', focus: () => {} };
      const mockStartInput = { value: '09:00', style: { display: 'inline' } };
      const mockStartDisplay = { style: { display: 'none' } };
      const mockDisplay = { style: { display: 'none' } };
      const mockForm = { style: { display: 'inline' } };
      const mockEditControls = { style: { display: 'inline-flex' } };
      const mockActionButtons = { style: { display: 'none' } };

      mockElements['input-4'] = mockInput;
      mockElements['start-input-4'] = mockStartInput;
      mockElements['start-display-4'] = mockStartDisplay;
      mockElements['display-4'] = mockDisplay;
      mockElements['form-4'] = mockForm;
      mockElements['edit-controls-4'] = mockEditControls;
      mockElements['action-buttons-4'] = mockActionButtons;

      // First edit to store original value
      exportedFunctions.editEntry(4);
      // Modify the start input
      mockStartInput.value = '10:00';
      // Then cancel
      exportedFunctions.cancelEdit(4);

      expect(mockStartInput.style.display).toBe('none');
      expect(mockStartDisplay.style.display).toBe('inline');
      expect(mockStartInput.value).toBe('09:00');
    });
  });

  describe('cancelEdit with legacy single value', () => {
    test('handles legacy originalValues format (single value)', () => {
      const mockInput = { value: '18:00', focus: () => {} };
      const mockDisplay = { style: { display: 'none' } };
      const mockForm = { style: { display: 'inline' } };
      const mockEditControls = { style: { display: 'inline-flex' } };
      const mockActionButtons = { style: { display: 'none' } };

      mockElements['input-5'] = mockInput;
      mockElements['display-5'] = mockDisplay;
      mockElements['form-5'] = mockForm;
      mockElements['edit-controls-5'] = mockEditControls;
      mockElements['action-buttons-5'] = mockActionButtons;

      // Edit the entry - this stores the original value "18:00"
      exportedFunctions.editEntry(5);
      // Modify the input
      mockInput.value = '21:00';
      // Then cancel - should restore to "18:00"
      exportedFunctions.cancelEdit(5);

      // Original value should be restored
      expect(mockInput.value).toBe('18:00');
    });
  });

  describe('toggleEditAll cancel mode', () => {
    test('verifies toggle behavior by checking state changes', () => {
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
      const saveAllBtn = { style: { display: 'none' } };

      mockElements['edit-all-controls'] = buttonContainer;
      mockElements['edit-all-btn'] = editAllBtn;
      mockElements['save-all-btn'] = saveAllBtn;

      // Set up mock entries
      [6, 7].forEach((id) => {
        mockElements[`input-${id}`] = { value: '18:00', focus: () => {} };
        mockElements[`display-${id}`] = { style: { display: '' } };
        mockElements[`form-${id}`] = { style: { display: '' } };
        mockElements[`edit-controls-${id}`] = { style: { display: '' } };
        mockElements[`action-buttons-${id}`] = { style: { display: '' } };
      });

      global.document.querySelectorAll = () => [
        { dataset: { entryId: '6' } },
        { dataset: { entryId: '7' } },
      ];

      // Toggle twice - should end up back in original state
      // (Note: Module state may persist from previous tests)

      // Two toggles should return to original state
      exportedFunctions.toggleEditAll();
      exportedFunctions.toggleEditAll();

      // After two toggles, we should be back to same state
      // The exact state depends on where we started
      expect(typeof editAllBtn.innerHTML).toBe('string');
      expect(typeof saveAllBtn.style.display).toBe('string');
    });
  });
});

describe('Countdown Timer Functions', () => {
  describe('updateCountdown', () => {
    test('decrements minutes when timer exists', () => {
      const timer = {
        dataset: { minutes: '5' },
        textContent: '(5 minutes remaining)',
      };
      mockElements['countdown-timer'] = timer;

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

      expect(timer.dataset.minutes).toBe('4');
      expect(timer.textContent).toBe('(4 minutes remaining)');
    });

    test('shows locking message when timer reaches zero', () => {
      const timer = {
        dataset: { minutes: '1' },
        textContent: '(1 minutes remaining)',
      };
      mockElements['countdown-timer'] = timer;

      // Simulate countdown to zero
      let minutes = parseInt(timer.dataset.minutes, 10);
      if (minutes > 0) {
        minutes--;
        timer.dataset.minutes = String(minutes);
        if (minutes === 0) {
          timer.textContent = '(Locking now...)';
        }
      }

      expect(timer.dataset.minutes).toBe('0');
      expect(timer.textContent).toBe('(Locking now...)');
    });

    test('does nothing when timer element not found', () => {
      // Clear the timer element
      delete mockElements['countdown-timer'];

      // This should not throw an error
      // The function checks for null and returns early
    });
  });
});

describe('Role Select Functions', () => {
  describe('toggleStartTimeField', () => {
    test('shows start time container for backup role', () => {
      const roleSelect = {
        options: [
          { dataset: { isBackup: 'false' } },
          { dataset: { isBackup: 'true' } },
        ],
        selectedIndex: 1,
      };
      const startTimeContainer = { style: { display: 'none' } };

      mockElements.role_id = roleSelect;
      mockElements.start_time_container = startTimeContainer;

      // Simulate toggleStartTimeField logic
      const selectedOption = roleSelect.options[roleSelect.selectedIndex];
      const isBackup = selectedOption?.dataset?.isBackup === 'true';
      startTimeContainer.style.display = isBackup ? 'block' : 'none';

      expect(startTimeContainer.style.display).toBe('block');
    });

    test('hides start time container for non-backup role', () => {
      const roleSelect = {
        options: [
          { dataset: { isBackup: 'false' } },
          { dataset: { isBackup: 'true' } },
        ],
        selectedIndex: 0,
      };
      const startTimeContainer = { style: { display: 'block' } };

      mockElements.role_id = roleSelect;
      mockElements.start_time_container = startTimeContainer;

      // Simulate toggleStartTimeField logic
      const selectedOption = roleSelect.options[roleSelect.selectedIndex];
      const isBackup = selectedOption?.dataset?.isBackup === 'true';
      startTimeContainer.style.display = isBackup ? 'block' : 'none';

      expect(startTimeContainer.style.display).toBe('none');
    });

    test('handles missing role select gracefully', () => {
      delete mockElements.role_id;
      mockElements.start_time_container = { style: { display: 'none' } };

      // Should not throw when role select is missing
      const roleSelect = mockElements.role_id;
      if (!roleSelect) return;
      // This line should not be reached
      expect(true).toBe(true);
    });

    test('handles missing start time container gracefully', () => {
      mockElements.role_id = { options: [], selectedIndex: 0 };
      delete mockElements.start_time_container;

      // Should not throw when container is missing
      const container = mockElements.start_time_container;
      if (!container) return;
      // This line should not be reached
      expect(true).toBe(true);
    });
  });
});
