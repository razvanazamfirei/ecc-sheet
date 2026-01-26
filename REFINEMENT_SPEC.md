# ECC Sheet Refinement Specification

**Created:** 2025-12-29 **Status:** Ready for Implementation **Priority:** High

## Executive Summary

This specification outlines refinements to the ECC Sheet system based on
detailed workflow analysis and user requirements. The system is currently in
testing/development phase and requires improvements before production
deployment.

### Key Changes Overview

- Auto-lock workflow with 8 AM warning and 9 AM auto-lock
- Daily email notifications to coordinators
- Improved inline editing with AJAX-based saves
- Import undo functionality with overwrite warnings
- Enhanced validation and error handling
- Missing exit time visual indicators

## Current System Analysis

### Actual Workflow (Not Originally Documented)

- System is NOT used directly by residents
- Different resident acts as daily coordinator each day
- Coordinator enters exit times for entire team from mixed sources (paper,
  messages, verbal)
- Data entry happens the morning after the shift
- Errors often discovered through resident complaints about incorrect overtime
- Manual transcription from CSV exports creates billing errors

### Current Pain Points

1. Time entry/editing process needs polish (page reloads, slow feedback)
2. No automatic enforcement of data entry deadlines
3. Import process creates confusion (no visibility, no undo, overwrites data
   silently)
4. Missing exit times not visually obvious
5. Errors discovered reactively (complaints) rather than proactively
6. Manual transcription to payroll system introduces errors
7. Main concern: System reliability and error handling

## Detailed Requirements

### 1. Auto-Lock Workflow

#### Requirement

Implement automatic sheet locking to enforce data entry deadlines while allowing
admin override.

#### Specification

**Time-Based Locking:**

- Sheet date is yesterday's date (shift that ended earlier today)
- At 08:00 Philadelphia time: Display prominent warning banner
- At 09:00 Philadelphia time: Automatically lock sheet
- Only admins can unlock after auto-lock
- Manual lock still available before auto-lock

**Warning Banner (08:00-09:00):**

```
[!] Warning: This sheet will auto-lock at 09:00 AM (X minutes remaining)
```

- Yellow/orange background
- Countdown timer showing minutes remaining
- Dismissible but reappears on page reload
- Visible above the entries table

**Auto-Lock Behavior:**

- Run scheduled task every minute between 08:00-09:00
- Lock all unlocked sheets for dates before today
- Set `locked = True`, `locked_by = "System Auto-Lock"`,
  `locked_at = current_time`
- Log to audit trail: `LOCK` action with `user = "system"`

**Admin Override:**

- Admins can unlock any sheet at any time
- Unlock button shows who/when it was locked
- Confirmation dialog: "This sheet was auto-locked. Are you sure you want to
  unlock?"
- Log unlock action with admin username

**Implementation Notes:**

- Use background scheduled task (cron job or similar)
- Consider timezone handling carefully (America/New_York)
- Grace period is 1 hour (08:00 warning → 09:00 lock)
- Edge case: If server is down during lock window, catch up on next run

#### Acceptance Criteria

- [ ] Warning banner appears at 08:00 with countdown
- [ ] Sheet auto-locks at 09:00 with system attribution
- [ ] Admins can unlock with confirmation dialog
- [ ] Audit log records auto-lock and admin unlocks
- [ ] Manual lock still works before auto-lock
- [ ] Time calculations respect Philadelphia timezone

---

### 2. Daily Email Notifications

#### Requirement

Send automated daily email at 09:00 (after auto-lock) to coordinator/admin with
sheet status summary.

#### Specification

**Email Schedule:**

- Send at 09:00 Philadelphia time daily
- Triggered after auto-lock process completes
- Send to configured admin email address(es)

**Email Content:**

**Subject:** `ECC Sheet Daily Summary - [Date]`

**Body Structure:**

```
ECC Sheet Daily Summary
Date: [Yesterday's Date]

SHEET STATUS:
✓ Locked at 09:00 (auto-lock)
  or
✗ Not locked (manual intervention needed)

INCOMPLETE ENTRIES:
[List of entries missing exit times, if any]
- Role: ECC 1, Resident: John Doe - MISSING EXIT TIME
- Role: ECA 2, Resident: Jane Smith - MISSING EXIT TIME

SUMMARY STATISTICS:
Total Entries: 15
Complete: 13
Missing Exit Times: 2
Total Overtime Hours: 45.50 hrs

[Link to view sheet]
[Link to reports]
```

**Email Configuration:**

- Use existing `email_service.py` infrastructure
- Configure SMTP settings via environment variables:
  - `SMTP_HOST`
  - `SMTP_PORT`
  - `SMTP_USERNAME`
  - `SMTP_PASSWORD`
  - `SMTP_FROM_EMAIL`
  - `ADMIN_EMAIL` (recipient address)
- Support multiple recipients (comma-separated)
- HTML and plain-text versions

**Error Handling:**

- Log email failures to application log
- Don't block auto-lock if email fails
- Retry once after 5 minutes if initial send fails
- Admin can manually trigger email from UI

**Implementation Notes:**

- Integrate with auto-lock scheduled task
- Query all entries for yesterday's date
- Calculate statistics: total entries, missing exit times, overtime sum
- Use Jinja2 template for email body
- Include deep links to specific sheets

#### Acceptance Criteria

- [ ] Email sent daily at 09:00 to configured admin
- [ ] Email includes locked status, incomplete entries, summary stats
- [ ] Email contains working links to view sheet and reports
- [ ] Email failures logged but don't block auto-lock
- [ ] HTML and plain-text versions render correctly
- [ ] Multiple recipients supported via comma-separated config

---

### 3. Improved Inline Editing with AJAX

#### Requirement

Polish the inline editing experience with instant saves, no page reloads, and
clear visual feedback.

#### Specification

**Current Behavior (Problem):**

- Click time → shows input → click save → full page reload
- Slow feedback, loses scroll position, feels clunky

**New Behavior:**

- Click time → shows input → type → blur or Enter → instant save via AJAX
- No page reload
- Inline success/error indicator
- Optimistic UI update

**Implementation Details:**

**AJAX Save Endpoint:**

```python
@app.route("/api/entries/<int:entry_id>/update_time", methods=["POST"])
def update_entry_time_ajax(entry_id):
    """Update entry exit time via AJAX"""
    # Verify sheet not locked (unless admin)
    # Parse and validate exit time
    # Round to quarter hour
    # Save to database
    # Log audit trail
    # Return JSON: {success: true, overtime_hours: 2.5, exit_time: "19:30"}
```

**Frontend Flow:**

1. User clicks exit time display → input appears
2. User types time and presses Enter or clicks away (blur)
3. JavaScript validates format, rounds to quarter hour
4. Send AJAX POST to `/api/entries/{id}/update_time`
5. Show loading spinner on the cell
6. On success:
   - Update display value without reload
   - Update overtime hours cell
   - Show green checkmark icon for 2 seconds
   - Return to display mode
7. On error:
   - Show red error icon with tooltip
   - Keep input visible for correction
   - Display error message

**Keyboard Shortcuts:**

- Enter: Save current entry
- Escape: Cancel and revert
- Tab: Save and move to next entry's edit mode
- Shift+Tab: Save and move to previous entry

**Visual Feedback:**

- Loading: Small spinner inside time cell
- Success: Green checkmark icon, fade out after 2s
- Error: Red X icon with error tooltip
- Highlight cell border: blue during edit, green on success, red on error

**Save All Button:**

- Keep existing "Edit All" / "Save All" functionality
- Convert to use AJAX instead of form submissions
- Show progress indicator: "Saving 3 of 15..."
- Collect all results and show summary: "Saved 14, Failed 1"

**Error Handling:**

- Network errors: "Connection error. Changes not saved."
- Validation errors: "Invalid time format. Use HH:MM."
- Lock errors: "Sheet is locked. Contact admin to unlock."
- Server errors: "Save failed. Please try again."
- All errors logged to console for debugging

**Mobile Considerations:**

- Larger touch targets (min 44px)
- Blur-to-save works well on mobile (no Enter key)
- Show numeric keyboard for time input
- Success/error indicators visible on small screens

#### Acceptance Criteria

- [ ] Exit time saves via AJAX without page reload
- [ ] Loading, success, error states clearly visible
- [ ] Keyboard shortcuts (Enter, Esc, Tab) work
- [ ] Overtime hours update instantly on save
- [ ] Error messages clear and actionable
- [ ] Save All uses AJAX with progress indicator
- [ ] Works on mobile/tablet (touch-friendly)
- [ ] Scroll position maintained during edits
- [ ] Network errors handled gracefully

---

### 4. Import Improvements

#### Requirement

Add undo functionality and overwrite warnings to address import confusion.

#### Specification

**Current Problems:**

- Can't see what was imported
- Role assignments don't match reality
- Can't undo or modify after import

**Solution: Three-Part Improvement**

#### Part 1: Overwrite Warning

Before import, check for existing entries that would be affected:

**Pre-Import Check:**

```python
def check_import_conflicts(sheet_date, import_data):
    """Check for existing entries that would be affected"""
    conflicts = []
    for item in import_data:
        existing = TimeEntry.query.filter_by(
            date=sheet_date,
            resident_id=item['resident_id'],
            role_id=item['role_id']
        ).first()

        if existing:
            if existing.exit_time:
                # Has exit time - would lose data
                conflicts.append({
                    'type': 'data_loss',
                    'resident': existing.resident.name,
                    'role': existing.role.name,
                    'exit_time': existing.exit_time
                })
            else:
                # No exit time - safe to skip
                conflicts.append({
                    'type': 'duplicate',
                    'resident': existing.resident.name,
                    'role': existing.role.name
                })

    return conflicts
```

**Warning Dialog:**

```
Import Warning

This import would affect existing entries:

DATA LOSS (3):
- ECC 1: John Doe (exit time 19:30 would be lost)
- ECA 2: Jane Smith (exit time 18:45 would be lost)

DUPLICATES (5):
- ECC 3: Bob Jones (entry exists, no exit time)
- PPMC: Alice Chen (entry exists, no exit time)

Options:
[ ] Skip entries with exit times (recommended)
[ ] Overwrite all (data will be lost)
[Cancel] [Continue Import]
```

#### Part 2: Undo Functionality

**Import Transaction Tracking:**

```python
class ImportTransaction(db.Model):
    """Track import operations for undo"""
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now(UTC))
    user = db.Column(db.String(100), nullable=False)
    entries_created = db.Column(db.Integer)
    entries_updated = db.Column(db.Integer)
    entry_ids = db.Column(db.Text)  # JSON list of created entry IDs
    can_undo = db.Column(db.Boolean, default=True)
```

**After Import:**

- Show success message: "Imported 15 entries. [Undo Import]"
- Store import transaction with all created entry IDs
- Undo button visible for 24 hours or until next import
- Undo removes ONLY entries created by that specific import
- Undo not available if entries have been edited since import

**Undo Logic:**

```python
@app.route("/undo_import/<int:transaction_id>", methods=["POST"])
def undo_import(transaction_id):
    """Undo a previous import"""
    transaction = ImportTransaction.query.get_or_404(transaction_id)

    # Check if undo is still possible
    if not transaction.can_undo:
        flash("Cannot undo: entries have been modified", "error")
        return redirect(...)

    # Get all entries created by this import
    entry_ids = json.loads(transaction.entry_ids)
    entries = TimeEntry.query.filter(TimeEntry.id.in_(entry_ids)).all()

    # Check if any have been edited
    for entry in entries:
        if entry.exit_time or entry.updated_at > transaction.timestamp:
            transaction.can_undo = False
            db.session.commit()
            flash("Cannot undo: some entries have been edited", "error")
            return redirect(...)

    # Delete all entries
    for entry in entries:
        db.session.delete(entry)

    # Log the undo
    log_import("Schedule", f"UNDO: Removed {len(entries)} entries from import {transaction.id}")

    transaction.can_undo = False
    db.session.commit()

    flash(f"Import undone: removed {len(entries)} entries", "success")
    return redirect(...)
```

#### Part 3: Visual Import Indicators

Mark imported entries to distinguish from manual entries:

**Database:**

- Add `source` field to TimeEntry: `manual` or `amion_import`
- Default `source = 'manual'` for backward compatibility

**UI:**

- Show small badge next to role name: `[Imported]` or `[↓]` icon
- Tooltip: "Imported from Amion on [date] at [time]"
- Optional filter: "Show only imported" / "Show only manual"

**Implementation Summary:**

1. Before import: Check for conflicts, show warning dialog with options
2. During import: Track transaction with entry IDs, set source='amion_import'
3. After import: Show success with [Undo] button, mark entries with badge
4. Undo available for 24 hours or until entries are edited
5. Audit log tracks import and undo operations

#### Acceptance Criteria

- [ ] Import shows warning if would overwrite entries with data
- [ ] Warning distinguishes data loss vs harmless duplicates
- [ ] Option to skip entries with exit times
- [ ] Undo button appears after successful import
- [ ] Undo removes only imported entries, not edited ones
- [ ] Undo disabled after 24 hours or if entries edited
- [ ] Imported entries visually distinguished (badge/icon)
- [ ] Audit log tracks import and undo operations
- [ ] Import transaction history accessible to admins

---

### 5. Missing Exit Time Validation

#### Requirement

Visual indicators for entries missing exit times to catch incomplete data before
sheet lock.

#### Specification

**Inline Visual Indicators:**

**In Table Row:**

```html
<tr class="entry-missing-data">
  <td><span class="badge bg-secondary">ECC 1</span></td>
  <td>John Doe</td>
  <td class="exit-time-cell missing">
    <span class="text-warning">
      <i class="bi bi-exclamation-triangle-fill"></i>
      Missing exit time
    </span>
  </td>
  <td class="overtime-cell">
    <span class="text-muted">-</span>
  </td>
  <td>...</td>
</tr>
```

**Styling:**

- Row has yellow/orange left border (3px)
- Exit time cell highlighted with warning background
- Warning icon (triangle with exclamation)
- Text: "Missing exit time" in orange/warning color
- Overtime shows "-" instead of "0.00 hrs"

**Summary Banner:** Display at top of entries table when incomplete entries
exist:

```
[!] 3 entries missing exit times

Click to highlight → [John Doe - ECC 1] [Jane Smith - ECA 2] [Bob Jones - PPMC]
```

- Orange/yellow banner above table
- Clickable resident names scroll to and highlight that entry
- Dismissible but reappears on reload
- Count updates dynamically as times are filled in
- Disappears when all times entered

**Email Integration:** Include in daily email (see Email Notifications section):

```
INCOMPLETE ENTRIES (3):
- ECC 1: John Doe - MISSING EXIT TIME
- ECA 2: Jane Smith - MISSING EXIT TIME
- PPMC: Bob Jones - MISSING EXIT TIME
```

**Lock Behavior:**

- Do NOT block lock if times are missing
- Show confirmation dialog:

  ```
  Warning: 3 entries are missing exit times

  These residents will not receive overtime credit:
  - John Doe (ECC 1)
  - Jane Smith (ECA 2)

  Lock anyway?
  [Cancel] [Lock Sheet]
  ```

- Admins can choose to lock despite missing data
- Log lock action notes incomplete entries

**CSV Export:**

- Missing exit times show as empty cell (not "00:00" or "-")
- Overtime shows as blank or "N/A"
- Consider adding "Data Complete" column: Yes/No

#### Implementation Notes

- Check `exit_time IS NULL` in query
- Apply CSS classes dynamically
- JavaScript for clickable summary links
- Count updates via AJAX after inline saves

#### Acceptance Criteria

- [ ] Entries with missing exit times have visual indicators (border, icon,
      text)
- [ ] Summary banner shows count and clickable names
- [ ] Banner dismissible but reappears on reload
- [ ] Lock shows confirmation if incomplete data
- [ ] Email includes list of incomplete entries
- [ ] CSV export handles missing times appropriately
- [ ] Visual indicators work on mobile/tablet
- [ ] Count updates dynamically after AJAX saves

---

### 6. Enhanced Error Handling

#### Requirement

Graceful error handling to address main production concern (system reliability).

#### Specification

**Error Handling Strategy:**

#### Frontend Error Handling

**AJAX Request Errors:**

```javascript
async function saveEntry(entryId, exitTime) {
  try {
    const response = await fetch(`/api/entries/${entryId}/update_time`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify({ exit_time: exitTime }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.message || "Save failed");
    }

    const data = await response.json();
    return { success: true, data };
  } catch (error) {
    if (error.name === "TypeError" && !navigator.onLine) {
      return {
        success: false,
        error: "No internet connection. Please check your network.",
      };
    }

    return {
      success: false,
      error: error.message || "An unexpected error occurred. Please try again.",
    };
  }
}
```

**User-Friendly Error Messages:**

- Network: "Connection lost. Check your internet and try again."
- Timeout: "Request timed out. The server may be slow."
- Locked Sheet: "This sheet is locked. Contact an admin to unlock."
- Validation: "Invalid time format. Please use HH:MM (e.g., 19:30)."
- Permission: "You don't have permission to edit this entry."
- Server Error: "Something went wrong. Please try again or contact support."

**Error Display:**

- Toast notifications (non-blocking, auto-dismiss after 5s)
- Critical errors: Modal dialog with clear action buttons
- Form validation errors: Inline under field with red border
- AJAX errors: Icon + tooltip on the edited cell

#### Backend Error Handling

**Structured Error Responses:**

```python
from flask import jsonify

class APIError(Exception):
    """Base API error with user-friendly message"""
    def __init__(self, message, status_code=400, payload=None):
        super().__init__()
        self.message = message
        self.status_code = status_code
        self.payload = payload

@app.errorhandler(APIError)
def handle_api_error(error):
    """Return JSON error response"""
    response = {
        'success': False,
        'error': error.message,
        'type': error.__class__.__name__
    }
    if error.payload:
        response['details'] = error.payload

    logger.error(f"API Error: {error.message}", extra={'payload': error.payload})
    return jsonify(response), error.status_code

@app.errorhandler(500)
def handle_internal_error(error):
    """Handle unexpected server errors"""
    logger.error(f"Internal Server Error: {str(error)}", exc_info=True)

    return jsonify({
        'success': False,
        'error': 'An unexpected error occurred. The issue has been logged.',
        'type': 'InternalServerError'
    }), 500
```

**Database Error Handling:**

```python
from sqlalchemy.exc import IntegrityError, OperationalError

@app.route("/api/entries/<int:entry_id>/update_time", methods=["POST"])
def update_entry_time(entry_id):
    try:
        entry = TimeEntry.query.get_or_404(entry_id)

        # Check if sheet is locked
        daily_sheet = DailySheet.query.filter_by(date=entry.date).first()
        if daily_sheet and daily_sheet.locked and not is_admin():
            raise APIError("Sheet is locked. Contact admin to unlock.", 403)

        # Validate and parse time
        exit_time_str = request.json.get('exit_time')
        if not exit_time_str:
            raise APIError("Exit time is required", 400)

        try:
            exit_time = datetime.strptime(exit_time_str, '%H:%M').time()
        except ValueError:
            raise APIError("Invalid time format. Use HH:MM (e.g., 19:30)", 400)

        # Save
        entry.exit_time = exit_time
        db.session.commit()

        # Log audit
        log_update("TimeEntry", entry.id, {"exit_time": exit_time_str})

        return jsonify({
            'success': True,
            'exit_time': exit_time_str,
            'overtime_hours': entry.overtime_hours
        })

    except IntegrityError as e:
        db.session.rollback()
        logger.error(f"Database integrity error: {str(e)}")
        raise APIError("Data validation error. Please refresh and try again.", 409)

    except OperationalError as e:
        db.session.rollback()
        logger.error(f"Database operational error: {str(e)}")
        raise APIError("Database connection error. Please try again.", 503)

    except Exception as e:
        db.session.rollback()
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise APIError("An unexpected error occurred. Please try again.", 500)
```

**Logging Strategy:**

```python
import logging
from logging.handlers import RotatingFileHandler

def setup_logging():
    """Configure application logging"""

    # Console handler (for development)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_formatter)

    # File handler (for production)
    file_handler = RotatingFileHandler(
        'logs/ecc_sheet.log',
        maxBytes=10485760,  # 10MB
        backupCount=10
    )
    file_handler.setLevel(logging.WARNING)
    file_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(pathname)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(file_formatter)

    # Error file handler (errors only)
    error_handler = RotatingFileHandler(
        'logs/ecc_sheet_errors.log',
        maxBytes=10485760,
        backupCount=10
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(file_formatter)

    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.addHandler(error_handler)

    return logger
```

**Health Check Endpoint:**

```python
@app.route("/health")
def health_check():
    """System health check for monitoring"""
    try:
        # Check database connection
        db.session.execute("SELECT 1")

        # Check disk space (for SQLite)
        import shutil
        disk_usage = shutil.disk_usage(app.instance_path)
        free_space_gb = disk_usage.free / (1024**3)

        if free_space_gb < 1:  # Less than 1GB free
            logger.warning(f"Low disk space: {free_space_gb:.2f}GB free")

        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'disk_space_gb': f"{free_space_gb:.2f}"
        }), 200

    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e)
        }), 503
```

#### Acceptance Criteria

- [ ] Frontend shows user-friendly error messages (no stack traces)
- [ ] Network errors detected and handled
- [ ] Backend returns structured JSON errors
- [ ] All exceptions logged with context
- [ ] Database errors don't crash the app
- [ ] Health check endpoint available
- [ ] Log rotation configured (max 10MB per file)
- [ ] Separate error log for critical issues
- [ ] CSRF errors handled gracefully
- [ ] 500 errors don't expose internal details

---

### 7. Responsive Design Improvements

#### Requirement

Optimize for desktop (primary) and phone (secondary) usage.

#### Specification

**Desktop Experience (Primary):**

- Current layout works well
- Maintain table-based display
- Keep inline editing
- Optimize for mouse + keyboard

**Phone Experience:**

**Responsive Breakpoints:**

- Desktop: ≥992px (default)
- Tablet: 768px - 991px
- Phone: <768px

**Phone Optimizations (<768px):**

1. **Navigation:**

   - Collapse to hamburger menu
   - Full-width dropdowns
   - Larger touch targets (min 44px)

2. **Daily Sheet Table:**
   - Switch to card-based layout (not table)
   - One entry per card
   - Vertical stacking of fields

```html
<!-- Phone Layout -->
<div class="entry-card">
  <div class="entry-header">
    <span class="badge bg-secondary">ECC 1</span>
    <span class="resident-name">John Doe</span>
  </div>
  <div class="entry-body">
    <div class="field">
      <label>Exit Time:</label>
      <span class="value" onclick="editEntry(...)">19:30</span>
    </div>
    <div class="field">
      <label>Overtime:</label>
      <span class="value">2.50 hrs</span>
    </div>
  </div>
  <div class="entry-actions">
    <button class="btn btn-sm">Edit</button>
    <button class="btn btn-sm">Delete</button>
  </div>
</div>
```

3. **Add Entry Form:**

   - Full-width fields
   - Vertical stacking
   - Native mobile time picker
   - Sticky submit button at bottom

4. **Reports:**

   - Responsive table → horizontal scroll with fixed first column
   - Or switch to card layout
   - Export buttons remain accessible

5. **Time Input:**
   - Use native `<input type="time">` (shows OS time picker)
   - 15-minute step enforced
   - Larger input fields (min 44px height)

**Touch Optimizations:**

- Increase button sizes to 44x44px minimum
- Add padding around clickable elements
- Reduce hover-dependent interactions
- Show tooltips on tap (not hover)
- Prevent accidental clicks (confirmation for destructive actions)

**Performance (Mobile):**

- Lazy load historical sheets
- Minimize page size (already using Vite bundling)
- Avoid heavy JavaScript operations
- Use CSS transforms for animations

**Testing:**

- Test on iPhone Safari (primary)
- Test on Android Chrome (secondary)
- Use Chrome DevTools responsive mode
- Test on actual devices before production

#### Acceptance Criteria

- [ ] Desktop layout unchanged and optimized
- [ ] Phone shows card-based layout for entries (<768px)
- [ ] All buttons minimum 44x44px touch targets
- [ ] Native time picker works on mobile
- [ ] Navigation collapses to hamburger on phone
- [ ] Reports readable and exportable on phone
- [ ] No horizontal scrolling (except data tables)
- [ ] Tested on iOS Safari and Android Chrome
- [ ] Forms usable on phone with on-screen keyboard
- [ ] Loading states clear on slow mobile connections

---

### 8. Database Backup & Recovery

#### Requirement

Implement backup strategy to address reliability concerns.

#### Specification

**Automated Backups:**

**Daily Backup Script:**

```bash
#!/bin/bash
# backup_database.sh

BACKUP_DIR="/var/backups/ecc_sheet"
DB_PATH="/path/to/instance/ecc_sheet.db"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/ecc_sheet_$TIMESTAMP.db"

# Create backup directory if doesn't exist
mkdir -p "$BACKUP_DIR"

# Copy database (SQLite supports hot backups)
cp "$DB_PATH" "$BACKUP_FILE"

# Compress backup
gzip "$BACKUP_FILE"

# Delete backups older than 30 days
find "$BACKUP_DIR" -name "ecc_sheet_*.db.gz" -mtime +30 -delete

# Log backup
echo "$(date): Backup created: $BACKUP_FILE.gz" >> "$BACKUP_DIR/backup.log"
```

**Backup Schedule:**

- Daily at 02:00 (via cron)
- Before major operations (migrations, imports)
- On-demand via admin UI

**Cron Configuration:**

```cron
# Daily backup at 2 AM
0 2 * * * /path/to/backup_database.sh

# Weekly backup to remote storage (optional)
0 3 * * 0 rsync -av /var/backups/ecc_sheet/ user@remote:/backups/ecc_sheet/
```

**Backup UI (Admin):**

Add to admin menu:

```
Admin > Database > Backups
- [Create Backup Now]
- List of backups with timestamp and size
- [Restore] button (with confirmation)
- [Download] button
```

**Restore Procedure:**

```python
@app.route("/admin/restore_backup", methods=["POST"])
@admin_required
def restore_backup():
    """Restore database from backup"""
    backup_file = request.form.get('backup_file')

    # Validate backup file
    if not backup_file or '..' in backup_file:
        flash("Invalid backup file", "error")
        return redirect(url_for('backups'))

    backup_path = os.path.join(BACKUP_DIR, backup_file)
    if not os.path.exists(backup_path):
        flash("Backup file not found", "error")
        return redirect(url_for('backups'))

    try:
        # Create pre-restore backup
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        current_backup = f"{BACKUP_DIR}/pre_restore_{timestamp}.db"
        shutil.copy(DB_PATH, current_backup)

        # Restore from backup
        if backup_path.endswith('.gz'):
            # Decompress first
            import gzip
            with gzip.open(backup_path, 'rb') as f_in:
                with open(DB_PATH, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
        else:
            shutil.copy(backup_path, DB_PATH)

        # Log restore
        log_action("Database", None, "RESTORE",
                   f"Restored from {backup_file} by {get_current_user()}")

        flash(f"Database restored from {backup_file}", "success")
        flash(f"Pre-restore backup saved as pre_restore_{timestamp}.db", "info")

    except Exception as e:
        logger.error(f"Restore failed: {str(e)}")
        flash(f"Restore failed: {str(e)}", "error")

    return redirect(url_for('backups'))
```

**Export Feature (Already Exists):**

- CSV export for reports
- Consider full database export (SQL dump)
- JSON export for programmatic access

**Backup Best Practices:**

- Store backups on different disk/server
- Test restore procedure monthly
- Keep 30 days of daily backups
- Keep 12 months of monthly backups
- Document restore procedure

#### Acceptance Criteria

- [ ] Daily automated backups at 2 AM
- [ ] Backup script logs successes and failures
- [ ] Old backups automatically deleted (30+ days)
- [ ] Admin UI shows backup list with dates/sizes
- [ ] Manual backup button works
- [ ] Restore creates pre-restore backup
- [ ] Restore procedure documented
- [ ] Backups tested monthly
- [ ] Remote backup storage configured (optional)
- [ ] Backup monitoring/alerts (optional)

---

## Additional Improvements

### 9. Code Quality & Maintainability

**Logging Enhancements:**

- Structured logging with context
- Separate logs for errors, audit trail, and application events
- Log rotation to prevent disk fill

**Configuration Management:**

- Validate all environment variables on startup
- Fail fast with clear error messages if config missing
- Document all configuration options

**Testing:**

- Unit tests for overtime calculation edge cases
- Integration tests for import/undo workflow
- End-to-end tests for critical paths (entry → lock → report)

**Documentation:**

- Admin guide for common operations
- User guide for daily coordinators
- Troubleshooting guide
- API documentation (if external integrations planned)

### 10. CSV Export Improvements

Based on "manual transcription errors" pain point:

**Enhanced CSV Format:**

- Include all fields payroll system needs
- Standardized date format
- Clear column headers
- Remove ambiguity (e.g., empty vs 0.00 for overtime)

**Template System:**

```python
# Allow admin to configure CSV template
CSV_TEMPLATES = {
    'payroll': ['Date', 'Resident Name', 'Epic ID', 'Role', 'Exit Time', 'Overtime Hours'],
    'analysis': ['Date', 'Resident', 'Role', 'Exit Time', 'Cutoff Time', 'Overtime', 'Notes']
}
```

**Direct Integration (Future):**

- API endpoint for payroll system to fetch data
- Webhook to push data when sheet locked
- OAuth/API key authentication

### 11. Audit Trail Enhancements

Since audit log is only used "when there's a problem":

**Better Search/Filter:**

- Date range filter
- Search by resident name
- Search by user who made change
- Filter by sheet date (not just audit timestamp)

**Diff View:**

- Show before/after values side-by-side
- Highlight changes in red/green
- Link to current entry state

**Export Audit Log:**

- CSV export for compliance
- Date range selection
- Include all details

---

## Implementation Phases

### Phase 1: Core Workflow (Week 1)

Priority: Critical

1. Auto-lock workflow (8 AM warning, 9 AM lock)
2. Missing exit time visual indicators
3. Enhanced error handling
4. Database backup script

**Deliverables:**

- Auto-lock scheduled task
- Warning banner component
- Admin unlock with confirmation
- Inline visual indicators for missing times
- Structured error responses (frontend + backend)
- Daily backup cron job
- Admin backup UI

**Testing:**

- Test auto-lock timing (mock different times)
- Test admin override
- Test warning displays
- Test error scenarios (network, validation, server)
- Test backup creation and restore

### Phase 2: Email & Communication (Week 2)

Priority: High

1. Daily email notification system
2. SMTP configuration
3. Email templates (HTML + plain text)
4. Manual email trigger

**Deliverables:**

- Email service integration
- Daily email scheduled task
- Email template (summary + incomplete entries)
- Email configuration UI
- Email send logs

**Testing:**

- Test email delivery
- Test with missing SMTP config
- Test multiple recipients
- Test HTML and plain-text rendering
- Test link functionality in emails

### Phase 3: UX Improvements (Week 3)

Priority: High

1. AJAX-based inline editing
2. Keyboard shortcuts
3. Loading/success/error states
4. Save All with progress indicator

**Deliverables:**

- AJAX save endpoint
- Updated frontend JavaScript
- Visual feedback components
- Progress indicator for bulk saves
- Mobile-optimized time inputs

**Testing:**

- Test AJAX saves (success and error paths)
- Test keyboard shortcuts
- Test concurrent edits
- Test mobile time picker
- Test Save All with errors

### Phase 4: Import Improvements (Week 4)

Priority: Medium

1. Overwrite warning system
2. Import transaction tracking
3. Undo functionality
4. Visual import indicators

**Deliverables:**

- Pre-import conflict detection
- Warning dialog
- ImportTransaction model + migration
- Undo endpoint
- Import badges/icons
- Import history UI

**Testing:**

- Test conflict detection accuracy
- Test undo with various scenarios
- Test undo timeout (24 hours)
- Test undo with edited entries
- Test import badges display

### Phase 5: Polish & Deployment (Week 5)

Priority: Medium

1. Responsive design improvements
2. CSV export enhancements
3. Documentation
4. Production deployment

**Deliverables:**

- Mobile card layout
- Touch-optimized buttons
- Enhanced CSV templates
- Admin guide
- User guide
- Deployment checklist
- Health monitoring setup

**Testing:**

- Cross-browser testing (Chrome, Firefox, Safari)
- Mobile device testing (iOS, Android)
- Performance testing with realistic data
- End-to-end workflow testing
- Security review

---

## Technical Architecture

### Database Changes

**New Tables:**

```sql
-- Import transaction tracking
CREATE TABLE import_transactions (
    id INTEGER PRIMARY KEY,
    date DATE NOT NULL,
    timestamp DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    user VARCHAR(100) NOT NULL,
    entries_created INTEGER,
    entries_updated INTEGER,
    entry_ids TEXT,  -- JSON array
    can_undo BOOLEAN DEFAULT 1,
    INDEX idx_date (date),
    INDEX idx_timestamp (timestamp)
);
```

**Modified Tables:**

```sql
-- Add source tracking to time_entries
ALTER TABLE time_entries ADD COLUMN source VARCHAR(20) DEFAULT 'manual';

-- Add email configuration (or use env vars)
CREATE TABLE system_config (
    key VARCHAR(100) PRIMARY KEY,
    value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Migrations:**

- Create migration for import_transactions table
- Create migration for time_entries.source column
- Backfill existing entries with source='manual'

### API Endpoints

**New Endpoints:**

```
POST   /api/entries/<id>/update_time       - AJAX time update
GET    /api/sheets/<date>/status         - Sheet status (locked, complete)
POST   /api/import/<date>/check          - Pre-import conflict check
POST   /api/import/<date>/undo           - Undo import transaction
GET    /api/backups                      - List available backups
POST   /api/backups/create               - Create manual backup
POST   /api/backups/restore              - Restore from backup
GET    /health                           - Health check endpoint
```

**Modified Endpoints:**

- Update `/schedule/<date>/import` to track transactions
- Update `/sheet/<date>/lock` to check completeness

### Scheduled Tasks

**Cron Jobs:**

```cron
# Auto-lock check (every minute 08:00-09:00)
* 8-9 * * * /path/to/check_autolock.py

# Daily email (09:05)
5 9 * * * /path/to/send_daily_email.py

# Daily backup (02:00)
0 2 * * * /path/to/backup_database.sh

# Health check (every 5 minutes)
*/5 * * * * curl -f http://localhost:5000/health || echo "Health check failed"
```

**Task Implementation:**

- Use system cron (simple, reliable)
- Alternative: APScheduler (Python-based)
- Log all task executions
- Alert on failures

### Environment Configuration

**New Variables:**

```bash
# Email Configuration
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=user@example.com
SMTP_PASSWORD=app_specific_password
SMTP_FROM_EMAIL=noreply@example.com
ADMIN_EMAIL=admin@example.com,coordinator@example.com

# Auto-lock Configuration
AUTO_LOCK_WARNING_TIME=08:00
AUTO_LOCK_TIME=09:00
TIMEZONE=America/New_York

# Backup Configuration
BACKUP_DIR=/var/backups/ecc_sheet
BACKUP_RETENTION_DAYS=30

# Monitoring
HEALTH_CHECK_ENABLED=true
```

### Logging Configuration

**Log Files:**

```
logs/
├── ecc_sheet.log           # All application logs
├── ecc_sheet_errors.log    # Errors only
├── scheduled_tasks.log     # Cron job logs
└── email.log               # Email sending logs
```

**Log Levels:**

- DEBUG: Development only
- INFO: Normal operations (saves, locks, imports)
- WARNING: Potential issues (missing config, retries)
- ERROR: Failures (email send failed, database error)
- CRITICAL: System-level issues (database unreachable)

---

## Testing Strategy

### Unit Tests

**Test Coverage:**

- Overtime calculation (edge cases, overnight shifts)
- Time rounding (always round up to 15 min)
- Auto-lock logic (timezone handling)
- Import conflict detection
- Undo eligibility checks
- Email template generation

**Example Tests:**

```python
def test_overtime_overnight_shift():
    """Test overnight shift overtime calculation"""
    role = Role(cutoff_hour=17, cutoff_minute=30)
    entry = TimeEntry(
        role=role,
        exit_time=time(2, 30)  # 2:30 AM
    )
    assert entry.overtime_hours == 9.0  # 17:30 to 02:30 next day

def test_import_conflict_detection():
    """Test import detects existing entries with data"""
    # Setup existing entry with exit time
    # Run import check
    # Assert conflict detected with type='data_loss'

def test_undo_eligibility():
    """Test undo disabled after edit"""
    # Create import transaction
    # Edit one of the imported entries
    # Assert can_undo = False
```

### Integration Tests

**Test Scenarios:**

- Full workflow: Import → Edit → Lock → Email → Report
- Error recovery: Failed save → Retry → Success
- Concurrent edits: Multiple users editing same sheet
- Auto-lock timing: Sheet locks at exactly 9 AM
- Backup/restore: Create backup → Modify data → Restore → Verify

### End-to-End Tests

**Critical Paths:**

1. **Daily Coordinator Workflow:**

   - Navigate to today's sheet
   - Import from Amion
   - Fill in missing exit times
   - Lock sheet
   - Verify email sent

2. **Admin Override:**

   - Auto-locked sheet
   - Admin unlocks
   - Edit entry
   - Re-lock
   - Verify audit log

3. **Error Scenario:**

   - Enter invalid time
   - See error message
   - Correct time
   - Save successfully
   - Verify overtime calculated

4. **Report Generation:**
   - Generate 30-day report
   - Filter by resident
   - Export CSV
   - Verify data accuracy

### User Acceptance Testing

**Test Cases for Coordinators:**

- Can import schedule without confusion
- Can easily fill in exit times
- Understands visual indicators for missing data
- Can lock sheet when complete
- Receives helpful error messages

**Test Cases for Admins:**

- Can unlock locked sheets
- Can undo incorrect imports
- Can access audit trail
- Can generate and export reports
- Can manage residents and roles

### Load Testing

**Scenarios:**

- 100 entries on one sheet (max expected)
- 50 concurrent users
- Bulk save of 50 entries
- Import with 30 entries
- Report covering 1 year of data

**Performance Targets:**

- Page load: <2 seconds
- AJAX save: <500ms
- Import: <5 seconds for 30 entries
- Report generation: <3 seconds for 30 days
- Database backup: <10 seconds

---

## Security Considerations

### Authentication & Authorization

**Current State:**

- Environment-based authentication (USER_NAME)
- Admin list (ADMIN_USERS)
- No password/session management

**Recommendations for Production:**

- Integrate with institutional SSO (SAML, OAuth)
- Use reverse proxy authentication (e.g., Apache mod_auth)
- Session management with secure cookies
- CSRF protection (already implemented)

### Data Protection

**Sensitive Data:**

- Resident names and EPIC IDs
- Work hours (potentially sensitive)
- Email addresses (if stored)

**Protection Measures:**

- HTTPS only in production
- Encrypt database backups
- Access logging (audit trail)
- Role-based access control

**Compliance:**

- HIPAA considerations (if resident data is PHI)
- FERPA (educational records)
- Retention policies

### Input Validation

**Already Implemented:**

- CSRF tokens on all forms
- SQL injection protection (SQLAlchemy ORM)
- XSS protection (Jinja2 auto-escaping)

**Enhancements:**

- Rate limiting on API endpoints
- Input sanitization for resident names
- File upload restrictions (if added)
- API authentication (if external access)

---

## Deployment Checklist

### Pre-Deployment

- [ ] All Phase 1-5 features implemented and tested
- [ ] Database migrations tested and documented
- [ ] Backup/restore procedure tested
- [ ] Environment variables documented
- [ ] SMTP credentials configured
- [ ] Cron jobs scheduled and tested
- [ ] Logs directory created with correct permissions
- [ ] Health check endpoint verified
- [ ] Security review completed
- [ ] User documentation written

### Deployment Steps

1. **Backup Production Data:**

   - Create full database backup
   - Export current data to CSV
   - Document current state

2. **Deploy Code:**

   - Pull latest code to production server
   - Install Python dependencies: `uv sync`
   - Install Node dependencies: `bun install`
   - Build frontend assets: `bun run build`

3. **Database Migration:**

   - Backup database again
   - Run migrations: `uv run flask --app backend.app db upgrade`
   - Verify migration success

4. **Configuration:**

   - Update environment variables (.env file)
   - Test SMTP configuration
   - Verify admin users list
   - Check timezone settings

5. **Scheduled Tasks:**

   - Install cron jobs
   - Test auto-lock script manually
   - Test backup script manually
   - Test email script manually

6. **Testing:**

   - Run health check: `curl http://localhost:5000/health`
   - Test authentication
   - Test admin features
   - Test daily coordinator workflow
   - Test email delivery

7. **Monitoring:**
   - Set up log monitoring
   - Configure disk space alerts
   - Set up uptime monitoring
   - Document support procedures

### Post-Deployment

- [ ] Monitor logs for errors (first 48 hours)
- [ ] Verify first auto-lock works correctly
- [ ] Verify first daily email sends successfully
- [ ] Verify backup runs successfully
- [ ] Collect user feedback
- [ ] Address any issues promptly
- [ ] Schedule one-week and one-month reviews

---

## Success Metrics

### Functional Metrics

- **Data Quality:**

  - % of sheets with complete data (target: >95%)
  - % of entries with exit times (target: >98%)
  - Overtime calculation accuracy (target: 100%)

- **Workflow Efficiency:**

  - Time to complete daily entry (target: <10 min)
  - % of sheets locked by 9 AM (target: >90%)
  - Number of unlocks required (target: <5%)

- **System Reliability:**
  - Uptime (target: >99.5%)
  - Successful backups (target: 100%)
  - Successful emails sent (target: >95%)
  - Error rate (target: <1% of operations)

### User Satisfaction

- **Coordinator Feedback:**

  - Ease of use rating (target: >4/5)
  - Time savings vs previous method
  - Error reduction vs previous method

- **Admin Feedback:**

  - Admin tool usefulness (target: >4/5)
  - Report quality (target: >4/5)
  - Audit trail usefulness when needed

- **Resident Feedback:**
  - Overtime accuracy (target: >95% satisfaction)
  - Dispute resolution time
  - Trust in system

### Business Impact

- **Payroll Accuracy:**

  - Reduction in transcription errors
  - Time saved in payroll processing
  - Dispute resolution time reduction

- **Operational Efficiency:**
  - Time saved per sheet entry
  - Reduction in manual data handling
  - Faster report generation

---

## Risk Mitigation

### Risk: Auto-lock causes data loss

**Mitigation:**

- Clear warning at 8 AM
- 1-hour grace period
- Admin can unlock
- Backup before lock
- Audit trail of locks

**Contingency:**

- Admin unlock procedure
- Restore from backup if needed
- Manual CSV import fallback

### Risk: Email delivery failures

**Mitigation:**

- Retry logic (1 retry after 5 min)
- Log all send attempts
- Manual trigger available
- Monitor email logs

**Contingency:**

- Admin checks dashboard manually
- Notification system (future)
- Fallback to SMS/Slack (future)

### Risk: Import undo used maliciously

**Mitigation:**

- Audit log tracks undo operations
- Undo disabled after edits
- 24-hour time limit
- Admin review of audit trail

**Contingency:**

- Restore from daily backup
- Manual data correction
- Review audit trail for patterns

### Risk: Database corruption

**Mitigation:**

- Daily automated backups
- Pre-operation backups (migrations, restores)
- SQLite integrity checks
- Separate backup storage

**Contingency:**

- Restore from latest backup
- Manual data re-entry (last resort)
- Contact support/DBA

### Risk: Poor user adoption

**Mitigation:**

- User training sessions
- Clear documentation
- Responsive support
- Iterative improvements based on feedback

**Contingency:**

- Extended parallel testing
- More training
- Simplified workflows
- Temporary manual processes

---

## Future Enhancements (Post-Launch)

### Phase 6: Advanced Features (Month 2-3)

1. **Notification System:**

   - Slack/Teams integration
   - SMS alerts for missing entries
   - Push notifications (mobile app)

2. **Advanced Reporting:**

   - Trend analysis (overtime by role, resident, time period)
   - Predictive analytics (forecast overtime)
   - Comparative reports (year-over-year)
   - Data visualization (charts, graphs)

3. **Mobile App:**

   - Native iOS/Android app
   - Offline mode with sync
   - Push notifications
   - Quick entry mode

4. **Payroll Integration:**

   - Direct API integration with payroll system
   - Automated data push on sheet lock
   - OAuth authentication
   - Error handling and retry logic

5. **Advanced Admin Tools:**

   - Bulk edit mode
   - Data import/export (Excel, JSON)
   - Role assignment templates
   - Schedule comparison (Amion vs actual)

6. **User Management:**
   - Self-service password reset (if not using SSO)
   - User profiles with preferences
   - Permission granularity (beyond admin/user)
   - Activity tracking per user

### Phase 7: Compliance & Analytics (Month 4-6)

1. **Compliance Dashboard:**

   - Duty hour tracking
   - ACGME reporting
   - Violation alerts
   - Historical compliance trends

2. **Advanced Analytics:**

   - Machine learning for anomaly detection
   - Workload balancing insights
   - Coverage gap identification
   - Resident wellness metrics

3. **Integration Ecosystem:**
   - Calendar integration (Google, Outlook)
   - HR system integration
   - Scheduling software API
   - Business intelligence tools (Tableau, Power BI)

---

## Appendix

### A. Configuration Reference

**Complete Environment Variables:**

```bash
# Application
SECRET_KEY=<generate-random-32-char-string>
FLASK_ENV=production
DATABASE_URL=sqlite:///instance/ecc_sheet.db
TIMEZONE=America/New_York

# Authentication
USER_NAME=Admin
ADMIN_USERS=Admin,John Doe,Jane Smith

# Email
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USE_TLS=true
SMTP_USERNAME=user@example.com
SMTP_PASSWORD=app_specific_password
SMTP_FROM_EMAIL=noreply@ecc-sheet.example.com
ADMIN_EMAIL=admin@example.com,coordinator@example.com

# Auto-lock
AUTO_LOCK_WARNING_TIME=08:00
AUTO_LOCK_TIME=09:00

# Backup
BACKUP_DIR=/var/backups/ecc_sheet
BACKUP_RETENTION_DAYS=30

# Monitoring
HEALTH_CHECK_ENABLED=true
LOG_LEVEL=INFO

# Amion Integration
AMION_BASE_URL=http://www.amion.com/cgi-bin/ocs
AMION_LOCATION=upennane
AMION_REPORT_ID=619

# Role Cutoff Defaults
DEFAULT_CUTOFF_HOUR=17
DEFAULT_CUTOFF_MINUTE=30
```

### B. Useful SQL Queries

**Find incomplete entries:**

```sql
SELECT
    te.date,
    r.name as resident,
    ro.name as role
FROM time_entries te
JOIN residents r ON te.resident_id = r.id
JOIN roles ro ON te.role_id = ro.id
WHERE te.exit_time IS NULL
ORDER BY te.date DESC, ro.display_order;
```

**Overtime by resident (last 30 days):**

```sql
SELECT
    r.name,
    COUNT(te.id) as shifts,
    SUM(CASE
        WHEN te.exit_time IS NOT NULL THEN
            -- Overtime calculation logic here
            0  -- Placeholder
        ELSE 0
    END) as total_overtime
FROM residents r
LEFT JOIN time_entries te ON r.id = te.resident_id
WHERE te.date >= DATE('now', '-30 days')
GROUP BY r.id
ORDER BY total_overtime DESC;
```

**Recent audit trail:**

```sql
SELECT
    timestamp,
    user,
    action,
    entity_type,
    details
FROM audit_logs
ORDER BY timestamp DESC
LIMIT 50;
```

### C. Troubleshooting Guide

**Problem: Auto-lock didn't run**

_Symptoms:_ Sheet not locked at 9 AM

_Checks:_

1. Check cron job: `crontab -l | grep autolock`
2. Check script logs: `tail -f logs/scheduled_tasks.log`
3. Verify timezone: `timedatectl` or `date`
4. Check server time: `date` should match expected time

_Solutions:_

- Restart cron: `sudo service cron restart`
- Run script manually: `/path/to/check_autolock.py`
- Check script permissions: `chmod +x check_autolock.py`

---

**Problem: Email not sending**

_Symptoms:_ No email received at 9 AM

_Checks:_

1. Check email logs: `tail -f logs/email.log`
2. Test SMTP: `python -c "import smtplib; ..."`
3. Verify credentials: Check .env file
4. Check spam folder

_Solutions:_

- Verify SMTP settings (host, port, TLS)
- Check firewall: Port 587 outbound allowed?
- Use app-specific password (Gmail)
- Check email queue: `mailq` (if using local MTA)

---

**Problem: AJAX save not working**

_Symptoms:_ Time update requires page reload

_Checks:_

1. Check browser console for JavaScript errors
2. Check network tab for failed requests
3. Verify CSRF token present
4. Check API endpoint response

_Solutions:_

- Clear browser cache
- Check CSRF token expiration
- Verify endpoint URL correct
- Check server logs for API errors

---

**Problem: Import creates duplicates**

_Symptoms:_ Same resident appears multiple times for same roles/date

_Checks:_

1. Check import logs in audit trail
2. Query database for duplicates:
   ```sql
   SELECT date, resident_id, role_id, COUNT(*)
   FROM time_entries
   GROUP BY date, resident_id, role_id
   HAVING COUNT(*) > 1;
   ```

_Solutions:_

- Use undo import feature
- Manually delete duplicates via admin UI
- Check import conflict detection working
- Report bug with import data

---

### D. User Guide Outline

**For Daily Coordinators:**

1. **Accessing the System**

   - URL and login
   - Navigation overview

2. **Daily Workflow**

   - Importing schedule from Amion
   - Filling in exit times
   - Using inline editing
   - Keyboard shortcuts
   - Locking the sheet

3. **Handling Errors**

   - Missing exit times (visual indicators)
   - Incorrect times (how to edit)
   - Undo import if needed
   - When to contact admin

4. **Best Practices**
   - Enter data before 9 AM
   - Double-check overtime calculations
   - Watch for warning banners
   - Review email summary

**For Admins:**

1. **Admin Features**

   - Managing residents
   - Configuring roles
   - Unlocking sheets
   - Accessing audit trail

2. **Reports**

   - Generating overtime reports
   - Filtering by resident/date
   - Exporting to CSV
   - Sending via email

3. **Maintenance**

   - Database backups
   - Restoring from backup
   - Reviewing audit logs
   - Troubleshooting common issues

4. **Configuration**
   - Environment variables
   - Email settings
   - Auto-lock timing
   - User permissions

---

## Document History

| Version | Date       | Author  | Changes                                                   |
| ------- | ---------- | ------- | --------------------------------------------------------- |
| 1.0     | 2025-12-29 | Initial | Complete refinement specification based on user interview |

---

## Approval & Sign-Off

**Stakeholder Review:**

- [ ] Daily Coordinator Representative
- [ ] Admin/Program Coordinator
- [ ] IT/Infrastructure Team
- [ ] Compliance/Legal (if required)

**Technical Review:**

- [ ] Lead Developer
- [ ] Database Administrator
- [ ] Security Team
- [ ] Operations Team

**Final Approval:**

- [ ] Project Sponsor
- [ ] Department Head

**Approved to Proceed:** **\*\*\*\***\_**\*\*\*\*** Date: \***\*\_\*\***
