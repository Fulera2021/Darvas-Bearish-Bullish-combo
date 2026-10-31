/**@OnlyCurrentDoc */

/**
 * ============================================================================
 * DARVAS SCANNER - PUBLIC CLIENT CONNECTOR (NATIVE GOOGLE APPS SCRIPT LIBRARY)
 * ============================================================================
 */

// ============================================================================
// SIMPLE TRIGGERS
// ============================================================================

/**
 * Triggered automatically when the spreadsheet is opened.
 * Builds the '⚡ Darvas Scanner' menu and initializes tab validations.
 */
function onOpen(e) {
  if (typeof DarvasMaster !== 'undefined') {
    try {
      DarvasMaster.onOpen(e);
    } catch (err) {
      buildFallbackMenu();
    }
  } else {
    buildFallbackMenu();
  }
}

/**
 * Triggered automatically when any cell or checkbox is edited.
 * Handles GTT transfer, GTT delete, Move to Sold, and Idle Money FIFO deductions.
 */
function onEdit(e) {
  if (typeof DarvasMaster !== 'undefined') {
    try {
      DarvasMaster.onEdit(e);
    } catch (err) {
      console.error('Error in DarvasMaster.onEdit:', err);
    }
  }
}

// ============================================================================
// MENU COMMANDS & DRAWING BUTTONS (DELEGATED TO DARVASMASTER LIBRARY)
// ============================================================================

/**
 * Main Scanner Execution
 */
function runDarvasScanner() {
  executeLibraryFunction('runDarvasScanner');
}

/**
 * Force Fallback Scanner (GoogleFinance Engine)
 */
function runDarvasScannerGoogleFinanceOnly() {
  executeLibraryFunction('runDarvasScannerGoogleFinanceOnly');
}

/**
 * Weekly Automated Saturday 8 AM Trigger
 */
function setupWeeklyTrigger() {
  executeLibraryFunction('setupWeeklyTrigger');
}

/**
 * GTT Tracker Initialization / Refresh
 */
function setupGttTrackerSheet() {
  executeLibraryFunction('setupGttTrackerSheet');
}

/**
 * Auto-populate checkboxes across all tabs
 */
function refreshAllSheetCheckboxes() {
  executeLibraryFunction('refreshAllSheetCheckboxes');
}

/**
 * Clear All GTTs in GTT Tracker (B4:L)
 */
function clearAllGttsMenu() {
  executeLibraryFunction('clearAllGttsMenu');
}

/**
 * Process Idle Money FIFO Sale
 */
function manualTriggerIdleMoneySale() {
  executeLibraryFunction('manualTriggerIdleMoneySale');
}

/**
 * Show Strategy Rules & About Dialog
 */
function showAboutDialog() {
  executeLibraryFunction('showAboutDialog');
}

/**
 * Apply Visual Conditional Formatting & Summary Cards
 */
function applyScannerFormattingRulesMenu() {
  executeLibraryFunction('applyScannerFormattingRulesMenu');
}

// ============================================================================
// DRAWING BUTTON ALIASES
// ============================================================================
function runTest() { runDarvasScanner(); }
function runScanner() { runDarvasScanner(); }
function runScannerClient() { runDarvasScanner(); }
function runDarvasScannerBackupOnly() { runDarvasScannerGoogleFinanceOnly(); }

// ============================================================================
// DISPATCHER & HELPER FUNCTIONS
// ============================================================================

/**
 * Safely calls a function from the DarvasMaster library with error handling.
 *
 * @param {string} fnName Name of the function to execute in DarvasMaster
 * @param {Array} [args=[]] Arguments to pass
 */
function executeLibraryFunction(fnName, args) {
  if (typeof DarvasMaster === 'undefined') {
    showEngineUnavailableAlert();
    return;
  }

  if (typeof DarvasMaster[fnName] === 'function') {
    try {
      if (args && args.length > 0) {
        return DarvasMaster[fnName].apply(null, args);
      } else {
        return DarvasMaster[fnName]();
      }
    } catch (err) {
      SpreadsheetApp.getUi().alert('Execution Error in ' + fnName + ':\n\n' + err.toString());
    }
  } else {
    SpreadsheetApp.getUi().alert("Function '" + fnName + "' not found in DarvasMaster library.");
  }
}

/**
 * Builds a fallback menu if the DarvasMaster library is temporarily unavailable.
 */
function buildFallbackMenu() {
  try {
    const ui = SpreadsheetApp.getUi();
    ui.createMenu('⚡ Darvas Scanner')
      .addItem('▶ Run Scanner Now', 'runDarvasScanner')
      .addToUi();
  } catch (err) {
    // Suppress if onOpen permissions restricted
  }
}

/**
 * Displays a clean, professional error message to end users if connection fails.
 */
function showEngineUnavailableAlert() {
  SpreadsheetApp.getUi().alert(
    "⚠️ Scanner Service Unavailable\n\n" +
    "Unable to connect to the Darvas Strategy Engine at this moment.\n\n" +
    "Please refresh the spreadsheet and try again. If the issue persists, please contact support."
  );
}

