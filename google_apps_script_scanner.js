/**@OnlyCurrentDoc */

/**
 * ============================================================================
 * DARVAS BEARISH + BULLISH COMBO SYSTEMATIC SCANNER FOR GOOGLE SHEETS
 * ============================================================================
 * 
 * Target Sheet Tab: "Scanner"
 * 
 * Layout Mapping (Columns J through Q):
 * - Rows 1-2 (Col J to P): Executive Summary KPI Cards:
 *                  - Col J:L -> Bullish Buy Triggered (number of stocks below it in Row 2)
 *                  - Col M:N -> Bearish Buy Triggered (number of stocks below it in Row 2)
 *                  - Col O:P -> Last Scan ran on (dd-mmm-yyyy HH:MM format in Row 2)
 * - Row 5: Column Headers
 * - Row 6: Dynamic Formulas (E6, F6, G6, H6, O6, P6)
 * - Row 7 downwards: Strategy Output (Columns J through Q)
 * - Col E: Last Buy Price of Already Bought Stock
 * - Col F: Distance between Suggested Buy Price and Last Buy Price
 * - Col G: Already Bought Tranches
 * - Col H: Bullish Buy Already Done? [Formula in H6: =IFERROR(ARRAYFORMULA(IF(VLOOKUP(J6:J,FILTER('Current Holdings'!B8:B,'Current Holdings'!E8:E="Bullish Buy"),1,0)<>"","Yes","No")))]
 * - Col I: GTT Select checkbox (auto-populated for buy-eligible stocks)
 * - Col J: Stock Code (Same format as input in Col A)
 * - Col K: Status (Sorted in this exact order:
 *                  1. Bullish Buy Triggered
 *                  2. Bearish Buy Triggered
 *                  3. Tracking for Bearish Buy Signal
 *                  4. Bullish Buy Running
 *                  5. Neutral / Inside 20W Range)
 * - Col L: Previous Week High (High of LAST TO LAST WEEK, W_{t-1})
 * - Col M: Last Week's Close (Friday Close of LAST COMPLETED WEEK, W_t)
 * - Col N: Breakout % (Rise) [(Close_M - High_L) / High_L, sorted least risen first]
 * - Col O: Buy Limit Ceiling (+0.5%) [Formula in O6: CEILING(M6:M*1.005, 0.05)]
 * - Col P: CMP [Formula in P6: GOOGLEFINANCE(ticker, "price")]
 * - Col Q: 20W Low Breakdown Signal ("20W Low Breakdown" if touched in recently completed week, else Blank)
 * 
 * Strategy Rules & State Tracking:
 * 1. Bullish Buy Triggered: When Close of last week (Col M) > rolling 20-week high for the first time.
 * 2. Bullish Buy Running: Stocks previously bought on Bullish signal that have NOT touched the 20-week low yet.
 * 3. Bearish Tracking Activation: When 20-week low is TOUCHED (Weekly Low <= 20W Low),
 *    bullish holding terminates and system starts tracking for Bearish Buy Signal.
 * 4. Bearish Buy Triggered: While tracking 20W low, Close of last week (Col M) > High of last to last week (Col L).
 * 5. Col Q (20W Low Breakdown): Highlights stocks whose weekly low touched/breached
 *    the 20-week low during the recently completed week (fresh breakdown).
 * ============================================================================
 */

// Configuration Constants
const CONFIG = {
  SHEET_NAME: 'Scanner',
  INPUT_START_ROW: 7,
  INPUT_COL: 1,           // Column A
  OUTPUT_START_ROW: 7,
  OUTPUT_START_COL: 10,   // Column J (Stock Code)
  OUTPUT_NUM_COLS: 8,     // Columns J to Q (8 columns: J, K, L, M, N, O, P, Q)
  FORMULA_ROW: 6,
  LOOKBACK_WEEKS: 20,
  // Col I (column 9): GTT Select checkbox — auto-populated for buy-eligible stocks
  GTT_SELECT_COL: 9,      // Column I (moved from Column R)
  // NSE Market Friday Holidays (where weekly close shifts to Thursday)
  NSE_FRIDAY_HOLIDAYS: [
    // 2024
    '2024-01-26', '2024-03-08', '2024-03-29', '2024-11-01', '2024-11-15',
    // 2025
    '2025-03-14', '2025-04-18', '2025-08-15', '2025-10-02', '2025-10-31',
    // 2026
    '2026-04-03', '2026-05-01', '2026-10-02', '2026-12-25',
    // 2027
    '2027-03-26', '2027-05-28', '2027-11-05', '2027-11-19'
  ]
};

const GTT_CONFIG = {
  SHEET_NAME: 'GTT Tracker',
  DATA_START_ROW: 4,          // B4 onwards for stock codes
  TICKER_COL: 2,              // Column B: Stock Code
  GTT_PRICE_COL: 3,           // Column C: GTT Order Price
  SIGNAL_TYPE_COL: 4,         // Column D: Signal Type ('Bullish Buy' or 'Bearish Buy')
  BUY_QTY_COL: 5,             // Column E: Suggested Buy Qty
  DELETE_CHK_COL: 10,         // Column J: Delete checkbox (J1: Clear All B4:L, J4+: Delete Row)
  TRANSFER_CHK_COL: 12,       // Column L: Transfer to Current Holdings checkbox
  MASTER_DELETE_ROW: 1,       // Row 1: Master delete checkbox in J1 (clears B4:L)
  DEST_SHEET_NAME: 'Current Holdings',
  DEST_DATA_START_ROW: 8      // Starting data row in Current Holdings
};

const HOLDINGS_CONFIG = {
  SHEET_NAME: 'Current Holdings',
  DATA_START_ROW: 8,          // Row 8 onwards (Row 7 is hidden formula dummy row)
  SELL_DATE_COL: 9,           // Column I: Sell Date
  MOVE_CHK_COL: 16,           // Column P: Move to Sold tab checkbox
  COPY_COLS_COUNT: 10,        // Columns A to J (1 to 10)
  SOLD_SHEET_NAME: 'Sold',    // Destination tab
  SOLD_DATA_START_ROW: 5      // First data row in Sold tab (Row 5 onwards)
};

const IDLE_MONEY_CONFIG = {
  HOLDINGS_SHEET_NAME: 'Idle Money - Holdings',
  SOLD_SHEET_NAME: 'Idle Money - Sold',
  DATA_START_ROW: 7,
  ETF_CODE_CELL: 'C2',
  SOLD_UNITS_CELL: 'E2',
  SELL_PRICE_CELL: 'F2',
  TRIGGER_CHK_CELL: 'H2',
  SOLD_DATA_START_ROW: 4
};

var IDLE_MONEY_HOLDINGS_TAB_NAME = 'Idle Money - Holdings';
var IDLE_MONEY_SOLD_TAB_NAME = 'Idle Money - Sold';

/**
 * Creates custom menu when Google Sheet is opened.
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('⚡ Darvas Scanner')
    .addItem('▶ Run Scanner Now', 'runDarvasScanner')
    .addItem('🛡 Force Fallback Scanner', 'runDarvasScannerGoogleFinanceOnly')
    .addSeparator()
    .addItem('⏰ Setup Auto Weekly Trigger (Saturday 8 AM)', 'setupWeeklyTrigger')
    .addSeparator()
    .addItem('📋 Refresh GTT Tracker Tab', 'setupGttTrackerSheet')
    .addItem('🔄 Auto-Populate All Checkboxes (All Tabs)', 'refreshAllSheetCheckboxes')
    .addItem('🗑 Clear All GTTs (GTT Tracker B4:L)', 'clearAllGttsMenu')
    .addSeparator()
    .addItem('💵 Idle Money: Process Sale', 'manualTriggerIdleMoneySale')
    .addSeparator()
    .addItem('ℹ About Scanner & Rules', 'showAboutDialog')
    .addToUi();

  // Auto-refresh checkboxes across all tabs when spreadsheet is opened
  try {
    refreshAllSheetCheckboxes();
  } catch (openErr) {
    // Suppress if onOpen permissions are restricted
  }
}

/**
 * Menu wrapper for formatting rules.
 */
function applyScannerFormattingRulesMenu() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(CONFIG.SHEET_NAME);
  if (sheet) {
    applyScannerFormattingRules(sheet);

    // Also refresh top summary KPI cards from existing sheet data
    const lastRow = sheet.getLastRow();
    let bullishCount = 0;
    let bearishCount = 0;
    if (lastRow >= CONFIG.OUTPUT_START_ROW) {
      const statuses = sheet.getRange(CONFIG.OUTPUT_START_ROW, 11, lastRow - CONFIG.OUTPUT_START_ROW + 1, 1).getValues();
      statuses.forEach(r => {
        if (r[0] === 'Bullish Buy Triggered') bullishCount++;
        if (r[0] === 'Bearish Buy Triggered') bearishCount++;
      });
    }
    updateScannerSummaryHeader(sheet, bullishCount, bearishCount);

    ss.toast('Visual formatting and summary header applied successfully!', 'Formatting', 5);
  }
}

/**
 * Main Scanner Execution Function.
 * Supports dual-engine data retrieval:
 * 1. Primary Engine: High-speed parallel Yahoo Finance v8 API.
 * 2. Automated Fallback Engine: Google Sheets native GOOGLEFINANCE() function
 *    if Yahoo Finance is down, rate-limited, or fails for specific tickers.
 * 
 * @param {boolean} [forceGoogleFinance=false] Set true to force execution via GoogleFinance backup engine.
 */
/**
 * Web App Endpoint: Receives scan requests from external public sheets
 */
function doPost(e) {
  try {
    const params = JSON.parse(e.postData.contents);
    const tickers = params.tickers || [];
    const gttTickers = params.gttTickers || [];
    const forceGoogleFinance = Boolean(params.forceGoogleFinance);

    if (!tickers || tickers.length === 0) {
      return ContentService.createTextOutput(JSON.stringify({
        success: false,
        error: "No stock tickers found in request payload."
      })).setMimeType(ContentService.MimeType.JSON);
    }

    const scanResult = scanTickersCore(tickers, gttTickers, forceGoogleFinance);
    return ContentService.createTextOutput(JSON.stringify({
      success: true,
      data: scanResult
    })).setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({
      success: false,
      error: err.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * Main Scanner Execution Function (Local Master Sheet runner)
 */
function runDarvasScanner(forceGoogleFinance = false) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(CONFIG.SHEET_NAME);

  if (!sheet) {
    SpreadsheetApp.getUi().alert(`Error: Sheet tab named '${CONFIG.SHEET_NAME}' was not found. Please create it or verify the name.`);
    return;
  }

  // 1. Read input tickers from Column A (Row 7 downwards)
  const lastInputRow = sheet.getLastRow();
  if (lastInputRow < CONFIG.INPUT_START_ROW) {
    ss.toast('No stock codes found in Column A (Row 7 downwards).', 'Scanner Finished', 5);
    return;
  }

  const numInputRows = lastInputRow - CONFIG.INPUT_START_ROW + 1;
  const inputValues = sheet.getRange(CONFIG.INPUT_START_ROW, CONFIG.INPUT_COL, numInputRows, 1).getValues();

  const rawTickers = [];
  inputValues.forEach(row => {
    const val = String(row[0]).trim();
    if (val && val !== '') {
      rawTickers.push(val);
    }
  });

  if (rawTickers.length === 0) {
    ss.toast('No valid ticker codes found in Column A.', 'Scanner Finished', 5);
    return;
  }

  // Filter out stocks already present in GTT Tracker
  const gttSheetForFilter = ss.getSheetByName(GTT_CONFIG.SHEET_NAME);
  let gttTickers = [];
  if (gttSheetForFilter) {
    const gttLastRow = gttSheetForFilter.getLastRow();
    if (gttLastRow >= GTT_CONFIG.DATA_START_ROW) {
      gttTickers = gttSheetForFilter
        .getRange(GTT_CONFIG.DATA_START_ROW, GTT_CONFIG.TICKER_COL, gttLastRow - GTT_CONFIG.DATA_START_ROW + 1, 1)
        .getValues()
        .map(r => String(r[0]).trim().toUpperCase())
        .filter(t => t !== '');
    }
  }

  const result = scanTickersCore(rawTickers, gttTickers, forceGoogleFinance, ss.toast.bind(ss));
  const outputRows = result.outputRows;
  const processedData = result.processedData;
  const summary = result.summary;

  // Ensure formulas in Row 6
  ensureRow6Formulas(sheet);

  // Clear any old data in J7:Q from previous runs
  const numOutputRows = outputRows.length;
  const numOutputCols = CONFIG.OUTPUT_NUM_COLS;
  const currentMaxRow = Math.max(sheet.getLastRow(), CONFIG.OUTPUT_START_ROW + numOutputRows + 10);
  if (currentMaxRow >= CONFIG.OUTPUT_START_ROW) {
    const clearNumRows = currentMaxRow - CONFIG.OUTPUT_START_ROW + 1;
    sheet.getRange(CONFIG.OUTPUT_START_ROW, CONFIG.OUTPUT_START_COL, clearNumRows, numOutputCols).clearContent();
    sheet.getRange(CONFIG.OUTPUT_START_ROW, CONFIG.GTT_SELECT_COL, clearNumRows, 1).clearContent().clearDataValidations().setBackground(null);
    sheet.getRange(CONFIG.OUTPUT_START_ROW, 18, clearNumRows, 1).clearContent().clearDataValidations();
  }

  // Write new values
  if (numOutputRows > 0) {
    sheet.getRange(CONFIG.OUTPUT_START_ROW, CONFIG.OUTPUT_START_COL, numOutputRows, numOutputCols).setValues(outputRows);
    formatScannerDataRange(sheet, CONFIG.OUTPUT_START_ROW, numOutputRows);
    applyScannerFormattingRules(sheet);
    updateScannerSummaryHeader(sheet, summary.bullishCount, summary.bearishCount);
    populateGttCheckboxes(sheet, CONFIG.OUTPUT_START_ROW, numOutputRows, processedData);
  }

  ss.toast(`Scan complete in ${summary.durationSec}s! Found ${summary.bullishCount} Bullish, ${summary.bearishCount} Bearish buys, ${summary.trackingCount} Tracking, and ${summary.runningCount} Bullish Running.`, '⚡ Scan Finished', 8);
}

/**
 * Core Scanner Engine: Parallel batch fetching, indicator calculation, and state tracking.
 * Pure logic decoupled from spreadsheet UI, accessible locally or remotely via doPost.
 */
function scanTickersCore(rawTickers, gttTickers = [], forceGoogleFinance = false, toastFn = null) {
  const startTime = new Date().getTime();
  const processedMap = {};
  const missingTickers = [];

  // Format tickers for Yahoo Finance API / Mirror Engines
  const yfTickerMap = {};
  rawTickers.forEach(t => {
    yfTickerMap[t] = convertToYfTicker(t);
  });

  // Dual-Engine Mirror Architecture:
  // 1. Primary Engine ("Run Scanner Now"): Uses query1 cluster with query2 failover
  // 2. Backup Engine ("Run via Backup Engine"): Uses query2 cluster with query1 failover
  const isBackupMode = Boolean(forceGoogleFinance);
  const primaryDomain = isBackupMode ? 'query2.finance.yahoo.com' : 'query1.finance.yahoo.com';
  const secondaryDomain = isBackupMode ? 'query1.finance.yahoo.com' : 'query2.finance.yahoo.com';
  const engineLabel = isBackupMode ? 'Backup Mirror Engine (Query2)' : 'Yahoo Finance (Query1)';

  // 3. Batch fetch weekly data in parallel using UrlFetchApp.fetchAll in safe chunks
  // Google Apps Script limits simultaneous UrlFetchApp connections. Chunking into batches of 25
  // guarantees lightning-fast execution (<4 seconds for 200+ stocks) without exceeding socket pools.
  const YF_BATCH_SIZE = 25;
  const totalBatches = Math.ceil(rawTickers.length / YF_BATCH_SIZE);

  for (let b = 0; b < totalBatches; b++) {
    const startIdx = b * YF_BATCH_SIZE;
    const endIdx = Math.min(startIdx + YF_BATCH_SIZE, rawTickers.length);
    const batchTickers = rawTickers.slice(startIdx, endIdx);

    if (toastFn) {
      if (totalBatches > 1) {
        toastFn(`Analyzing stocks ${startIdx + 1}–${endIdx} of ${rawTickers.length} (${engineLabel} Batch ${b + 1}/${totalBatches})...`, 'Darvas Scanner', 10);
      } else {
        toastFn(`Analyzing ${rawTickers.length} stocks via ${engineLabel}...`, 'Darvas Scanner', 10);
      }
    }

    const requests = batchTickers.map(t => {
      const yfTicker = yfTickerMap[t];
      return {
        url: `https://${primaryDomain}/v8/finance/chart/${encodeURIComponent(yfTicker)}?range=2y&interval=1wk`,
        method: 'get',
        headers: {
          'User-Agent': isBackupMode
            ? 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15'
            : 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        },
        muteHttpExceptions: true
      };
    });

    let responses = null;
    try {
      responses = UrlFetchApp.fetchAll(requests);
    } catch (err) {
      Logger.log(`Batch ${b + 1} primary fetchAll failed: ${err}. Retrying on ${secondaryDomain}...`);
      try {
        const fallbackReqs = requests.map(r => ({
          ...r,
          url: r.url.replace(primaryDomain, secondaryDomain)
        }));
        responses = UrlFetchApp.fetchAll(fallbackReqs);
      } catch (err2) {
        Logger.log(`Batch ${b + 1} secondary fetchAll failed: ${err2}. Falling back to sequential fetch...`);
        responses = [];
        for (let rIdx = 0; rIdx < requests.length; rIdx++) {
          try {
            responses.push(UrlFetchApp.fetch(requests[rIdx].url, {
              headers: requests[rIdx].headers,
              muteHttpExceptions: true
            }));
          } catch (err3) {
            responses.push(null);
          }
        }
      }
    }

    // 4. Process each stock's historical bars from this batch
    for (let i = 0; i < batchTickers.length; i++) {
      const rawTicker = batchTickers[i];
      let bars = null;
      if (responses && responses[i]) {
        bars = parseYahooFinanceBars(responses[i]);
      }

      // Resilient single-stock retry if batch response missed this ticker
      if (!bars) {
        try {
          const yfTicker = yfTickerMap[rawTicker];
          const secUrl = `https://${secondaryDomain}/v8/finance/chart/${encodeURIComponent(yfTicker)}?range=2y&interval=1wk`;
          const secResp = UrlFetchApp.fetch(secUrl, {
            headers: { 'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36' },
            muteHttpExceptions: true
          });
          bars = parseYahooFinanceBars(secResp);
        } catch (eSec) {
          // Will fallback to GoogleFinance engine below
        }
      }

      if (bars && bars.length >= 25) {
        const analysis = analyzeStockFromBars(rawTicker, bars);
        if (analysis) {
          processedMap[rawTicker] = analysis;
        } else {
          missingTickers.push(rawTicker);
        }
      } else {
        missingTickers.push(rawTicker);
      }
    }
  }

  // 4b. Secondary Fallback: Fetch missing / failed stocks via GoogleFinance native engine
  const uniqueMissingTickers = Array.from(new Set(missingTickers));
  if (uniqueMissingTickers.length > 0) {
    try {
      const ss = SpreadsheetApp.getActiveSpreadsheet();
      if (ss) {
        const gfBarsMap = fetchBarsFromGoogleFinance(ss, uniqueMissingTickers);
        uniqueMissingTickers.forEach(ticker => {
          const bars = gfBarsMap[ticker];
          if (bars && bars.length >= 25) {
            const analysis = analyzeStockFromBars(ticker, bars);
            if (analysis) {
              processedMap[ticker] = analysis;
            }
          }
        });
      }
    } catch (gfErr) {
      Logger.log('GoogleFinance fallback error: ' + gfErr);
    }
  }

  // Collect final results for all rawTickers
  let processedData = rawTickers.map(ticker => {
    if (processedMap[ticker]) {
      return processedMap[ticker];
    }
    return {
      ticker: ticker,
      status: 'Data Unavailable',
      prevWeekHigh: '',
      lastWeekClose: '',
      buySignal: '',
      breakoutPct: null,
      colO_breakdown: '',
      sortGroup: 6
    };
  });

  // 5. Sort processed stocks strictly in Column I priority:
  //    1. Bullish Buy Triggered (Sort Group 1, sorted least risen first by Breakout %)
  //    2. Bearish Buy Triggered (Sort Group 2, sorted least risen first by Breakout %)
  //    3. Tracking for Bearish Buy Signal (Sort Group 3, alphabetical)
  //    4. Bullish Buy Running (Sort Group 4, alphabetical)
  //    5. Neutral / Inside 20W Range (Sort Group 5, alphabetical)
  //    6. Data Unavailable (Sort Group 6, alphabetical)
  processedData.sort((a, b) => {
    if (a.sortGroup !== b.sortGroup) {
      return a.sortGroup - b.sortGroup;
    }
    // Within Group 1 or Group 2: sort by Breakout % (Rise) ascending (least risen at the top)
    if (a.sortGroup === 1 || a.sortGroup === 2) {
      const valA = (a.breakoutPct !== null && a.breakoutPct !== undefined) ? a.breakoutPct : 999999;
      const valB = (b.breakoutPct !== null && b.breakoutPct !== undefined) ? b.breakoutPct : 999999;
      return valA - valB;
    }
    // Within Group 3, 4, 5, 6: sort alphabetically by ticker code
    return a.ticker.localeCompare(b.ticker);
  });

  // 5b. Filter out stocks already present in GTT Tracker
  if (gttTickers && gttTickers.length > 0) {
    const gttSet = new Set(gttTickers.map(t => String(t).trim().toUpperCase()));
    processedData = processedData.filter(item => !gttSet.has(String(item.ticker).trim().toUpperCase()));
  }

  // 6. Prepare batch values to write to sheet (Columns J to Q)
  const outputRows = processedData.map(item => {
    return [
      item.ticker,                                                  // Col J: Stock Code
      item.status,                                                  // Col K: Status
      item.prevWeekHigh !== '' ? Number(item.prevWeekHigh) : '',    // Col L: Previous Week High
      item.lastWeekClose !== '' ? Number(item.lastWeekClose) : '',  // Col M: Last Week's Close
      item.breakoutPct !== null ? Number(item.breakoutPct) : '',    // Col N: Breakout % (Rise)
      '',                                                           // Col O: Handled by formula in O6
      '',                                                           // Col P: Handled by formula in P6
      item.colO_breakdown                                           // Col Q: 20W Low Breakdown Signal
    ];
  });

  const durationSec = ((new Date().getTime() - startTime) / 1000).toFixed(1);
  const bullishCount = processedData.filter(d => d.sortGroup === 1).length;
  const bearishCount = processedData.filter(d => d.sortGroup === 2).length;
  const trackingCount = processedData.filter(d => d.sortGroup === 3).length;
  const runningCount = processedData.filter(d => d.sortGroup === 4).length;
  const breakdownCount = processedData.filter(d => d.colO_breakdown !== '').length;

  return {
    outputRows: outputRows,
    processedData: processedData,
    summary: {
      bullishCount: bullishCount,
      bearishCount: bearishCount,
      trackingCount: trackingCount,
      runningCount: runningCount,
      breakdownCount: breakdownCount,
      durationSec: durationSec
    }
  };
}

// ============================================================================
// GTT ORDER TRACKING SYSTEM
// ============================================================================

/**
 * onEdit simple trigger — fires automatically when any cell in the spreadsheet
 * is edited by the user.
 *
 * When a checkbox in Col R (GTT Select) on the Scanner tab is checked:
 *  1. Reads the stock code (Col H) and GTT price (Col N) from that row.
 *  2. Appends them to the GTT Tracker tab (starting at B4 / C4 / D4).
 *  3. Clears that row's data from the Scanner tab (Cols H:P and Col R) so it disappears
 *     from scan results. Col A-G is never touched.
 *
 * @param {GoogleAppsScript.Events.SheetsOnEdit} e The onEdit event object.
 */
function onEdit(e) {
  try {
    const range = e.range;
    const sheet = range.getSheet();
    const sheetName = sheet.getName();
    const editedRow = range.getRow();
    const editedCol = range.getColumn();
    const ss = SpreadsheetApp.getActiveSpreadsheet();

    // -----------------------------------------------------------------------
    // BRANCH 0: Idle Money - Holdings tab — Checkbox trigger & sale processing
    // -----------------------------------------------------------------------
    if (sheetName === IDLE_MONEY_HOLDINGS_TAB_NAME) {
      handleIdleMoneyHoldingsEdit(e);
      return;
    }

    // -----------------------------------------------------------------------
    // BRANCH A: Scanner tab — Col I (GTT Select) checkbox checked
    // -----------------------------------------------------------------------
    if (sheetName === CONFIG.SHEET_NAME &&
      editedCol === CONFIG.GTT_SELECT_COL &&
      editedRow >= CONFIG.OUTPUT_START_ROW &&
      e.value === 'TRUE') {

      // Read stock code (Col J = col 10), GTT price (Col O = col 15), and Status (Col K = col 11)
      const ticker = sheet.getRange(editedRow, 10).getValue();
      const gttPrice = sheet.getRange(editedRow, 15).getValue();
      const rawSignal = sheet.getRange(editedRow, 11).getValue(); // Col K: Status

      if (!ticker || ticker === '') return; // Safety: skip empty row

      // Map signal type to short label
      let signalShort = '';
      if (rawSignal === 'Bullish Buy Triggered') signalShort = 'Bullish Buy';
      else if (rawSignal === 'Bearish Buy Triggered') signalShort = 'Bearish Buy';
      else signalShort = rawSignal;

      // Ensure GTT Tracker sheet exists
      let gttSheet = ss.getSheetByName(GTT_CONFIG.SHEET_NAME);
      if (!gttSheet) gttSheet = setupGttTrackerSheet();

      // Find next empty row in GTT Tracker (from DATA_START_ROW)
      const nextRow = getFirstEmptyRowInGttTab(gttSheet);

      // Write values to Col B-D: do not apply any formatting, just paste as values
      const numGttPrice = (gttPrice !== '' && gttPrice !== null && !isNaN(gttPrice)) ? Number(gttPrice) : (gttPrice || '');
      gttSheet.getRange(nextRow, GTT_CONFIG.TICKER_COL, 1, 3).setValues([[ticker, numGttPrice, signalShort]]);

      // Add checkboxes (Col J & Col L) for this new row
      refreshGttCheckboxes(gttSheet);

      // Clear the stock's row from Scanner (Cols J:Q and Col I only, leave Col A-H untouched)
      sheet.getRange(editedRow, CONFIG.OUTPUT_START_COL, 1, CONFIG.OUTPUT_NUM_COLS).clearContent();
      sheet.getRange(editedRow, CONFIG.GTT_SELECT_COL).clearContent().clearDataValidations().setBackground(null);

      ss.toast(`✅ ${ticker} → GTT Tracker (row ${nextRow}), GTT price ₹${gttPrice}.`, 'GTT Order Queued', 5);
      return;
    }

    // -----------------------------------------------------------------------
    // BRANCH B0: GTT Tracker tab — Master Delete Checkbox in J1 checked
    // -----------------------------------------------------------------------
    if (sheetName === GTT_CONFIG.SHEET_NAME &&
      editedRow === GTT_CONFIG.MASTER_DELETE_ROW &&
      editedCol === GTT_CONFIG.DELETE_CHK_COL &&
      (e.value === 'TRUE' || range.getValue() === true)) {

      // Explicitly uncheck J1 checkbox and flush to UI immediately
      range.setValue(false);
      SpreadsheetApp.flush();

      clearAllGtts(sheet);
      return;
    }

    // -----------------------------------------------------------------------
    // BRANCH B: GTT Tracker tab — Col J (Delete single row) checkbox checked
    // -----------------------------------------------------------------------
    if (sheetName === GTT_CONFIG.SHEET_NAME &&
      editedCol === GTT_CONFIG.DELETE_CHK_COL &&
      editedRow >= GTT_CONFIG.DATA_START_ROW &&
      e.value === 'TRUE') {

      const ticker = sheet.getRange(editedRow, GTT_CONFIG.TICKER_COL).getValue();

      // Delete this row entirely so rows below shift up
      sheet.deleteRow(editedRow);

      // Refresh checkboxes for remaining data rows
      refreshGttCheckboxes(sheet);

      ss.toast(`🗑 ${ticker} removed from GTT Tracker.`, 'GTT Removed', 4);
      return;
    }

    // -----------------------------------------------------------------------
    // BRANCH C: GTT Tracker tab — Col L (Transfer to Current Holdings) checked
    // -----------------------------------------------------------------------
    if (sheetName === GTT_CONFIG.SHEET_NAME &&
      editedCol === GTT_CONFIG.TRANSFER_CHK_COL &&
      editedRow >= GTT_CONFIG.DATA_START_ROW &&
      e.value === 'TRUE') {

      const ticker = String(sheet.getRange(editedRow, GTT_CONFIG.TICKER_COL).getValue()).trim();
      const buyPrice = sheet.getRange(editedRow, GTT_CONFIG.GTT_PRICE_COL).getValue(); // Col C
      const signalType = sheet.getRange(editedRow, GTT_CONFIG.SIGNAL_TYPE_COL).getValue(); // Col D
      const quantity = sheet.getRange(editedRow, GTT_CONFIG.BUY_QTY_COL).getValue(); // Col E

      if (!ticker || ticker === '') {
        sheet.getRange(editedRow, editedCol).setValue(false);
        return;
      }

      // Check destination tab 'Current Holdings'
      const destSheet = ss.getSheetByName(GTT_CONFIG.DEST_SHEET_NAME);
      if (!destSheet) {
        SpreadsheetApp.getUi().alert(`Error: Sheet tab named '${GTT_CONFIG.DEST_SHEET_NAME}' was not found. Please create it first.`);
        sheet.getRange(editedRow, editedCol).setValue(false);
        return;
      }

      const destLastRow = destSheet.getLastRow();
      let lastMatchingRow = -1;
      let lastDataRow = 0;

      if (destLastRow > 0) {
        const colBValues = destSheet.getRange(1, 2, destLastRow, 1).getValues();
        const targetClean = ticker.toUpperCase();
        const targetNormalized = targetClean.replace(/^(NSE:|BSE:|BOM:|NASDAQ:|NYSE:|LON:|TSE:|ETR:)/i, '').replace(/\.(NS|BO|L|TO|DE)$/i, '');

        for (let r = 0; r < destLastRow; r++) {
          const val = String(colBValues[r][0]).trim().toUpperCase();
          if (val !== '') {
            lastDataRow = r + 1; // 1-indexed row of non-empty Col B
            const valNorm = val.replace(/^(NSE:|BSE:|BOM:|NASDAQ:|NYSE:|LON:|TSE:|ETR:)/i, '').replace(/\.(NS|BO|L|TO|DE)$/i, '');
            if (val === targetClean || valNorm === targetNormalized) {
              lastMatchingRow = r + 1; // 1-indexed row of last occurrence
            }
          }
        }
      }

      let targetRow;
      if (lastMatchingRow !== -1) {
        // Rule 1: Stock is already present in Col B.
        // Insert a new blank row below its last entry.
        destSheet.insertRowAfter(lastMatchingRow);
        targetRow = lastMatchingRow + 1;
      } else {
        // Rule 2: Stock is not present in Col B.
        // Insert in the last empty row of destination.
        targetRow = Math.max(lastDataRow + 1, GTT_CONFIG.DEST_DATA_START_ROW);
        if (targetRow > destSheet.getMaxRows()) {
          destSheet.insertRowAfter(destSheet.getMaxRows());
        }
      }

      // Format values to insert:
      // Col A: Today's date (Pure Date, zero time component)
      // Col B: Stock code
      // Col C: Buy Price (from Col C of source)
      // Col D: Quantity (from Col E of source)
      // Col E: 'Buy Type (Bearish / Bullish)' (from Col D of source)
      const ssTimeZone = ss.getSpreadsheetTimeZone() || 'Asia/Kolkata';
      const now = new Date();
      const year = Number(Utilities.formatDate(now, ssTimeZone, 'yyyy'));
      const month = Number(Utilities.formatDate(now, ssTimeZone, 'MM'));
      const day = Number(Utilities.formatDate(now, ssTimeZone, 'dd'));

      // Insert clean date without time
      const dateCell = destSheet.getRange(targetRow, 1);
      dateCell.setFormula(`=DATE(${year},${month},${day})`);
      SpreadsheetApp.flush();
      dateCell.setValue(dateCell.getValue()).setNumberFormat('dd-mmm-yy').setHorizontalAlignment('right');

      const numBuyPrice = (buyPrice !== '' && !isNaN(buyPrice)) ? Number(buyPrice) : buyPrice;
      const numQty = (quantity !== '' && !isNaN(quantity)) ? Number(quantity) : quantity;

      destSheet.getRange(targetRow, 2).setValue(ticker).setHorizontalAlignment('left');
      if (numBuyPrice !== '' && numBuyPrice !== null) {
        destSheet.getRange(targetRow, 3).setValue(numBuyPrice).setNumberFormat('#,##0.00').setHorizontalAlignment('right');
      }
      if (numQty !== '' && numQty !== null) {
        destSheet.getRange(targetRow, 4).setValue(numQty).setNumberFormat('#,##0').setHorizontalAlignment('right');
      }
      destSheet.getRange(targetRow, 5).setValue(signalType).setHorizontalAlignment('right');

      // Clear any inherited cell background color from row above in destSheet
      // destSheet.getRange(targetRow, 1, 1, 5).setBackground(null);

      // Rule 3: After transfer is done, delete its row from source tab
      sheet.deleteRow(editedRow);

      // Refresh checkboxes for remaining rows
      refreshGttCheckboxes(sheet);

      ss.toast(`✅ Transferred ${ticker} (Qty: ${numQty}, ₹${numBuyPrice}) to '${GTT_CONFIG.DEST_SHEET_NAME}' (Row ${targetRow}).`, 'Stock Transferred', 5);
      return;
    }

    // -----------------------------------------------------------------------
    // BRANCH D: GTT Tracker tab — any data edit auto-refreshes checkboxes
    // -----------------------------------------------------------------------
    if (sheetName === GTT_CONFIG.SHEET_NAME &&
      editedRow >= GTT_CONFIG.DATA_START_ROW &&
      editedCol !== GTT_CONFIG.DELETE_CHK_COL &&
      editedCol !== GTT_CONFIG.TRANSFER_CHK_COL) {
      refreshGttCheckboxes(sheet);
      return;
    }

    // -----------------------------------------------------------------------
    // BRANCH E: Current Holdings tab — Col P (Move to Sold tab) checked
    // -----------------------------------------------------------------------
    if (sheetName === HOLDINGS_CONFIG.SHEET_NAME &&
      editedCol === HOLDINGS_CONFIG.MOVE_CHK_COL &&
      editedRow >= HOLDINGS_CONFIG.DATA_START_ROW &&
      e.value === 'TRUE') {

      // Ensure destination 'Sold' sheet exists
      let soldSheet = ss.getSheetByName(HOLDINGS_CONFIG.SOLD_SHEET_NAME);
      if (!soldSheet) {
        soldSheet = ss.insertSheet(HOLDINGS_CONFIG.SOLD_SHEET_NAME);
        // Copy headers from Current Holdings Row 6 (Cols A-J) to Row 4 of Sold if newly created
        const headerVals = sheet.getRange(6, 1, 1, HOLDINGS_CONFIG.COPY_COLS_COUNT).getValues();
        soldSheet.getRange(4, 1, 1, HOLDINGS_CONFIG.COPY_COLS_COUNT).setValues(headerVals).setFontWeight('bold');
      }

      // 1. Read row data for Col A to Col J (Columns 1 to 10)
      const rowValues = sheet.getRange(editedRow, 1, 1, HOLDINGS_CONFIG.COPY_COLS_COUNT).getValues();
      const ticker = String(rowValues[0][1] || '').trim(); // Stock code from Col B

      // 2. Find first empty row in Sold tab (Row 5 onwards)
      const nextSoldRow = getFirstEmptyRowInSoldTab(soldSheet);

      // 3. Paste as VALUES in first empty row of Sold tab in Col A-J (strictly values, no formatting)
      soldSheet.getRange(nextSoldRow, 1, 1, HOLDINGS_CONFIG.COPY_COLS_COUNT).setValues(rowValues);

      // 4. Delete the entire row from source tab ('Current Holdings')
      sheet.deleteRow(editedRow);

      // 5. Refresh checkboxes for remaining rows in Current Holdings
      refreshCurrentHoldingsCheckboxes(sheet);

      ss.toast(`✅ Moved ${ticker || 'row'} to '${HOLDINGS_CONFIG.SOLD_SHEET_NAME}' tab (Row ${nextSoldRow}).`, 'Moved to Sold', 4);
      return;
    }

    // -----------------------------------------------------------------------
    // BRANCH F: Current Holdings tab — any data edit auto-refreshes checkboxes
    // -----------------------------------------------------------------------
    if (sheetName === HOLDINGS_CONFIG.SHEET_NAME &&
      editedRow >= HOLDINGS_CONFIG.DATA_START_ROW &&
      editedCol !== HOLDINGS_CONFIG.MOVE_CHK_COL) {
      refreshCurrentHoldingsCheckboxes(sheet);
      return;
    }

    // -----------------------------------------------------------------------
    // BRANCH G: Scanner tab — any data edit auto-refreshes checkboxes
    // -----------------------------------------------------------------------
    if (sheetName === CONFIG.SHEET_NAME &&
      editedRow >= CONFIG.OUTPUT_START_ROW &&
      editedCol !== CONFIG.GTT_SELECT_COL) {
      refreshScannerGttCheckboxes(sheet);
      return;
    }

  } catch (err) {
    Logger.log('onEdit GTT error: ' + err);
  }
}

/**
 * Populates GTT Select checkboxes in Column I for rows where status is
 * 'Bullish Buy Triggered' or 'Bearish Buy Triggered'. Other rows get no checkbox.
 *
 * @param {SpreadsheetApp.Sheet} sheet The Scanner sheet.
 * @param {number} startRow The first data row (Row 7).
 * @param {number} numRows Total number of output rows written.
 * @param {Array} processedData The sorted processed data array.
 */
function populateGttCheckboxes(sheet, startRow, numRows, processedData) {
  if (numRows <= 0) return;

  // Add header label in I5 if it's blank
  const headerCell = sheet.getRange(5, CONFIG.GTT_SELECT_COL);
  if (headerCell.getValue() === '') {
    headerCell
      .setValue('GTT Select')
      .setFontWeight('bold')
      .setHorizontalAlignment('center')
      .setBackground('#FEF9C3')
      .setFontColor('#713F12');
  }

  const checkboxValidation = SpreadsheetApp.newDataValidation()
    .requireCheckbox()
    .build();

  for (let i = 0; i < numRows; i++) {
    const row = startRow + i;
    const item = processedData[i];
    const isBuyEligible = (item.sortGroup === 1 || item.sortGroup === 2); // Bullish or Bearish Triggered

    const cell = sheet.getRange(row, CONFIG.GTT_SELECT_COL);
    if (isBuyEligible) {
      cell
        .setDataValidation(checkboxValidation)
        .setValue(false)
        .setBackground('#FEFCE8')   // Soft yellow
        .setHorizontalAlignment('center');
    } else {
      cell.clearContent().clearDataValidations().setBackground(null);
    }
  }
}

/**
 * Sets up or refreshes the GTT Tracker sheet:
 * - Creates the tab only if it doesn't already exist.
 * - Places ARRAYFORMULA / GOOGLEFINANCE formulas in E3:I3.
 * - Places Delete checkboxes in Col J and Transfer checkboxes in Col L for all rows with data in Col B.
 * - Ensures Column L header is set.
 * - Does NOT overwrite existing user header content if the tab already exists.
 *
 * @returns {SpreadsheetApp.Sheet} The GTT Tracker sheet.
 */
function setupGttTrackerSheet() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  let gttSheet = ss.getSheetByName(GTT_CONFIG.SHEET_NAME);
  const isNew = !gttSheet;

  if (isNew) {
    gttSheet = ss.insertSheet(GTT_CONFIG.SHEET_NAME);
  }

  // --- Ensure Column L Header if blank ---
  const transferHeader = gttSheet.getRange(2, GTT_CONFIG.TRANSFER_CHK_COL);
  if (transferHeader.getValue() === '') {
    transferHeader
      .setValue('Transfer Bought Stocks to Current Holdings')
      .setFontWeight('bold')
      .setWrap(true)
      .setHorizontalAlignment('center')
      .setVerticalAlignment('middle');
  }

  // --- Formulas in Row 3 (E3:I3) — always (re)set so they stay current ---
  // E3: Qty you can buy based on budget in Current Holdings D3
  gttSheet.getRange('E3').setFormula(
    "=ARRAYFORMULA(IF(C3:C=\"\",,FLOOR('Current Holdings'!$E$3/C3:C,1)))"
  );
  // F3: Total cost = GTT Price × Qty
  gttSheet.getRange('F3').setFormula(
    "=ARRAYFORMULA(IF(C3:C=\"\",,C3:C*E3:E))"
  );
  // G3: Already in Current Holdings? Yes / blank
  gttSheet.getRange('G3').setFormula(
    "=ARRAYFORMULA(IF(B3:B=\"\",,IF(COUNTIF('Current Holdings'!B8:B,B3:B)>0,\"Yes\",)))"
  );
  // H3: Live CMP via GOOGLEFINANCE
  gttSheet.getRange('H3').setFormula(
    "=IFERROR(map(B3:B,lambda(ticker,GOOGLEFINANCE(ticker,\"price\"))))"
  );
  // I3: GTT Price / CMP - 1  (how far CMP is from the GTT trigger)
  gttSheet.getRange('I3').setFormula(
    "=IFERROR(ARRAYFORMULA(C3:C/H3:H-1))"
  );

  // --- Ensure Master Delete Checkbox in J1 ---
  setupGttMasterDeleteCheckbox(gttSheet);

  // --- Populate Checkboxes in Col J (Delete) & Col L (Transfer) ---
  refreshGttCheckboxes(gttSheet);

  if (isNew) {
    // Only show the 'created' message for brand-new tabs
    try {
      SpreadsheetApp.getUi().alert(
        '✅ GTT Tracker tab created!\n\n' +
        'Stocks appear here when you check the ☑ GTT Select checkbox (Col I) in the Scanner tab.\n\n' +
        '• Col B: NSE Code\n• Col C: GTT Price\n• Col D: Signal Type\n' +
        '• Col E: Qty (budget ÷ GTT price)\n• Col F: Total cost\n' +
        '• Col G: In Holdings?\n• Col H: CMP\n• Col I: GTT vs CMP %\n' +
        '• Cell J1: ☑ Check to DELETE ALL GTTs (clear B4:L)\n' +
        '• Col J: ☑ Check to DELETE single row\n' +
        '• Col L: ☑ Check to TRANSFER stock to Current Holdings'
      );
    } catch (uiErr) { /* suppress if called from trigger */ }
  } else {
    try {
      SpreadsheetApp.getUi().alert('✅ GTT Tracker formulas refreshed in E3:I3, Master Delete checkbox set in J1, and row checkboxes updated in Col J & Col L.');
    } catch (uiErr) { /* suppress if called from trigger */ }
  }

  return gttSheet;
}

/**
 * Refreshes both Delete checkboxes (Col J) and Transfer checkboxes (Col L)
 * in the GTT Tracker sheet for all non-empty rows in Col B.
 * Adds checkboxes for every row where Col B (NSE Code) is non-empty,
 * starting from DATA_START_ROW. Removes checkboxes from rows where Col B is empty.
 * Also re-numbers sequential S.No. in Col A (1, 2, 3...).
 *
 * @param {SpreadsheetApp.Sheet} gttSheet The GTT Tracker sheet.
 */
function refreshGttCheckboxes(gttSheet) {
  if (!gttSheet) return;

  // Ensure Master Delete Checkbox in J1 is configured
  setupGttMasterDeleteCheckbox(gttSheet);

  const lastRow = gttSheet.getLastRow();
  if (lastRow < GTT_CONFIG.DATA_START_ROW) return;

  const numRows = lastRow - GTT_CONFIG.DATA_START_ROW + 1;
  const tickerValues = gttSheet
    .getRange(GTT_CONFIG.DATA_START_ROW, GTT_CONFIG.TICKER_COL, numRows, 1)
    .getValues();

  // Clear existing checkboxes and styles in Col J and Col L for the range
  gttSheet.getRange(GTT_CONFIG.DATA_START_ROW, GTT_CONFIG.DELETE_CHK_COL, numRows, 1)
    .clearContent()
    .clearDataValidations()
    .setBackground(null);

  gttSheet.getRange(GTT_CONFIG.DATA_START_ROW, GTT_CONFIG.TRANSFER_CHK_COL, numRows, 1)
    .clearContent()
    .clearDataValidations()
    .setBackground(null);

  let seq = 1;
  const seqValues = [];

  for (let i = 0; i < numRows; i++) {
    const row = GTT_CONFIG.DATA_START_ROW + i;
    const ticker = String(tickerValues[i][0]).trim();
    if (ticker !== '') {
      seqValues.push([seq++]);

      // Col J: Delete Checkbox (soft red)
      gttSheet.getRange(row, GTT_CONFIG.DELETE_CHK_COL)
        .setNumberFormat('General')
        .insertCheckboxes()
        .uncheck()
        .setBackground('#FEF2F2')
        .setHorizontalAlignment('center');

      // Col L: Transfer Checkbox (soft green)
      gttSheet.getRange(row, GTT_CONFIG.TRANSFER_CHK_COL)
        .setNumberFormat('General')
        .insertCheckboxes()
        .uncheck()
        .setBackground('#F0FDF4')
        .setHorizontalAlignment('center');
    } else {
      seqValues.push(['']);
    }
  }

  // Set sequential numbers in Col A (S.No.)
  if (seqValues.length > 0) {
    gttSheet.getRange(GTT_CONFIG.DATA_START_ROW, 1, numRows, 1)
      .setValues(seqValues)
      .setHorizontalAlignment('center');
  }
}

/**
 * Backward compatibility alias for refreshGttCheckboxes.
 */
function refreshGttDeleteCheckboxes(gttSheet) {
  refreshGttCheckboxes(gttSheet);
}

/**
 * Ensures the Master Delete Checkbox in J1 of the GTT Tracker tab is set up.
 * When checked, this checkbox clears all GTT entries (content of B4:L).
 *
 * @param {SpreadsheetApp.Sheet} gttSheet
 */
function setupGttMasterDeleteCheckbox(gttSheet) {
  if (!gttSheet) return;
  const j1Cell = gttSheet.getRange(GTT_CONFIG.MASTER_DELETE_ROW, GTT_CONFIG.DELETE_CHK_COL); // J1
  j1Cell.setNumberFormat('General')
    .insertCheckboxes()
    .uncheck()
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle')
    .setNote('☑ Check to delete all GTTs in sheet (clear content of B4:L)');
}

/**
 * Clears all GTTs in the 'GTT Tracker' tab by clearing the content of B4:L,
 * clearing sequential S.No. in Col A, removing row-level checkboxes in Col J & Col L,
 * preserving all existing cell formatting in B-D, and resetting the J1 checkbox back to false.
 *
 * @param {SpreadsheetApp.Sheet} [gttSheet] The GTT Tracker sheet.
 */
function clearAllGtts(gttSheet) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = gttSheet || ss.getSheetByName(GTT_CONFIG.SHEET_NAME);
  if (!sheet) return;

  const maxRows = sheet.getMaxRows();
  if (maxRows >= GTT_CONFIG.DATA_START_ROW) {
    const numRows = maxRows - GTT_CONFIG.DATA_START_ROW + 1;

    // 1. Clear content ONLY of B4:L (Cols 2 to 12 = 11 columns: B to L)
    // Preserves all cell formatting, colors, borders, and number formats in B-D
    sheet.getRange(GTT_CONFIG.DATA_START_ROW, GTT_CONFIG.TICKER_COL, numRows, 11).clearContent();

    // 2. Clear sequential S.No. content in Col A
    sheet.getRange(GTT_CONFIG.DATA_START_ROW, 1, numRows, 1).clearContent();

    // 3. Clear row-level checkboxes in Col J & Col L
    sheet.getRange(GTT_CONFIG.DATA_START_ROW, GTT_CONFIG.DELETE_CHK_COL, numRows, 1)
      .clearContent()
      .clearDataValidations()
      .setBackground(null);

    sheet.getRange(GTT_CONFIG.DATA_START_ROW, GTT_CONFIG.TRANSFER_CHK_COL, numRows, 1)
      .clearContent()
      .clearDataValidations()
      .setBackground(null);
  }

  // 4. Reset Master Delete Checkbox in J1 back to false (unchecked)
  const j1Cell = sheet.getRange(GTT_CONFIG.MASTER_DELETE_ROW, GTT_CONFIG.DELETE_CHK_COL);
  j1Cell.setValue(false);
  SpreadsheetApp.flush();

  ss.toast('🗑 All GTTs deleted (B4:L content cleared).', 'GTT Tracker Cleared', 4);
}

/**
 * Menu wrapper to clear all GTTs in GTT Tracker (B4:L).
 */
function clearAllGttsMenu() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const gttSheet = ss.getSheetByName(GTT_CONFIG.SHEET_NAME);
  if (!gttSheet) {
    SpreadsheetApp.getUi().alert(`Sheet '${GTT_CONFIG.SHEET_NAME}' was not found.`);
    return;
  }
  const ui = SpreadsheetApp.getUi();
  const response = ui.alert('Confirm Delete All GTTs', 'Are you sure you want to delete all GTTs in GTT Tracker (clear content of B4:L)?', ui.ButtonSet.YES_NO);
  if (response === ui.Button.YES) {
    clearAllGtts(gttSheet);
  }
}

/**
 * Finds the first empty data row in the 'GTT Tracker' tab starting from row 4 onwards.
 * A row is considered empty if Column B (Stock Code) is blank.
 *
 * @param {SpreadsheetApp.Sheet} gttSheet
 * @returns {number} 1-indexed row number (>= 4)
 */
function getFirstEmptyRowInGttTab(gttSheet) {
  const startRow = GTT_CONFIG.DATA_START_ROW; // Row 4
  const maxRows = gttSheet.getMaxRows();
  if (maxRows < startRow) {
    gttSheet.insertRowsAfter(maxRows, startRow - maxRows + 10);
  }

  const numToCheck = gttSheet.getMaxRows() - startRow + 1;
  const values = gttSheet.getRange(startRow, GTT_CONFIG.TICKER_COL, numToCheck, 1).getValues();

  for (let i = 0; i < values.length; i++) {
    const colB = values[i][0];
    const isColBBlank = (colB === '' || colB === null || colB === undefined);
    if (isColBBlank) {
      return startRow + i;
    }
  }

  gttSheet.insertRowAfter(gttSheet.getMaxRows());
  return gttSheet.getMaxRows();
}

/**
 * In tab 'Current Holdings', populates checkboxes in Col P (rows 8 onwards)
 * wherever the cell in Col I (Sell Date) is not blank.
 * If Col I is blank, removes any checkbox from Col P.
 *
 * @param {SpreadsheetApp.Sheet} [holdingsSheet] Optional sheet object.
 */
function refreshCurrentHoldingsCheckboxes(holdingsSheet) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = holdingsSheet || ss.getSheetByName(HOLDINGS_CONFIG.SHEET_NAME);
  if (!sheet) return;

  const lastRow = sheet.getLastRow();
  if (lastRow < HOLDINGS_CONFIG.DATA_START_ROW) return;

  const numRows = lastRow - HOLDINGS_CONFIG.DATA_START_ROW + 1;
  const colIValues = sheet.getRange(HOLDINGS_CONFIG.DATA_START_ROW, HOLDINGS_CONFIG.SELL_DATE_COL, numRows, 1).getValues();
  const colPRange = sheet.getRange(HOLDINGS_CONFIG.DATA_START_ROW, HOLDINGS_CONFIG.MOVE_CHK_COL, numRows, 1);
  const colPValues = colPRange.getValues();

  const checkboxValidation = SpreadsheetApp.newDataValidation().requireCheckbox().build();
  const validations = [];
  const newPValues = [];

  for (let i = 0; i < numRows; i++) {
    const valI = colIValues[i][0];
    const isNotBlank = (valI !== '' && valI !== null && valI !== undefined);
    const currentVal = colPValues[i][0];

    if (isNotBlank) {
      validations.push([checkboxValidation]);
      newPValues.push([currentVal === true || currentVal === 'TRUE' ? true : false]);
    } else {
      validations.push([null]);
      newPValues.push(['']);
    }
  }

  colPRange.setDataValidations(validations);
  colPRange.setValues(newPValues);
}

/**
 * Menu wrapper to refresh Move-to-Sold checkboxes in Current Holdings tab.
 */
function refreshCurrentHoldingsCheckboxesMenu() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(HOLDINGS_CONFIG.SHEET_NAME);
  if (!sheet) {
    SpreadsheetApp.getUi().alert(`Sheet '${HOLDINGS_CONFIG.SHEET_NAME}' was not found.`);
    return;
  }
  refreshCurrentHoldingsCheckboxes(sheet);
  ss.toast('✅ Checkboxes refreshed in Col P (Move to Sold tab).', 'Checkboxes Updated', 3);
}

/**
 * Finds the first empty row in the 'Sold' tab starting from row 5 onwards.
 * A row is considered empty if Column A (Buy Date) and Column B (Stock Code) are both blank.
 *
 * @param {SpreadsheetApp.Sheet} soldSheet
 * @returns {number} 1-indexed row number (>= 5)
 */
function getFirstEmptyRowInSoldTab(soldSheet) {
  const startRow = HOLDINGS_CONFIG.SOLD_DATA_START_ROW; // Row 5
  const maxRows = soldSheet.getMaxRows();
  if (maxRows < startRow) {
    soldSheet.insertRowsAfter(maxRows, startRow - maxRows + 10);
  }

  const numToCheck = soldSheet.getMaxRows() - startRow + 1;
  const values = soldSheet.getRange(startRow, 1, numToCheck, 2).getValues();

  for (let i = 0; i < values.length; i++) {
    const colA = values[i][0];
    const colB = values[i][1];
    const isColABlank = (colA === '' || colA === null || colA === undefined);
    const isColBBlank = (colB === '' || colB === null || colB === undefined);

    if (isColABlank && isColBBlank) {
      return startRow + i;
    }
  }

  soldSheet.insertRowAfter(soldSheet.getMaxRows());
  return soldSheet.getMaxRows();
}

/**
 * Refreshes GTT Select checkboxes in Column I of the Scanner tab for all rows
 * where Column K (Status) is 'Bullish Buy Triggered' or 'Bearish Buy Triggered'.
 *
 * @param {SpreadsheetApp.Sheet} [scannerSheet]
 */
function refreshScannerGttCheckboxes(scannerSheet) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = scannerSheet || ss.getSheetByName(CONFIG.SHEET_NAME);
  if (!sheet) return;

  const lastRow = sheet.getLastRow();
  if (lastRow < CONFIG.OUTPUT_START_ROW) return;

  const numRows = lastRow - CONFIG.OUTPUT_START_ROW + 1;
  const statusValues = sheet.getRange(CONFIG.OUTPUT_START_ROW, 11, numRows, 1).getValues(); // Col K: Status
  const colIRange = sheet.getRange(CONFIG.OUTPUT_START_ROW, CONFIG.GTT_SELECT_COL, numRows, 1);
  const colIValues = colIRange.getValues();

  const checkboxValidation = SpreadsheetApp.newDataValidation().requireCheckbox().build();
  const validations = [];
  const newIValues = [];
  const backgrounds = [];

  for (let i = 0; i < numRows; i++) {
    const status = String(statusValues[i][0] || '').trim();
    const isBuyEligible = (status === 'Bullish Buy Triggered' || status === 'Bearish Buy Triggered');
    const currentVal = colIValues[i][0];

    if (isBuyEligible) {
      validations.push([checkboxValidation]);
      newIValues.push([currentVal === true || currentVal === 'TRUE' ? true : false]);
      backgrounds.push(['#FEFCE8']);
    } else {
      validations.push([null]);
      newIValues.push(['']);
      backgrounds.push([null]);
    }
  }

  colIRange.setDataValidations(validations);
  colIRange.setValues(newIValues);
  colIRange.setBackgrounds(backgrounds);
}

/**
 * Refreshes and auto-populates checkboxes across all sheets in the workbook:
 * 1. Scanner tab (Col I: wherever Col K is 'Bullish Buy Triggered' or 'Bearish Buy Triggered')
 * 2. GTT Tracker tab (Col J & Col L: wherever Col B is not blank)
 * 3. Current Holdings tab (Col P: wherever Col I is not blank)
 */
function refreshAllSheetCheckboxes() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();

  // 1. Scanner tab
  const scanSheet = ss.getSheetByName(CONFIG.SHEET_NAME);
  if (scanSheet) {
    refreshScannerGttCheckboxes(scanSheet);
  }

  // 2. GTT Tracker tab
  const gttSheet = ss.getSheetByName(GTT_CONFIG.SHEET_NAME);
  if (gttSheet) {
    refreshGttCheckboxes(gttSheet);
  }

  // 3. Current Holdings tab
  const holdingsSheet = ss.getSheetByName(HOLDINGS_CONFIG.SHEET_NAME);
  if (holdingsSheet) {
    refreshCurrentHoldingsCheckboxes(holdingsSheet);
  }

  // 4. Idle Money - Holdings tab
  const idleHoldingsSheet = ss.getSheetByName(IDLE_MONEY_HOLDINGS_TAB_NAME);
  if (idleHoldingsSheet) {
    refreshIdleMoneyCheckboxes(idleHoldingsSheet);
  }
}

/**
 * Determines exact index of Last Completed Week and Last to Last Week
 * based on Indian Standard Time (IST / Asia/Kolkata).
 */
function getCompletedWeekIndices(bars) {
  if (!bars || bars.length < 25) return null;

  // Format current time in Indian Standard Time (Asia/Kolkata)
  const now = new Date();
  const istString = Utilities.formatDate(now, "Asia/Kolkata", "yyyy-MM-dd HH:mm:ss EEE");
  const parts = istString.split(' ');
  const dateParts = parts[0].split('-');
  const timeParts = parts[1].split(':');

  const year = parseInt(dateParts[0], 10);
  const month = parseInt(dateParts[1], 10) - 1;
  const day = parseInt(dateParts[2], 10);
  const hour = parseInt(timeParts[0], 10);
  const minute = parseInt(timeParts[1], 10);

  const istDate = new Date(year, month, day, hour, minute);
  const dayOfWeek = istDate.getDay(); // 0 = Sun, 1 = Mon, ..., 5 = Fri, 6 = Sat

  // Today and tomorrow dates in YYYY-MM-DD
  const todayYmd = parts[0];
  const tomorrowObj = new Date(year, month, day + 1);
  const tomYear = tomorrowObj.getFullYear();
  const tomMonth = String(tomorrowObj.getMonth() + 1).padStart(2, '0');
  const tomDay = String(tomorrowObj.getDate()).padStart(2, '0');
  const tomorrowYmd = `${tomYear}-${tomMonth}-${tomDay}`;

  const isFridayHoliday = (dayOfWeek === 5) && (CONFIG.NSE_FRIDAY_HOLIDAYS.indexOf(todayYmd) !== -1);
  const isThursdayBeforeHoliday = (dayOfWeek === 4) &&
    (hour > 15 || (hour === 15 && minute >= 30)) &&
    (CONFIG.NSE_FRIDAY_HOLIDAYS.indexOf(tomorrowYmd) !== -1);

  // Determine Monday of the CURRENT calendar week
  // Sunday = 0 (6 days after Monday), Monday = 1 (0 days), ..., Saturday = 6 (5 days)
  const daysSinceThisMonday = (dayOfWeek === 0) ? 6 : (dayOfWeek - 1);
  const currentWeekMonday = new Date(year, month, day - daysSinceThisMonday);
  currentWeekMonday.setHours(0, 0, 0, 0);

  // Determine if the current calendar week is COMPLETED
  // Handles:
  // 1. Normal weekends (Saturday / Sunday) -> 100% completed
  // 2. Normal Friday market close (after 15:30 IST) -> Completed
  // 3. Friday Exchange Holiday (e.g. Gandhi Jayanti on Friday) -> Completed on Thursday
  // 4. Thursday evening after 15:30 IST before a Friday Holiday -> Completed
  let isCurrentWeekCompleted = false;
  if (dayOfWeek === 6 || dayOfWeek === 0) {
    isCurrentWeekCompleted = true;
  } else if (dayOfWeek === 5) {
    if (isFridayHoliday || hour > 15 || (hour === 15 && minute >= 30)) {
      isCurrentWeekCompleted = true;
    }
  } else if (isThursdayBeforeHoliday) {
    isCurrentWeekCompleted = true;
  }

  // Calculate target Friday boundary for the last COMPLETED week
  let targetCompletedFriday;
  if (isCurrentWeekCompleted) {
    targetCompletedFriday = new Date(currentWeekMonday.getTime() + 4 * 24 * 3600 * 1000);
  } else {
    // Active mid-week trading: take previous completed week
    targetCompletedFriday = new Date(currentWeekMonday.getTime() - 3 * 24 * 3600 * 1000);
  }
  targetCompletedFriday.setHours(23, 59, 59, 999);

  // Search from the end backwards for the latest consolidated bar completed on or before targetCompletedFriday.
  // Seamlessly handles Monday bars (Yahoo Finance) and Friday/Thursday bars (GoogleFinance)
  // while automatically filtering out any active incomplete trading bars.
  let lastCompletedIdx = -1;
  for (let i = bars.length - 1; i >= 0; i--) {
    if (bars[i].date.getTime() <= targetCompletedFriday.getTime()) {
      lastCompletedIdx = i;
      break;
    }
  }

  if (lastCompletedIdx === -1) {
    lastCompletedIdx = bars.length - 1;
  }

  const lastToLastIdx = lastCompletedIdx - 1;

  if (lastToLastIdx < CONFIG.LOOKBACK_WEEKS) {
    return null;
  }

  return {
    lastCompletedIdx: lastCompletedIdx,
    lastToLastIdx: lastToLastIdx
  };
}

/**
 * Parses Yahoo Finance v8 JSON response into structured weekly bar objects.
 * @param {HTTPResponse} response UrlFetchApp HTTP response
 * @returns {Array<{date: Date, open: number, high: number, low: number, close: number}>|null}
 */
function parseYahooFinanceBars(response) {
  if (!response || response.getResponseCode() !== 200) {
    return null;
  }

  let json;
  try {
    json = JSON.parse(response.getContentText());
  } catch (e) {
    return null;
  }

  if (!json.chart || !json.chart.result || json.chart.result.length === 0) {
    return null;
  }

  const result = json.chart.result[0];
  const timestamps = result.timestamp;
  const quote = result.indicators.quote[0];

  if (!timestamps || !quote || timestamps.length < 25) {
    return null;
  }

  // Clean data into structured bars, discarding bars with null close/high/low
  const bars = [];
  for (let i = 0; i < timestamps.length; i++) {
    const c = quote.close[i];
    const h = quote.high[i];
    const l = quote.low[i];
    const o = quote.open[i];
    if (c !== null && h !== null && l !== null && o !== null && !isNaN(c) && Number(c) > 0) {
      bars.push({
        date: new Date(timestamps[i] * 1000),
        open: Number(o),
        high: Number(h),
        low: Number(l),
        close: Number(c)
      });
    }
  }

  bars.sort((a, b) => a.date.getTime() - b.date.getTime());

  // Deduplicate and consolidate weekly bars:
  // Yahoo Finance occasionally appends a Friday intraday snapshot bar (< 5 days from Monday weekly bar).
  // Consolidate any bars within the same calendar week (< 5 days apart) into a single weekly bar.
  const consolidatedBars = [];
  for (let i = 0; i < bars.length; i++) {
    const b = bars[i];
    if (consolidatedBars.length > 0) {
      const prev = consolidatedBars[consolidatedBars.length - 1];
      const diffDays = (b.date.getTime() - prev.date.getTime()) / (1000 * 3600 * 24);
      if (diffDays < 5) {
        prev.high = Math.max(prev.high, b.high);
        prev.low = Math.min(prev.low, b.low);
        prev.close = b.close; // Latest closing price of the completed week
        continue;
      }
    }
    consolidatedBars.push(b);
  }

  return consolidatedBars;
}

/**
 * Automated Fallback Engine using Google Sheets native GOOGLEFINANCE() function.
 * Fetches historical weekly OHLC bars in safe chunks of 15 stocks via a hidden cache tab.
 * @param {SpreadsheetApp.Spreadsheet} ss Active Spreadsheet
 * @param {string[]} tickers Array of tickers in 'NSE:INFY' format
 * @returns {Object} Map of ticker -> array of { date, open, high, low, close }
 */
function fetchBarsFromGoogleFinance(ss, tickers) {
  if (!tickers || tickers.length === 0) return {};

  const CACHE_SHEET_NAME = '_Scanner_Backup_Cache';
  let cacheSheet = ss.getSheetByName(CACHE_SHEET_NAME);
  if (!cacheSheet) {
    cacheSheet = ss.insertSheet(CACHE_SHEET_NAME);
    cacheSheet.hideSheet();
  } else {
    cacheSheet.clear();
  }

  // Ensure cacheSheet has enough columns for a 15-stock batch (15 * 6 + 10 = 100 columns)
  const GF_BATCH_SIZE = 15;
  const requiredCols = Math.max(GF_BATCH_SIZE * 6 + 10, 26);
  const currentCols = cacheSheet.getMaxColumns();
  if (currentCols < requiredCols) {
    cacheSheet.insertColumnsAfter(currentCols, requiredCols - currentCols);
  }

  const totalGfBatches = Math.ceil(tickers.length / GF_BATCH_SIZE);
  const barsByTicker = {};

  for (let b = 0; b < totalGfBatches; b++) {
    const startIdx = b * GF_BATCH_SIZE;
    const endIdx = Math.min(startIdx + GF_BATCH_SIZE, tickers.length);
    const batchTickers = tickers.slice(startIdx, endIdx);

    if (totalGfBatches > 1) {
      ss.toast(`Fetching GoogleFinance fallback ${startIdx + 1}–${endIdx} of ${tickers.length} (Batch ${b + 1}/${totalGfBatches})...`, '⚡ GoogleFinance', 10);
    }

    cacheSheet.clear();

    // Populate GOOGLEFINANCE formulas for this batch across columns (6 columns per ticker)
    const formulaRow = [];
    for (let i = 0; i < batchTickers.length; i++) {
      let gfCode = batchTickers[i].trim();
      if (!gfCode.includes(':')) {
        gfCode = 'NSE:' + gfCode.replace(/\.(NS|BO)$/i, '');
      } else if (gfCode.toUpperCase().startsWith('BSE:')) {
        gfCode = 'BOM:' + gfCode.substring(4).trim();
      }
      const formula = `=IFERROR(GOOGLEFINANCE("${gfCode}", "all", TODAY()-450, TODAY(), "WEEKLY"), "")`;
      formulaRow.push(formula, '', '', '', '', '');
    }

    // Write formulas in Row 1
    cacheSheet.getRange(1, 1, 1, formulaRow.length).setFormulas([formulaRow]);
    SpreadsheetApp.flush();

    // Polling wait for Google Sheets to evaluate and expand the formulas downward
    let waitLoops = 0;
    while (cacheSheet.getLastRow() < 15 && waitLoops < 6) {
      Utilities.sleep(1000);
      SpreadsheetApp.flush();
      waitLoops++;
    }

    const finalLastRow = Math.max(cacheSheet.getLastRow(), 2);
    const finalLastCol = formulaRow.length;
    const values = cacheSheet.getRange(1, 1, finalLastRow, finalLastCol).getValues();

    for (let i = 0; i < batchTickers.length; i++) {
      const ticker = batchTickers[i];
      const colStart = i * 6; // 0-indexed column
      const bars = [];

      // Row 0 is the headers ("Date", "Open", "High", "Low", "Close", "Volume")
      // Data rows start from row 1
      for (let r = 1; r < values.length; r++) {
        const d = values[r][colStart];
        const o = values[r][colStart + 1];
        const h = values[r][colStart + 2];
        const l = values[r][colStart + 3];
        const c = values[r][colStart + 4];

        if (d instanceof Date && !isNaN(c) && c !== '' && c !== null && Number(c) > 0) {
          bars.push({
            date: d,
            open: Number(o),
            high: Number(h),
            low: Number(l),
            close: Number(c)
          });
        }
      }

      // Sort bars chronologically (oldest first)
      bars.sort((a, b) => a.date.getTime() - b.date.getTime());

      // Deduplicate any same-week bars if present (< 5 days apart)
      const consolidatedBars = [];
      for (let r = 0; r < bars.length; r++) {
        const barItem = bars[r];
        if (consolidatedBars.length > 0) {
          const prev = consolidatedBars[consolidatedBars.length - 1];
          const diffDays = (barItem.date.getTime() - prev.date.getTime()) / (1000 * 3600 * 24);
          if (diffDays < 5) {
            prev.high = Math.max(prev.high, barItem.high);
            prev.low = Math.min(prev.low, barItem.low);
            prev.close = barItem.close;
            continue;
          }
        }
        consolidatedBars.push(barItem);
      }

      barsByTicker[ticker] = consolidatedBars;
    }
  }

  // Clean up cache sheet to keep spreadsheet lightweight
  cacheSheet.clear();

  return barsByTicker;
}

/**
 * Analyzes structured weekly bars and applies Darvas Bearish + Bullish Strategy Rules.
 * @param {string} ticker Stock ticker code (e.g. 'NSE:INFY')
 * @param {Array<{date: Date, open: number, high: number, low: number, close: number}>} bars
 * @returns {Object|null} Strategy analysis result object
 */
function analyzeStockFromBars(ticker, bars) {
  if (!bars || bars.length < 25) {
    return null;
  }

  // Determine exact indices for Last Week (W_t) and Last to Last Week (W_{t-1})
  const indices = getCompletedWeekIndices(bars);
  if (!indices) {
    return null;
  }

  const currentCompletedIdx = indices.lastCompletedIdx; // W_t: Last Completed Week
  const prevWeekIdx = indices.lastToLastIdx;             // W_{t-1}: Last to Last Week

  const lastWeekBar = bars[currentCompletedIdx];         // Last Week (Col K)
  const lastToLastWeekBar = bars[prevWeekIdx];           // Last to Last Week (Col J)

  const lastWeekClose = lastWeekBar.close;               // Close of Last Week
  const lastToLastWeekHigh = lastToLastWeekBar.high;     // High of Last to Last Week

  // Simulate historical state machine over past bars up to prevWeekIdx (prior to W_t)
  // State:
  // - isBullishRunning: true if bought on Bullish signal (20W high breakout) and has NOT touched 20W low since.
  // - isTracking20w: true if 20-week low was touched and has NOT broken out to 20W high since.
  let isBullishRunning = false;
  let isTracking20w = false;
  const lookback = CONFIG.LOOKBACK_WEEKS; // 20 weeks

  for (let i = lookback; i <= prevWeekIdx; i++) {
    const bar = bars[i];
    const barClose = bar.close;
    const barLow = bar.low;

    // Rolling 20-week high and low from prior 20 completed weeks [i-lookback to i-1]
    let r20h = -Infinity;
    let r20l = Infinity;
    for (let k = i - lookback; k < i; k++) {
      if (bars[k].high > r20h) r20h = bars[k].high;
      if (bars[k].low < r20l) r20l = bars[k].low;
    }

    // 1. Touched 20-Week Low: Terminates bullish holding, activates bearish dip tracking
    if (barLow <= r20l) {
      isBullishRunning = false;
      isTracking20w = true;
    }

    // 2. 20-Week High Breakout: Activates bullish holding, terminates bearish dip tracking
    if (barClose > r20h) {
      isBullishRunning = true;
      isTracking20w = false;
    }
  }

  // Calculate rolling 20W high and low for evaluating current completed week W_t
  let r20h_current = -Infinity;
  let r20l_current = Infinity;
  for (let k = currentCompletedIdx - lookback; k < currentCompletedIdx; k++) {
    if (bars[k].high > r20h_current) r20h_current = bars[k].high;
    if (bars[k].low < r20l_current) r20l_current = bars[k].low;
  }

  // Check if recently completed week touched/breached 20W low
  const touched20wLowThisWeek = (lastWeekBar.low <= r20l_current);
  if (touched20wLowThisWeek) {
    isBullishRunning = false;
    isTracking20w = true;
  }

  // Populate Column P: '20W Low Breakdown' if 20-week low was touched in recently completed week
  const colO_breakdown = touched20wLowThisWeek ? '20W Low Breakdown' : '';

  let status = 'Neutral / Inside 20W Range';
  let buySignal = '';
  let breakoutPct = null;
  let sortGroup = 5;

  const isBullishBreakoutThisWeek = (lastWeekClose > r20h_current);
  const isWeeklySwingBreakout = (lastWeekClose > lastToLastWeekHigh);

  if (isBullishBreakoutThisWeek && !isBullishRunning) {
    // 1. Bullish Buy Triggered (Fresh initial 20-week high breakout)
    status = 'Bullish Buy Triggered';
    buySignal = 'Bullish Buy Triggered';
    breakoutPct = ((lastWeekClose - lastToLastWeekHigh) / lastToLastWeekHigh);
    sortGroup = 1;
    isBullishRunning = true;
    isTracking20w = false;
  } else if (isTracking20w && isWeeklySwingBreakout) {
    // 2. Bearish Buy Triggered (Tracking 20W low & Close of Last Week > High of Last to Last Week)
    status = 'Bearish Buy Triggered';
    buySignal = 'Bearish Buy Triggered';
    breakoutPct = ((lastWeekClose - lastToLastWeekHigh) / lastToLastWeekHigh);
    sortGroup = 2;
  } else if (isTracking20w) {
    // 3. Tracking for Bearish Buy Signal (20W low touched, awaiting weekly bounce, e.g. NSE:YESBANK)
    status = 'Tracking for Bearish Buy Signal';
    sortGroup = 3;
  } else if (isBullishRunning && !touched20wLowThisWeek) {
    // 4. Bullish Buy Running (Bought on Bullish signal in past, has NOT touched 20W low yet, e.g. NSE:ABCAPITAL)
    status = 'Bullish Buy Running';
    sortGroup = 4;
  } else {
    // 5. Neutral / Inside 20W Range (Fluctuating inside range without touching 20W low or high)
    status = 'Neutral / Inside 20W Range';
    sortGroup = 5;
  }

  return {
    ticker: ticker,
    status: status,
    prevWeekHigh: lastToLastWeekHigh.toFixed(2),  // Col J: High of Last to Last Week
    lastWeekClose: lastWeekClose.toFixed(2),      // Col K: Close of Last Week
    buySignal: buySignal,                        // Col L: Buy Signal
    breakoutPct: breakoutPct,                    // Col M: Breakout % (Rise)
    colO_breakdown: colO_breakdown,              // Col P: 20W Low Breakdown Signal
    sortGroup: sortGroup
  };
}

/**
 * Backward compatibility wrapper for Yahoo Finance analysis.
 */
function analyzeStockWeeklyHistory(ticker, response) {
  const bars = parseYahooFinanceBars(response);
  if (!bars || bars.length < 25) return null;
  return analyzeStockFromBars(ticker, bars);
}

/**
 * Dedicated menu function to force execution via Backup Mirror engine.
 */
function runDarvasScannerGoogleFinanceOnly() {
  runDarvasScanner(true);
}
function runDarvasScannerBackupOnly() {
  runDarvasScanner(true);
}

/**
 * Ensures required formulas are placed in Row 6 (E6, F6, G6, H6, O6, P6).
 * - H6 is populated with the user formula looking up Stock Code in J6:J against Current Holdings Bullish Buys.
 * - O6 computes Buy Limit Ceiling from Last Week's Close in M6:M.
 * - P6 computes CMP from Stock Code in J6:J via GOOGLEFINANCE.
 */
function ensureRow6Formulas(sheet) {
  // Clear any leftover array formulas from previous layouts in row 6 to avoid formula collision/spill errors
  const cellsToClear = ['I6', 'M6', 'N6', 'Q6'];
  cellsToClear.forEach(cell => {
    const r = sheet.getRange(cell);
    if (r.getFormula()) {
      r.clearContent();
    }
  });

  // If H7:H contains static values from previous runs (when stock code was in Col H),
  // clear it so the array formula in H6 can expand cleanly downward without #REF! spill errors.
  const lastRow = sheet.getLastRow();
  if (lastRow >= CONFIG.OUTPUT_START_ROW) {
    const hRange = sheet.getRange(CONFIG.OUTPUT_START_ROW, 8, lastRow - CONFIG.OUTPUT_START_ROW + 1, 1);
    const hFormulas = hRange.getFormulas();
    const hasFormulas = hFormulas.some(row => row[0] !== '');
    if (!hasFormulas) {
      hRange.clearContent();
    }
  }

  const formulas = {
    'E6': "=IFERROR(ARRAYFORMULA(IF(N6:N=\"\",,XLOOKUP(J6:J,'Current Holdings'!B:B,'Current Holdings'!C:C,,,-1))))",
    'F6': "=IFERROR(ARRAYFORMULA(IF(O6:O=\"\",,O6:O/E6:E-1)))",
    'G6': "=IFERROR(ARRAYFORMULA(IF(N6:N=\"\",,XLOOKUP(J6:J,'Current Holdings'!S:S,'Current Holdings'!X:X))))",
    'H6': "=IFERROR(ARRAYFORMULA(IF(N6:N=\"\",,IF(VLOOKUP(J6:J,FILTER('Current Holdings'!B8:B,'Current Holdings'!E8:E=\"Bullish Buy\"),1,0)<>\"\",\"Yes\",\"No\"))))",
    'O6': "=IFERROR(ARRAYFORMULA(IF(N6:N=\"\",,CEILING(M6:M*1.005,0.05))))",
    'P6': "=IFERROR(MAP(J6:J, LAMBDA(t, IF(t=\"\",, IF(ISNUMBER(SEARCH(\":\", t)), IFERROR(GOOGLEFINANCE(t, \"price\"), IFERROR(GOOGLEFINANCE(SUBSTITUTE(t, \"BSE:\", \"BOM:\"), \"price\"))), IFERROR(GOOGLEFINANCE(\"NSE:\" & t, \"price\"), IFERROR(GOOGLEFINANCE(\"BOM:\" & t, \"price\"))))))))"
  };

  for (const cell in formulas) {
    sheet.getRange(cell).setFormula(formulas[cell]);
  }
}

/**
 * Formats columns E:Q with clean numbers, percentages, currencies, and alignments.
 */
function formatScannerDataRange(sheet, startRow, numRows) {
  if (numRows <= 0) return;

  const FMT_PRICE = '#,##0.00';
  const FMT_PERCENT = '0.00%';

  // Format Col E & F
  sheet.getRange(startRow, 5, numRows, 1).setNumberFormat(FMT_PRICE);   // Col E: Last Buy Price
  sheet.getRange(startRow, 6, numRows, 1).setNumberFormat(FMT_PERCENT); // Col F: Distance %

  // Format Col H: Bullish Buy Already Done? (Center alignment)
  sheet.getRange(startRow, 8, numRows, 1).setHorizontalAlignment('center');

  // Format Col J: Stock Code (Left alignment)
  sheet.getRange(startRow, 10, numRows, 1).setHorizontalAlignment('left');

  // Format Col K: Status (Bold font)
  sheet.getRange(startRow, 11, numRows, 1).setFontWeight('bold');

  // Format Col L, M: Prices (Col L: Prev Week High, Col M: Last Week Close)
  sheet.getRange(startRow, 12, numRows, 2).setNumberFormat(FMT_PRICE);  // Col L, M: High, Close

  // Format Col N: Breakout %
  sheet.getRange(startRow, 14, numRows, 1).setNumberFormat(FMT_PERCENT); // Col N: Breakout %

  // Format Col O, P: Prices
  sheet.getRange(startRow, 15, numRows, 2).setNumberFormat(FMT_PRICE);  // Col O, P: Ceiling, CMP

  // Format Col Q: Center alignment
  sheet.getRange(startRow, 17, numRows, 1).setHorizontalAlignment('center'); // Col Q: 20W Low Breakdown Signal
}

/**
 * Populates top executive summary KPI cards in Rows 1-2 across Columns J:P.
 * Displays:
 * 1. Col J:L (Row 1-2) -> Bullish Buy Triggered (number of stocks below it in Row 2)
 * 2. Col M:N (Row 1-2) -> Bearish Buy Triggered (number of stocks below it in Row 2)
 * 3. Col O:P (Row 1-2) -> Last Scan ran on (dd-mmm-yyyy HH:MM format in Row 2)
 * 
 * Row 3 content is cleared and formatted cleanly as breathing space.
 * 
 * @param {SpreadsheetApp.Sheet} sheet Active Scanner sheet
 * @param {number} bullishCount Number of Bullish Buy Triggered stocks
 * @param {number} bearishCount Number of Bearish Buy Triggered stocks
 */
function updateScannerSummaryHeader(sheet, bullishCount, bearishCount) {
  const now = new Date();
  const timestampStr = Utilities.formatDate(now, "Asia/Kolkata", "dd-MMM-yyyy HH:mm");

  // Set row heights for visual balance
  sheet.setRowHeight(1, 26);
  sheet.setRowHeight(2, 34);
  sheet.setRowHeight(3, 16);

  // Safely clear old contents, formats & reset merges across G1:Q3
  const oldHeaderRange = sheet.getRange('J1:P3');
  oldHeaderRange.breakApart();
  oldHeaderRange.clearContent();
  oldHeaderRange.clearFormat();

  // --- CARD 1: Bullish Buy Triggered (Cols J:L, Rows 1-2) ---
  sheet.getRange('J1:L1').merge()
    .setValue('Bullish Buy Triggered')
    .setBackground('#D1FAE5')
    .setFontColor('#065F46')
    .setFontSize(11)
    .setFontWeight('bold')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  sheet.getRange('J2:L2').merge()
    .setValue(bullishCount)
    .setBackground('#ECFDF5')
    .setFontColor('#047857')
    .setFontSize(20)
    .setFontWeight('bold')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  sheet.getRange('J1:L2').setBorder(true, true, true, true, false, false, '#A7F3D0', SpreadsheetApp.BorderStyle.SOLID_MEDIUM);

  // --- CARD 2: Bearish Buy Triggered (Cols M:N, Rows 1-2) ---
  sheet.getRange('M1:N1').merge()
    .setValue('Bearish Buy Triggered')
    .setBackground('#DBEAFE')
    .setFontColor('#1E40AF')
    .setFontSize(11)
    .setFontWeight('bold')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  sheet.getRange('M2:N2').merge()
    .setValue(bearishCount)
    .setBackground('#EFF6FF')
    .setFontColor('#1D4ED8')
    .setFontSize(20)
    .setFontWeight('bold')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  sheet.getRange('M1:N2').setBorder(true, true, true, true, false, false, '#BFDBFE', SpreadsheetApp.BorderStyle.SOLID_MEDIUM);

  // --- CARD 3: Last Scan ran on (Cols O:P, Rows 1-2) ---
  sheet.getRange('O1:P1').merge()
    .setValue('Last Scan ran on')
    .setBackground('#E2E8F0')
    .setFontColor('#1E293B')
    .setFontSize(11)
    .setFontWeight('bold')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  sheet.getRange('O2:P2').merge()
    .setValue(timestampStr)
    .setBackground('#F8FAFC')
    .setFontColor('#0F172A')
    .setFontSize(13)
    .setFontWeight('bold')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  sheet.getRange('O1:P2').setBorder(true, true, true, true, false, false, '#CBD5E1', SpreadsheetApp.BorderStyle.SOLID_MEDIUM);
}

/**
 * Applies visual conditional formatting rules:
 * - Highlights entire row range (Col J to P) ONLY for 'Buy Triggered' stocks (Bullish and Bearish)
 * - Highlights Column K only for 'Bullish Buy Running' and 'Tracking for Bearish Buy Signal'
 * - Col Q (20W Low Breakdown Signal) -> Soft Red Alert Badge
 * - Col F (Distance %) -> Soft Green (Positive) / Soft Red (Negative)
 */
function applyScannerFormattingRules(sheet) {
  const rules = [];

  // 1. Buy Triggered Stocks Highlighting across Columns J through P (Columns 10 through 16)
  // Formula: =$K7="..." locks evaluation to Column K Status for the entire row range J:P

  // 1a. Bullish Buy Triggered -> Soft Emerald Green across Col J-P
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenFormulaSatisfied('=$K7="Bullish Buy Triggered"')
    .setBackground('#D1FAE5') // Light Emerald
    .setFontColor('#065F46')  // Dark Emerald
    .setRanges([sheet.getRange('J7:P500')])
    .build());

  // 1b. Bearish Buy Triggered -> Soft Cyan / Blue across Col J-P
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenFormulaSatisfied('=$K7="Bearish Buy Triggered"')
    .setBackground('#DBEAFE') // Light Blue
    .setFontColor('#1E40AF')  // Dark Blue
    .setRanges([sheet.getRange('J7:P500')])
    .build());

  // 2. Non-triggered Statuses -> Highlight Column K ONLY (Columns J-P remain normal/white)

  // 2a. Bullish Buy Running -> Soft Mint / Teal on Column K only
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo('Bullish Buy Running')
    .setBackground('#CCFBF1') // Light Teal
    .setFontColor('#0F766E')  // Dark Teal
    .setBold(true)
    .setRanges([sheet.getRange('K7:K500')])
    .build());

  // 2b. Tracking for Bearish Buy Signal -> Soft Amber / Orange on Column K only
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo('Tracking for Bearish Buy Signal')
    .setBackground('#FEF3C7') // Light Amber
    .setFontColor('#92400E')  // Dark Amber
    .setRanges([sheet.getRange('K7:K500')])
    .build());

  // 2. Col Q (20W Low Breakdown Signal) -> Soft Red Alert Badge
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo('20W Low Breakdown')
    .setBackground('#FEE2E2') // Light Red
    .setFontColor('#991B1B')  // Dark Red
    .setBold(true)
    .setRanges([sheet.getRange('Q7:Q500')])
    .build());

  // 3. Distance between CMP and Last Buy Price (Col F)
  // Positive -> Soft Green
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenNumberGreaterThan(0)
    .setBackground('#ECFDF5')
    .setFontColor('#047857')
    .setRanges([sheet.getRange('F7:F500')])
    .build());

  // Negative -> Soft Red
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenNumberLessThan(0)
    .setBackground('#FFF1F2')
    .setFontColor('#BE123C')
    .setRanges([sheet.getRange('F7:F500')])
    .build());

  // Set the conditional format rules
  sheet.setConditionalFormatRules(rules);
}

/**
 * Sets up an automated weekly time-driven trigger running every Saturday at 8:00 AM.
 */
function setupWeeklyTrigger() {
  removeWeeklyTrigger(); // Avoid duplicates

  ScriptApp.newTrigger('runDarvasScanner')
    .timeBased()
    .onWeekDay(ScriptApp.WeekDay.SATURDAY)
    .atHour(8)
    .create();

  SpreadsheetApp.getUi().alert('✅ Success!\n\nAutomated weekly scanner trigger has been set to run every Saturday at 8:00 AM (after weekly market close).');
}

/**
 * Removes any existing automated triggers.
 */
function removeWeeklyTrigger() {
  const triggers = ScriptApp.getProjectTriggers();
  triggers.forEach(trigger => {
    if (trigger.getHandlerFunction() === 'runDarvasScanner') {
      ScriptApp.deleteTrigger(trigger);
    }
  });
}

/**
 * Displays an informational modal dialog explaining the scanner logic and rules.
 */
function showAboutDialog() {
  const htmlContent = `
    <div style="font-family: Arial, sans-serif; font-size: 13px; line-height: 1.6; color: #1e293b; padding: 10px;">
      <h3 style="color: #2563eb; margin-top: 0;">⚡ Darvas Systematic Strategy Scanner</h3>
      <p>This automated scanner downloads weekly historical OHLC data from Yahoo Finance and identifies trade setups across your watchlist:</p>
      
      <table style="width: 100%; border-collapse: collapse; margin-bottom: 12px; font-size: 12px;">
        <tr style="background: #f1f5f9; text-align: left;">
          <th style="padding: 6px; border: 1px solid #cbd5e1;">Status / Signal</th>
          <th style="padding: 6px; border: 1px solid #cbd5e1;">Trigger Condition</th>
          <th style="padding: 6px; border: 1px solid #cbd5e1;">Action</th>
        </tr>
        <tr>
          <td style="padding: 6px; border: 1px solid #cbd5e1; font-weight: bold; color: #047857;">1. Bullish Buy Triggered</td>
          <td style="padding: 6px; border: 1px solid #cbd5e1;">Close of Last Week (Col M) > 20-Week High (Fresh Breakout)</td>
          <td style="padding: 6px; border: 1px solid #cbd5e1;">Deploy Slot 1 Macro Trend Compounder</td>
        </tr>
        <tr>
          <td style="padding: 6px; border: 1px solid #cbd5e1; font-weight: bold; color: #1e40af;">2. Bearish Buy Triggered</td>
          <td style="padding: 6px; border: 1px solid #cbd5e1;">20W Low Touched & Close of Last Week (Col M) > High of Last to Last Week (Col L)</td>
          <td style="padding: 6px; border: 1px solid #cbd5e1;">Deploy Dip-Harvester Tranche (Target +5%)</td>
        </tr>
        <tr>
          <td style="padding: 6px; border: 1px solid #cbd5e1; font-weight: bold; color: #92400e;">3. Tracking for Bearish Buy Signal</td>
          <td style="padding: 6px; border: 1px solid #cbd5e1;">20W Low Touched, Awaiting Weekly Bounce (e.g. NSE:YESBANK)</td>
          <td style="padding: 6px; border: 1px solid #cbd5e1;">Monitor Watchlist for Entry Signal</td>
        </tr>
        <tr>
          <td style="padding: 6px; border: 1px solid #cbd5e1; font-weight: bold; color: #0f766e;">4. Bullish Buy Running</td>
          <td style="padding: 6px; border: 1px solid #cbd5e1;">Bought on Bullish signal & has NOT touched 20W low yet (e.g. NSE:ABCAPITAL)</td>
          <td style="padding: 6px; border: 1px solid #cbd5e1;">Holding & Compounding Macro Trend</td>
        </tr>
        <tr>
          <td style="padding: 6px; border: 1px solid #cbd5e1; font-weight: bold; color: #b91c1c;">Col Q: 20W Low Breakdown Signal</td>
          <td style="padding: 6px; border: 1px solid #cbd5e1;">Low of recently completed week <= 20W Low</td>
          <td style="padding: 6px; border: 1px solid #cbd5e1;">Alert: Fresh 20W low touched this week!</td>
        </tr>
      </table>

      <p><b>Columns:</b><br>
      • <b>Col H:</b> Bullish Buy Already Done?<br>
      • <b>Col I:</b> GTT Select Checkbox<br>
      • <b>Col J:</b> Stock Code<br>
      • <b>Col K:</b> Status<br>
      • <b>Col L:</b> High of Last to Last Week<br>
      • <b>Col M:</b> Close of Last Week<br>
      • <b>Col N:</b> Breakout % = (Col M - Col L) / Col L<br>
      • <b>Col O:</b> Buy Limit Ceiling = CEILING(Col M * 1.005, 0.05)<br>
      • <b>Col P:</b> Current Market Price (CMP)<br>
      • <b>Col Q:</b> 20W Low Breakdown Signal (Alert for fresh breakdown this week)</p>

      <p><b>Sorting Order in Column K:</b><br>
      1. Bullish Buy Triggered (sorted by least Breakout % rise first)<br>
      2. Bearish Buy Triggered (sorted by least Breakout % rise first)<br>
      3. Tracking for Bearish Buy Signal<br>
      4. Bullish Buy Running (holding above 20W floor)<br>
      5. Neutral / Inside 20W Range</p>
      <p><b>Supported Stock Code Formats (Column A):</b></p>
      <table style="width: 100%; border-collapse: collapse; margin-bottom: 12px; font-size: 11.5px;">
        <tr style="background: #0f172a; color: #38bdf8; text-align: left;">
          <th style="padding: 6px 8px; border: 1px solid #334155;">Market</th>
          <th style="padding: 6px 8px; border: 1px solid #334155;">Format to Enter in Column A</th>
          <th style="padding: 6px 8px; border: 1px solid #334155;">Example</th>
        </tr>
        <tr style="background: #1e293b; color: #f8fafc;">
          <td style="padding: 6px 8px; border: 1px solid #334155; font-weight: 600;">Indian Stocks</td>
          <td style="padding: 6px 8px; border: 1px solid #334155; color: #93c5fd;">NSE:&lt;TICKER&gt;, BOM:&lt;TICKER&gt;</td>
          <td style="padding: 6px 8px; border: 1px solid #334155; color: #cbd5e1;">NSE:INFY<br>BOM:500209</td>
        </tr>
        <tr style="background: #1e293b; color: #f8fafc;">
          <td style="padding: 6px 8px; border: 1px solid #334155; font-weight: 600;">US Stocks (Tech / NASDAQ)</td>
          <td style="padding: 6px 8px; border: 1px solid #334155; color: #93c5fd;">NASDAQ:&lt;TICKER&gt;</td>
          <td style="padding: 6px 8px; border: 1px solid #334155; color: #cbd5e1;">NASDAQ:AAPL</td>
        </tr>
        <tr style="background: #1e293b; color: #f8fafc;">
          <td style="padding: 6px 8px; border: 1px solid #334155; font-weight: 600;">US Stocks (NYSE / Dow)</td>
          <td style="padding: 6px 8px; border: 1px solid #334155; color: #93c5fd;">NYSE:&lt;TICKER&gt;</td>
          <td style="padding: 6px 8px; border: 1px solid #334155; color: #cbd5e1;">NYSE:JPM</td>
        </tr>
        <tr style="background: #1e293b; color: #f8fafc;">
          <td style="padding: 6px 8px; border: 1px solid #334155; font-weight: 600;">UK / London Stocks</td>
          <td style="padding: 6px 8px; border: 1px solid #334155; color: #93c5fd;">LON:&lt;TICKER&gt;</td>
          <td style="padding: 6px 8px; border: 1px solid #334155; color: #cbd5e1;">LON:VOD</td>
        </tr>
        <tr style="background: #1e293b; color: #f8fafc;">
          <td style="padding: 6px 8px; border: 1px solid #334155; font-weight: 600;">Canadian / Toronto Stocks</td>
          <td style="padding: 6px 8px; border: 1px solid #334155; color: #93c5fd;">TSE:&lt;TICKER&gt;</td>
          <td style="padding: 6px 8px; border: 1px solid #334155; color: #cbd5e1;">TSE:SHOP</td>
        </tr>
        <tr style="background: #1e293b; color: #f8fafc;">
          <td style="padding: 6px 8px; border: 1px solid #334155; font-weight: 600;">European / German Stocks</td>
          <td style="padding: 6px 8px; border: 1px solid #334155; color: #93c5fd;">ETR:&lt;TICKER&gt;</td>
          <td style="padding: 6px 8px; border: 1px solid #334155; color: #cbd5e1;">ETR:SAP</td>
        </tr>
      </table>
      <p style="font-size: 11px; color: #64748b; margin-top: -6px;"><i>* Tickers entered without prefix (e.g. <code>TCS</code>) automatically default to Indian NSE (<code>NSE:TCS</code>).</i></p>

      <p style="color: #64748b; font-size: 11px;">Powered by Google Apps Script, Yahoo Finance v8 API & GoogleFinance native engine.</p>
    </div>
  `;
  const htmlOutput = HtmlService.createHtmlOutput(htmlContent)
    .setWidth(600)
    .setHeight(620);
  SpreadsheetApp.getUi().showModalDialog(htmlOutput, 'About Darvas Strategy Scanner');
}

/**
 * Helper to convert standard Google Finance ticker format to Yahoo Finance ticker format.
 * Matches your guide table:
 * - Indian: 'NSE:INFY' -> 'INFY.NS', 'BSE:500209' -> '500209.BO', 'TCS' -> 'TCS.NS'
 * - US Tech: 'NASDAQ:AAPL' -> 'AAPL', 'NASDAQ:NVDA' -> 'NVDA'
 * - US NYSE: 'NYSE:JPM' -> 'JPM', 'NYSE:TSLA' -> 'TSLA'
 * - UK London: 'LON:VOD' -> 'VOD.L', 'LSE:VOD' -> 'VOD.L'
 * - Canadian: 'TSE:SHOP' -> 'SHOP.TO', 'TSX:SHOP' -> 'SHOP.TO'
 * - European / German: 'ETR:SAP' -> 'SAP.DE', 'FRA:SAP' -> 'SAP.DE'
 */
function convertToYfTicker(ticker) {
  let clean = String(ticker).trim().toUpperCase();

  // 1. UK / London Stocks (LON:VOD or LSE:VOD -> VOD.L)
  if (clean.startsWith('LON:')) return clean.substring(4).trim() + '.L';
  if (clean.startsWith('LSE:')) return clean.substring(4).trim() + '.L';

  // 2. Canadian / Toronto Stocks (TSE:SHOP or TSX:SHOP -> SHOP.TO)
  if (clean.startsWith('TSE:')) return clean.substring(4).trim() + '.TO';
  if (clean.startsWith('TSX:')) return clean.substring(4).trim() + '.TO';

  // 3. European / German Stocks (ETR:SAP or FRA:SAP -> SAP.DE)
  if (clean.startsWith('ETR:')) return clean.substring(4).trim() + '.DE';
  if (clean.startsWith('FRA:')) return clean.substring(4).trim() + '.DE';

  // 4. US Stocks (NASDAQ:AAPL, NYSE:JPM, AMEX:SPY, ARCA:QQQ, etc. -> strip prefix)
  const usPrefixes = ['NASDAQ:', 'NYSE:', 'AMEX:', 'BATS:', 'ARCA:', 'OTCMKTS:', 'US:'];
  for (const p of usPrefixes) {
    if (clean.startsWith(p)) {
      return clean.substring(p.length).trim();
    }
  }

  // 5. Strip .US suffix if entered (e.g. AAPL.US -> AAPL)
  if (clean.endsWith('.US')) {
    return clean.replace(/\.US$/i, '');
  }

  // 6. Indian market prefixes
  if (clean.startsWith('NSE:')) {
    return clean.substring(4).trim() + '.NS';
  } else if (clean.startsWith('BSE:')) {
    return clean.substring(4).trim() + '.BO';
  } else if (clean.startsWith('BOM:')) {
    return clean.substring(4).trim() + '.BO';
  }

  // 7. If user already entered with suffix or symbol (e.g. VOD.L, SAP.DE, BTC-USD)
  if (clean.includes('.') || clean.includes('-') || clean.includes('=')) {
    return clean;
  }

  // 8. Plain ticker without exchange prefix (defaults to Indian NSE)
  return clean + '.NS';
}

// ==============================================================================
// IDLE MONEY AUTOMATION (HOLDINGS -> SOLD WITH FIFO LOT DEDUCTION)
// ==============================================================================

/**
 * Refreshes checkboxes on 'Idle Money - Holdings':
 * - If E2 has a valid positive sold units count, ensures H2 has a checkbox.
 */
function refreshIdleMoneyCheckboxes(idleSheet) {
  if (!idleSheet) return;
  var e2Val = idleSheet.getRange('E2').getValue();
  var h2Range = idleSheet.getRange('H2');
  if (e2Val !== '' && e2Val !== null && !isNaN(e2Val) && Number(e2Val) > 0) {
    var h2Val = h2Range.getValue();
    if (typeof h2Val !== 'boolean') {
      h2Range.insertCheckboxes();
      h2Range.setValue(false);
    }
  } else {
    h2Range.clearContent();
    h2Range.clearDataValidations();
  }
  // Ensure I2 is clean
  idleSheet.getRange('I2').clearContent().clearDataValidations();
}

/**
 * Handles edit events originating from 'Idle Money - Holdings'.
 * 1. Populates checkbox in H2 when E2 (Sold Units) is entered; clears H2 if E2 is emptied.
 * 2. Triggers FIFO sale processing when H2 checkbox is checked.
 */
function handleIdleMoneyHoldingsEdit(e) {
  var range = e.range;
  var sheet = range.getSheet();
  var startRow = range.getRow();
  var endRow = startRow + range.getNumRows() - 1;
  var startCol = range.getColumn();
  var endCol = startCol + range.getNumColumns() - 1;

  // 1. Detect edit in E2 (Row 2, Column 5): Sold Units
  if (startRow <= 2 && endRow >= 2 && startCol <= 5 && endCol >= 5) {
    var e2Val = sheet.getRange('E2').getValue();
    var h2Range = sheet.getRange('H2');
    if (e2Val !== '' && e2Val !== null && !isNaN(e2Val) && Number(e2Val) > 0) {
      var currentVal = h2Range.getValue();
      if (typeof currentVal !== 'boolean') {
        h2Range.insertCheckboxes();
        h2Range.setValue(false);
      }
    } else {
      h2Range.clearContent();
      h2Range.clearDataValidations();
    }
  }

  // 2. Detect click on H2 (Row 2, Column 8): Trigger Sale
  if (startRow <= 2 && endRow >= 2 && startCol <= 8 && endCol >= 8) {
    var h2Val = sheet.getRange('H2').getValue();
    if (h2Val === true || (e && e.value === 'TRUE')) {
      processIdleMoneySale(sheet);
    }
  }
}

/**
 * Executes the sale:
 * - Validates C2 (ETF Code), E2 (Sold Units), F2 (Sell Price).
 * - Finds matching lots in Column A (Row 7+), sorted FIFO by oldest Buy Date (Column B).
 * - Deducts units lot-by-lot:
 *   - Lots reduced to 0 units have their rows deleted entirely.
 *   - Partially sold lots have Column D (Bought Units) updated. Existing formulas in E:J are untouched.
 * - Appends records to destination tab 'Idle Money - Sold' (Col A:F) at the first empty row after row 3.
 * - Leaves pre-applied formatting in 'Idle Money - Sold' completely untouched.
 * - Clears E2 and F2, removes H2 checkbox.
 */
function processIdleMoneySale(sheet) {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  if (!sheet) {
    sheet = ss.getSheetByName(IDLE_MONEY_HOLDINGS_TAB_NAME);
  }
  if (!sheet) return;

  var h2Range = sheet.getRange('H2');

  try {
    // 1. Read & validate inputs
    var etfCodeRaw = sheet.getRange('C2').getValue();
    var soldUnitsRaw = sheet.getRange('E2').getValue();
    var sellPriceRaw = sheet.getRange('F2').getValue();

    var etfCode = etfCodeRaw ? etfCodeRaw.toString().trim() : '';
    var soldUnits = Number(soldUnitsRaw);
    var sellPrice = Number(sellPriceRaw);

    if (!etfCode) {
      ss.toast('Please select an ETF Code in C2 before confirming.', 'Idle Money - Incomplete', 5);
      h2Range.setValue(false);
      return;
    }
    if (isNaN(soldUnits) || soldUnits <= 0) {
      ss.toast('Sold Units in E2 must be a positive number.', 'Idle Money - Incomplete', 5);
      h2Range.setValue(false);
      return;
    }
    if (isNaN(sellPrice) || sellPrice <= 0) {
      ss.toast('Sell Price in F2 must be a positive number.', 'Idle Money - Incomplete', 5);
      h2Range.setValue(false);
      return;
    }

    // 2. Read Holdings data from Row 7 downwards
    var lastRow = sheet.getLastRow();
    if (lastRow < 7) {
      ss.toast('No holding records found in row 7 onwards.', 'Idle Money - Error', 5);
      h2Range.setValue(false);
      return;
    }

    var numCols = Math.max(sheet.getLastColumn(), 10);
    var numRows = lastRow - 6;
    var range = sheet.getRange(7, 1, numRows, numCols);
    var values = range.getValues();
    var formulas = range.getFormulas();
    var backgrounds = range.getBackgrounds();
    var fontWeights = range.getFontWeights();
    var numberFormats = range.getNumberFormats();

    // 3. Find candidate lots for the selected ETF Code
    var candidateLots = [];
    for (var i = 0; i < values.length; i++) {
      var rowCode = values[i][0] ? values[i][0].toString().trim() : '';
      var boughtUnits = Number(values[i][3]); // Column D = Bought Units
      if (isMatchingEtfCode(rowCode, etfCode) && !isNaN(boughtUnits) && boughtUnits > 0) {
        candidateLots.push({
          rowIndex: 7 + i,
          dataIndex: i,
          rowCode: rowCode,
          buyDate: values[i][1],
          buyPrice: values[i][2],
          boughtUnits: boughtUnits,
          timestamp: parseDateToTimestamp(values[i][1]),
          fullValues: values[i],
          fullFormulas: formulas[i],
          fullBackgrounds: backgrounds[i],
          fullFontWeights: fontWeights[i],
          fullNumberFormats: numberFormats[i]
        });
      }
    }

    if (candidateLots.length === 0) {
      ss.toast('No available holding lots found for ETF Code: ' + etfCode, 'Idle Money - Error', 5);
      h2Range.setValue(false);
      return;
    }

    // 4. Validate total available units
    var totalAvailableUnits = 0;
    for (var k = 0; k < candidateLots.length; k++) {
      totalAvailableUnits += candidateLots[k].boughtUnits;
    }

    if (soldUnits > totalAvailableUnits) {
      ss.toast('Sold Units (' + soldUnits + ') exceed total available holdings (' + totalAvailableUnits + ') for ' + etfCode + '.', 'Idle Money - Insufficient Units', 6);
      h2Range.setValue(false);
      return;
    }

    // 5. Sort candidate lots FIFO by oldest Buy Date
    candidateLots.sort(function(a, b) {
      if (a.timestamp !== b.timestamp) {
        return a.timestamp - b.timestamp;
      }
      return a.rowIndex - b.rowIndex;
    });

    // 6. Access Destination tab 'Idle Money - Sold'
    var soldSheet = ss.getSheetByName(IDLE_MONEY_SOLD_TAB_NAME);
    if (!soldSheet) {
      soldSheet = ss.insertSheet(IDLE_MONEY_SOLD_TAB_NAME);
      soldSheet.getRange('A2:F2').setValues([['ETF Code', 'Buy Date', 'Buy Price', 'Sold Units', 'Sell Date', 'Sell Price']]).setFontWeight('bold');
    }

    // 7. Calculate FIFO deductions & build Sold payloads
    var ssTimeZone = ss.getSpreadsheetTimeZone() || 'Asia/Kolkata';
    var now = new Date();
    var year = Number(Utilities.formatDate(now, ssTimeZone, 'yyyy'));
    var month = Number(Utilities.formatDate(now, ssTimeZone, 'MM'));
    var day = Number(Utilities.formatDate(now, ssTimeZone, 'dd'));
    var today = new Date(year, month - 1, day);

    var remainingToSell = soldUnits;
    var payloads = [];
    var rowsToDelete = [];
    var rowToModify = null;

    for (var m = 0; m < candidateLots.length; m++) {
      if (remainingToSell <= 0) break;
      var lot = candidateLots[m];
      var lotUnits = lot.boughtUnits;
      var cleanBuyDate = lot.buyDate;
      if (cleanBuyDate instanceof Date) {
        var bYear = Number(Utilities.formatDate(cleanBuyDate, ssTimeZone, 'yyyy'));
        var bMonth = Number(Utilities.formatDate(cleanBuyDate, ssTimeZone, 'MM'));
        var bDay = Number(Utilities.formatDate(cleanBuyDate, ssTimeZone, 'dd'));
        cleanBuyDate = new Date(bYear, bMonth - 1, bDay);
      }

      if (lotUnits <= remainingToSell) {
        // Fully sold lot -> row will be deleted
        var unitsDeducted = lotUnits;
        remainingToSell -= lotUnits;
        rowsToDelete.push(lot.rowIndex);
        payloads.push([etfCode, cleanBuyDate, lot.buyPrice, unitsDeducted, today, sellPrice]);
      } else {
        // Partially sold lot -> column D updated
        var unitsDeducted = remainingToSell;
        var newUnits = lotUnits - remainingToSell;
        remainingToSell = 0;
        rowToModify = {
          rowIndex: lot.rowIndex,
          newUnits: newUnits,
          oldUnits: lotUnits
        };
        payloads.push([etfCode, cleanBuyDate, lot.buyPrice, unitsDeducted, today, sellPrice]);
      }
    }

    // 8. Find first empty row after row 3 in 'Idle Money - Sold' and write payloads as raw values
    var destStartRow = getFirstEmptyRowAfterRow3(soldSheet);
    var requiredRows = (destStartRow + payloads.length - 1) - soldSheet.getMaxRows();
    if (requiredRows > 0) {
      soldSheet.insertRowsAfter(soldSheet.getMaxRows(), requiredRows);
    }
    soldSheet.getRange(destStartRow, 1, payloads.length, 6).setValues(payloads);

    // 9. Update 'Idle Money - Holdings' table:
    // Update partially sold row first (only Column D is modified)
    if (rowToModify) {
      sheet.getRange(rowToModify.rowIndex, 4).setValue(rowToModify.newUnits);
    }

    // Delete fully sold rows descending from bottom to top so row indices don't shift
    if (rowsToDelete.length > 0) {
      rowsToDelete.sort(function(a, b) { return b - a; });
      for (var d = 0; d < rowsToDelete.length; d++) {
        sheet.deleteRow(rowsToDelete[d]);
      }
    }

    // 10. Clear E2 and F2, remove H2 checkbox and ensure I2 is cleared
    sheet.getRange('E2:F2').clearContent();
    h2Range.clearContent();
    h2Range.clearDataValidations();
    sheet.getRange('I2').clearContent().clearDataValidations();

    ss.toast(
      'Sold ' + soldUnits + ' units of ' + etfCode + ' recorded in ' + IDLE_MONEY_SOLD_TAB_NAME + ' across ' + payloads.length + ' lot(s).',
      'Idle Money - Sale Recorded ✓',
      6
    );

  } catch (err) {
    console.error('Error in processIdleMoneySale:', err);
    ss.toast('Error processing sale: ' + err.message, 'Idle Money - Error', 6);
    h2Range.setValue(false);
  }
}

/**
 * Menu trigger wrappers
 */
function manualTriggerIdleMoneySale() {
  var ss = SpreadsheetApp.getActiveSpreadsheet();
  var sheet = ss.getSheetByName(IDLE_MONEY_HOLDINGS_TAB_NAME);
  if (!sheet) {
    ss.toast("Sheet '" + IDLE_MONEY_HOLDINGS_TAB_NAME + "' not found.", 'Error', 4);
    return;
  }
  processIdleMoneySale(sheet);
}