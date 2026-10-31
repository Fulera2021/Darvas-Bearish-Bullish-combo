/**@OnlyCurrentDoc */

/**
 * ============================================================================
 * DARVAS BACKTESTER - PUBLIC CLIENT CONNECTOR (NATIVE GOOGLE APPS SCRIPT LIBRARY)
 * ============================================================================
 */

// ============================================================================
// SIMPLE TRIGGERS
// ============================================================================

/**
 * Triggered automatically when the spreadsheet is opened.
 * Builds the '🚀 Darvas Backtest' menu.
 */
function onOpen(e) {
  if (typeof DarvasBacktestMaster !== 'undefined') {
    try {
      if (typeof DarvasBacktestMaster.onClientOpen === 'function') {
        DarvasBacktestMaster.onClientOpen(e);
      } else {
        DarvasBacktestMaster.onOpen(e);
      }
    } catch (err) {
      buildFallbackMenu();
    }
  } else {
    buildFallbackMenu();
  }
}

// ============================================================================
// MENU COMMANDS & DRAWING BUTTONS (DELEGATED TO DARVASBACKTESTMASTER LIBRARY)
// ============================================================================

/**
 * Run Backtest using data already present in sheet
 */
function runBacktestFromSheet() {
  executeLibraryFunction('runBacktestFromSheet');
}

/**
 * Run Backtest by fetching historical bars & dividends from Yahoo Finance
 */
function runBacktestFromYahooFinance() {
  executeLibraryFunction('runBacktestFromYahooFinance');
}

/**
 * Drawing button alias
 */
function runTest() {
  executeLibraryFunction('runBacktestFromYahooFinance');
}

function runBacktestClient() {
  executeLibraryFunction('runBacktestFromYahooFinance');
}

function executeBacktestEngine() {
  executeLibraryFunction('runBacktestFromYahooFinance');
}

// ============================================================================
// EXECUTIVE VISUAL THEMES
// ============================================================================
function applyThemeNavy() { executeLibraryFunction('applyThemeNavy'); }
function applyThemeIndigo() { executeLibraryFunction('applyThemeIndigo'); }
function applyThemeEmerald() { executeLibraryFunction('applyThemeEmerald'); }
function applyThemeCleanGray() { executeLibraryFunction('applyThemeCleanGray'); }

// ============================================================================
// DISPATCHER & HELPER FUNCTIONS
// ============================================================================

/**
 * Safely calls a function from the DarvasBacktestMaster library with error handling.
 *
 * @param {string} fnName Name of the function to execute in DarvasBacktestMaster
 * @param {Array} [args=[]] Arguments to pass
 */
function executeLibraryFunction(fnName, args) {
  if (typeof DarvasBacktestMaster === 'undefined') {
    showEngineUnavailableAlert();
    return;
  }

  if (typeof DarvasBacktestMaster[fnName] === 'function') {
    try {
      if (args && args.length > 0) {
        return DarvasBacktestMaster[fnName].apply(null, args);
      } else {
        return DarvasBacktestMaster[fnName]();
      }
    } catch (err) {
      SpreadsheetApp.getUi().alert('Execution Error in ' + fnName + ':\n\n' + err.toString());
    }
  } else {
    SpreadsheetApp.getUi().alert("Function '" + fnName + "' not found in DarvasBacktestMaster library.");
  }
}

/**
 * Builds a fallback menu if the DarvasBacktestMaster library is temporarily unavailable.
 */
function buildFallbackMenu() {
  try {
    const ui = SpreadsheetApp.getUi();
    ui.createMenu('🚀 Darvas Backtest')
      .addItem('🌐 Run Backtest (Sync from Yahoo Finance)', 'runBacktestFromYahooFinance')
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
    "⚠️ Backtest Engine Unavailable\n\n" +
    "Unable to connect to the Darvas Backtest Engine at this moment.\n\n" +
    "Please refresh the spreadsheet and try again. If the issue persists, please contact support."
  );
}
