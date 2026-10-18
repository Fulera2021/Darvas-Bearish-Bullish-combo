/**
 * ============================================================================
 * DARVAS BEARISH + BULLISH COMBO SYSTEMATIC SCANNER FOR GOOGLE SHEETS
 * ============================================================================
 * 
 * Target Sheet Tab: "Scanner"
 * 
 * Layout Mapping (Columns G through O):
 * - Rows 1-2 (Col G to O): Executive Summary KPI Cards:
 *                  - Col G:I -> Bullish Buy Triggered (number of stocks below it in Row 2)
 *                  - Col J:L -> Bearish Buy Triggered (number of stocks below it in Row 2)
 *                  - Col M:O -> Last Scan ran on (dd-mmm-yyyy HH:MM format in Row 2)
 * - Row 5: Column Headers
 * - Row 6: Dynamic Formulas (E6, F6, M6, N6)
 * - Row 7 downwards: Strategy Output (Columns G through O)
 * - Col G: NSE Code (Same format as input in Col A)
 * - Col H: Status (Sorted in this exact order:
 *                  1. Bullish Buy Triggered
 *                  2. Bearish Buy Triggered
 *                  3. Tracking for Bearish Buy Signal
 *                  4. Bullish Buy Running
 *                  5. Neutral / Inside 20W Range)
 * - Col I: Previous Week High (High of LAST TO LAST WEEK, W_{t-1})
 * - Col J: Last Week's Close (Friday Close of LAST COMPLETED WEEK, W_t)
 * - Col K: Buy Signal ("Bullish Buy Triggered", "Bearish Buy Triggered", or Blank)
 * - Col L: Breakout % (Rise) [(Close_J - High_I) / High_I, sorted least risen first]
 * - Col M: Buy Limit Ceiling (+0.5%) [Formula in M6: CEILING(J6:J*1.005, 0.05)]
 * - Col N: CMP [Formula in N6: GOOGLEFINANCE(ticker, "price")]
 * - Col O: 20W Low Breakdown ("20W Low Breakdown" if touched in recently completed week, else Blank)
 * *(Columns P and Q are omitted / deleted)*
 * 
 * Strategy Rules & State Tracking:
 * 1. Bullish Buy Triggered: When Close of last week (Col J) > rolling 20-week high for the first time.
 * 2. Bullish Buy Running: Stocks previously bought on Bullish signal that have NOT touched the 20-week low yet (e.g. NSE:ABCAPITAL).
 * 3. Bearish Tracking Activation: When 20-week low is TOUCHED (Weekly Low <= 20W Low),
 *    bullish holding terminates and system starts tracking for Bearish Buy Signal (e.g. NSE:YESBANK).
 * 4. Bearish Buy Triggered: While tracking 20W low, Close of last week (Col J) > High of last to last week (Col I).
 * 5. Col O (20W Low Breakdown): Highlights stocks whose weekly low touched/breached
 *    the 20-week low during the recently completed week (fresh breakdown).
 * ============================================================================
 */

// Configuration Constants
const CONFIG = {
  SHEET_NAME: 'Scanner',
  INPUT_START_ROW: 7,
  INPUT_COL: 1,           // Column A
  OUTPUT_START_ROW: 7,
  OUTPUT_START_COL: 7,    // Column G
  OUTPUT_NUM_COLS: 9,     // Columns G to O (9 columns)
  FORMULA_ROW: 6,
  LOOKBACK_WEEKS: 20,
  // Col Q (column 17): GTT Select checkbox — auto-populated for buy-eligible stocks
  GTT_SELECT_COL: 17,     // Column Q
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
  DATA_START_ROW: 4,      // B4 onwards for stock codes
  TICKER_COL: 2,          // Column B
  GTT_PRICE_COL: 3,       // Column C
  SIGNAL_TYPE_COL: 4,     // Column D: 'Bullish Buy' or 'Bearish Buy'
  DELETE_CHK_COL: 10,     // Column J: Delete checkbox
};

/**
 * Creates custom menu when Google Sheet is opened.
 */
function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('⚡ Darvas Scanner')
    .addItem('▶ Run Scanner Now', 'runDarvasScanner')
    .addItem('🛡 Force Fallback: Run via GoogleFinance', 'runDarvasScannerGoogleFinanceOnly')
    .addSeparator()
    .addItem('🎨 Apply Visual Formatting Rules', 'applyScannerFormattingRulesMenu')
    .addItem('⏰ Setup Auto Weekly Trigger (Saturday 8 AM)', 'setupWeeklyTrigger')
    .addItem('🗑 Remove Automated Trigger', 'removeWeeklyTrigger')
    .addSeparator()
    .addItem('📋 Setup GTT Tracker Tab', 'setupGttTrackerSheet')
    .addSeparator()
    .addItem('ℹ About Scanner & Rules', 'showAboutDialog')
    .addToUi();
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
      const statuses = sheet.getRange(CONFIG.OUTPUT_START_ROW, 8, lastRow - CONFIG.OUTPUT_START_ROW + 1, 1).getValues();
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
function runDarvasScanner(forceGoogleFinance = false) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName(CONFIG.SHEET_NAME);
  
  if (!sheet) {
    SpreadsheetApp.getUi().alert(`Error: Sheet tab named '${CONFIG.SHEET_NAME}' was not found. Please create it or verify the name.`);
    return;
  }

  const startTime = new Date().getTime();

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

  const processedMap = {};
  const missingTickers = [];

  if (forceGoogleFinance) {
    // User explicitly requested to run via GoogleFinance engine
    ss.toast(`Running scan for ${rawTickers.length} stocks via GoogleFinance engine...`, '⚡ Backup Mode', 15);
    missingTickers.push(...rawTickers);
  } else {
    // 2. Format tickers for Yahoo Finance API
    const yfTickerMap = {};
    rawTickers.forEach(t => {
      yfTickerMap[t] = convertToYfTicker(t);
    });

    // 3. Batch fetch weekly data in parallel using UrlFetchApp.fetchAll
    ss.toast(`Analyzing ${rawTickers.length} stocks via Yahoo Finance...`, 'Darvas Scanner', 15);
    const requests = rawTickers.map(t => {
      const yfTicker = yfTickerMap[t];
      return {
        url: `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(yfTicker)}?range=2y&interval=1wk`,
        method: 'get',
        headers: {
          'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        },
        muteHttpExceptions: true
      };
    });

    let responses = null;
    try {
      responses = UrlFetchApp.fetchAll(requests);
    } catch (err) {
      Logger.log('fetchAll failed on query1, attempting fallback to query2: ' + err);
      try {
        const fallbackReqs = requests.map(r => ({
          ...r,
          url: r.url.replace('query1.finance.yahoo.com', 'query2.finance.yahoo.com')
        }));
        responses = UrlFetchApp.fetchAll(fallbackReqs);
      } catch (err2) {
        Logger.log('Yahoo query2 fetchAll also failed: ' + err2);
        responses = null;
      }
    }

    // 4. Process each stock's historical bars from Yahoo Finance
    for (let i = 0; i < rawTickers.length; i++) {
      const rawTicker = rawTickers[i];
      let bars = null;
      if (responses && responses[i]) {
        bars = parseYahooFinanceBars(responses[i]);
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
  if (missingTickers.length > 0) {
    const reasonMsg = forceGoogleFinance 
      ? `Fetching ${missingTickers.length} stock(s) via GoogleFinance...` 
      : `Yahoo Finance unavailable for ${missingTickers.length} stock(s). Using GoogleFinance fallback...`;
    ss.toast(reasonMsg, '⚡ GoogleFinance Fallback', 10);
    try {
      const gfBarsMap = fetchBarsFromGoogleFinance(ss, missingTickers);
      missingTickers.forEach(ticker => {
        const bars = gfBarsMap[ticker];
        if (bars && bars.length >= 25) {
          const analysis = analyzeStockFromBars(ticker, bars);
          if (analysis) {
            processedMap[ticker] = analysis;
          }
        }
      });
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

  // 5. Sort processed stocks strictly in Column H priority:
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

  // 5b. Filter out stocks already present in GTT Tracker (they have been queued for GTT order)
  const ss2 = SpreadsheetApp.getActiveSpreadsheet();
  const gttSheetForFilter = ss2.getSheetByName(GTT_CONFIG.SHEET_NAME);
  if (gttSheetForFilter) {
    const gttLastRow = gttSheetForFilter.getLastRow();
    if (gttLastRow >= GTT_CONFIG.DATA_START_ROW) {
      const gttTickers = gttSheetForFilter
        .getRange(GTT_CONFIG.DATA_START_ROW, GTT_CONFIG.TICKER_COL, gttLastRow - GTT_CONFIG.DATA_START_ROW + 1, 1)
        .getValues()
        .map(r => String(r[0]).trim().toUpperCase())
        .filter(t => t !== '');
      if (gttTickers.length > 0) {
        const gttSet = new Set(gttTickers);
        processedData = processedData.filter(item => !gttSet.has(String(item.ticker).trim().toUpperCase()));
      }
    }
  }

  // 6. Ensure formulas in Row 6 are set correctly (Col J is Close, so M6 uses J6:J)
  ensureRow6Formulas(sheet);

  // 7. Prepare batch values to write to sheet (Columns G to O)
  // Columns:
  // Col G: NSE Code
  // Col H: Status
  // Col I: Previous Week High  (High of LAST TO LAST WEEK)
  // Col J: Last Week's Close   (Friday Close of LAST COMPLETED WEEK)
  // Col K: Buy Signal
  // Col L: Breakout % (Rise)   [(Close_J - High_I) / High_I]
  // Col M: Buy Limit Ceiling (+0.5%) -> Handled by M6 Formula: CEILING(J6:J*1.005, 0.05)
  // Col N: CMP -> Handled by N6 Formula: GOOGLEFINANCE(ticker, "price")
  // Col O: 20W Low Breakdown -> Shows '20W Low Breakdown' if 20W low touched in last completed week, else Blank

  const outputRows = processedData.map(item => {
    return [
      item.ticker,                                                  // Col G: NSE Code
      item.status,                                                  // Col H: Status
      item.prevWeekHigh !== '' ? Number(item.prevWeekHigh) : '',    // Col I: Previous Week High
      item.lastWeekClose !== '' ? Number(item.lastWeekClose) : '',  // Col J: Last Week's Close
      item.buySignal,                                               // Col K: Buy Signal
      item.breakoutPct !== null ? Number(item.breakoutPct) : '',    // Col L: Breakout % (Rise)
      '',                                                           // Col M: Formula in M6
      '',                                                           // Col N: Formula in N6
      item.colO_breakdown                                           // Col O: 20W Low Breakdown
    ];
  });

  // 8. Write to Sheet (Columns G through O)
  const numOutputRows = outputRows.length;
  const numOutputCols = CONFIG.OUTPUT_NUM_COLS; // 9 columns (G to O)
  
  // Clear any old data in G7:Q from previous runs (including old GTT checkboxes in Col Q)
  const currentMaxRow = Math.max(sheet.getLastRow(), CONFIG.OUTPUT_START_ROW + numOutputRows + 10);
  if (currentMaxRow >= CONFIG.OUTPUT_START_ROW) {
    // Clear G:O (output data)
    sheet.getRange(CONFIG.OUTPUT_START_ROW, CONFIG.OUTPUT_START_COL, currentMaxRow - CONFIG.OUTPUT_START_ROW + 1, numOutputCols).clearContent();
    // Clear Q (old GTT checkboxes)
    sheet.getRange(CONFIG.OUTPUT_START_ROW, CONFIG.GTT_SELECT_COL, currentMaxRow - CONFIG.OUTPUT_START_ROW + 1, 1).clearContent().clearDataValidations();
  }

  // Set new values
  sheet.getRange(CONFIG.OUTPUT_START_ROW, CONFIG.OUTPUT_START_COL, numOutputRows, numOutputCols).setValues(outputRows);

  // 9. Format columns with proper numbers and percentages
  formatScannerDataRange(sheet, CONFIG.OUTPUT_START_ROW, numOutputRows);

  // 10. Automatically apply conditional formatting rules
  applyScannerFormattingRules(sheet);

  const durationSec = ((new Date().getTime() - startTime) / 1000).toFixed(1);
  const bullishCount = processedData.filter(d => d.sortGroup === 1).length;
  const bearishCount = processedData.filter(d => d.sortGroup === 2).length;
  const trackingCount = processedData.filter(d => d.sortGroup === 3).length;
  const runningCount = processedData.filter(d => d.sortGroup === 4).length;
  const breakdownCount = processedData.filter(d => d.colO_breakdown !== '').length;

  // 11. Populate executive summary KPI cards (Rows 1-2 from Col G onwards)
  updateScannerSummaryHeader(sheet, bullishCount, bearishCount);

  // 12. Populate GTT Select checkboxes in Col Q for buy-eligible stocks
  populateGttCheckboxes(sheet, CONFIG.OUTPUT_START_ROW, numOutputRows, processedData);

  ss.toast(`Scan complete in ${durationSec}s! Found ${bullishCount} Bullish, ${bearishCount} Bearish buys, ${trackingCount} Tracking, and ${runningCount} Bullish Running.`, '⚡ Scan Finished', 8);
}

// ============================================================================
// GTT ORDER TRACKING SYSTEM
// ============================================================================

/**
 * onEdit simple trigger — fires automatically when any cell in the spreadsheet
 * is edited by the user.
 *
 * When a checkbox in Col Q (GTT Select) on the Scanner tab is checked:
 *  1. Reads the stock code (Col G) and GTT price (Col M) from that row.
 *  2. Appends them to the GTT Tracker tab (starting at B4 / C4 / D4).
 *  3. Clears that row's data from the Scanner tab (Cols G:Q) so it disappears
 *     from scan results. Col A (input ticker) is never touched.
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
    // BRANCH A: Scanner tab — Col Q (GTT Select) checkbox checked
    // -----------------------------------------------------------------------
    if (sheetName === CONFIG.SHEET_NAME &&
        editedCol === CONFIG.GTT_SELECT_COL &&
        editedRow >= CONFIG.OUTPUT_START_ROW &&
        e.value === 'TRUE') {

      // Read stock code (Col G = col 7) and GTT price (Col M = col 13)
      const ticker    = sheet.getRange(editedRow, 7).getValue();
      const gttPrice  = sheet.getRange(editedRow, 13).getValue();
      const rawSignal = sheet.getRange(editedRow, 11).getValue(); // Col K: Buy Signal

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
      const gttLastRow = gttSheet.getLastRow();
      const nextRow = Math.max(gttLastRow + 1, GTT_CONFIG.DATA_START_ROW);

      // Write: Col B = ticker, Col C = GTT Price, Col D = Signal Short Label
      gttSheet.getRange(nextRow, GTT_CONFIG.TICKER_COL).setValue(ticker).setFontWeight('bold');
      if (gttPrice !== '' && gttPrice !== null) {
        gttSheet.getRange(nextRow, GTT_CONFIG.GTT_PRICE_COL)
          .setValue(gttPrice)
          .setNumberFormat('#,##0.00');
      }
      gttSheet.getRange(nextRow, GTT_CONFIG.SIGNAL_TYPE_COL).setValue(signalShort);

      // Light formatting for new GTT row
      gttSheet.getRange(nextRow, GTT_CONFIG.TICKER_COL, 1, 3)
        .setBackground('#F0FDF4')
        .setFontColor('#14532D');

      // Add delete checkbox (Col J) for this new row
      refreshGttDeleteCheckboxes(gttSheet);

      // Clear the stock's row from Scanner (G:Q only, leave Col A untouched)
      sheet.getRange(editedRow, 7, 1, 9).clearContent();
      sheet.getRange(editedRow, CONFIG.GTT_SELECT_COL).clearContent().clearDataValidations();

      ss.toast(`✅ ${ticker} → GTT Tracker (row ${nextRow}), GTT price ₹${gttPrice}.`, 'GTT Order Queued', 5);
      return;
    }

    // -----------------------------------------------------------------------
    // BRANCH B: GTT Tracker tab — Col J (Delete) checkbox checked
    // -----------------------------------------------------------------------
    if (sheetName === GTT_CONFIG.SHEET_NAME &&
        editedCol === GTT_CONFIG.DELETE_CHK_COL &&
        editedRow >= GTT_CONFIG.DATA_START_ROW &&
        e.value === 'TRUE') {

      const ticker = sheet.getRange(editedRow, GTT_CONFIG.TICKER_COL).getValue();

      // Delete the data in B:J for this row, shifting rows up
      // Delete columns B–J (cols 2–10) in this row by deleting the entire row
      // then optionally shift: deleteRow removes the row entirely and shifts everything up
      sheet.deleteRow(editedRow);

      // Refresh delete checkboxes for remaining data rows
      refreshGttDeleteCheckboxes(sheet);

      ss.toast(`🗑 ${ticker} removed from GTT Tracker.`, 'GTT Removed', 4);
      return;
    }

  } catch (err) {
    Logger.log('onEdit GTT error: ' + err);
  }
}

/**
 * Populates GTT Select checkboxes in Column Q for rows where status is
 * 'Bullish Buy Triggered' or 'Bearish Buy Triggered'. Other rows get no checkbox.
 *
 * @param {SpreadsheetApp.Sheet} sheet The Scanner sheet.
 * @param {number} startRow The first data row (Row 7).
 * @param {number} numRows Total number of output rows written.
 * @param {Array} processedData The sorted processed data array.
 */
function populateGttCheckboxes(sheet, startRow, numRows, processedData) {
  if (numRows <= 0) return;

  // Add header label in Q5 if it's blank
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
 * - Places Delete checkboxes in Col J for all rows with data in Col B.
 * - Does NOT overwrite existing header content if the tab already exists.
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

  // --- Formulas in Row 3 (E3:I3) — always (re)set so they stay current ---
  // E3: Qty you can buy based on budget in Current Holdings D3
  gttSheet.getRange('E3').setFormula(
    "=ARRAYFORMULA(IF(C3:C=\"\",,FLOOR('Current Holdings'!$D$3/C3:C,1)))"
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

  // --- Delete checkboxes in Col J (J4 onwards for non-empty B rows) ---
  refreshGttDeleteCheckboxes(gttSheet);

  if (isNew) {
    // Only show the 'created' message for brand-new tabs
    try {
      SpreadsheetApp.getUi().alert(
        '✅ GTT Tracker tab created!\n\n' +
        'Stocks appear here when you check the ☑ GTT Select checkbox (Col Q) in the Scanner tab.\n\n' +
        '• Col B: NSE Code\n• Col C: GTT Price\n• Col D: Signal Type\n' +
        '• Col E: Qty (budget ÷ GTT price)\n• Col F: Total cost\n' +
        '• Col G: In Holdings?\n• Col H: CMP\n• Col I: GTT vs CMP %\n' +
        '• Col J: ☑ Check to DELETE row'
      );
    } catch (uiErr) { /* suppress if called from trigger */ }
  } else {
    try {
      SpreadsheetApp.getUi().alert('✅ GTT Tracker formulas refreshed in E3:I3 and Col J delete checkboxes updated.');
    } catch (uiErr) { /* suppress if called from trigger */ }
  }

  return gttSheet;
}

/**
 * Refreshes the delete-checkbox column (Col J) in the GTT Tracker sheet.
 * Adds a checkbox for every row in Col J where Col B (NSE Code) is non-empty,
 * starting from DATA_START_ROW. Removes checkboxes from rows where Col B is empty.
 *
 * @param {SpreadsheetApp.Sheet} gttSheet The GTT Tracker sheet.
 */
function refreshGttDeleteCheckboxes(gttSheet) {
  const lastRow = gttSheet.getLastRow();
  if (lastRow < GTT_CONFIG.DATA_START_ROW) return;

  const numRows = lastRow - GTT_CONFIG.DATA_START_ROW + 1;
  const tickerValues = gttSheet
    .getRange(GTT_CONFIG.DATA_START_ROW, GTT_CONFIG.TICKER_COL, numRows, 1)
    .getValues();

  const checkboxRule = SpreadsheetApp.newDataValidation().requireCheckbox().build();

  // First clear any old checkboxes in J column beyond last row
  gttSheet.getRange(GTT_CONFIG.DATA_START_ROW, GTT_CONFIG.DELETE_CHK_COL, numRows, 1)
    .clearContent()
    .clearDataValidations()
    .setBackground(null);

  for (let i = 0; i < numRows; i++) {
    const row = GTT_CONFIG.DATA_START_ROW + i;
    const ticker = String(tickerValues[i][0]).trim();
    const cell = gttSheet.getRange(row, GTT_CONFIG.DELETE_CHK_COL);
    if (ticker !== '') {
      cell
        .setDataValidation(checkboxRule)
        .setValue(false)
        .setBackground('#FEF2F2')   // Soft red tint — signals 'delete action'
        .setHorizontalAlignment('center');
    }
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
 * Fetches historical weekly OHLC bars in parallel via a hidden cache tab.
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

  // Ensure cacheSheet has enough columns: 6 columns per ticker
  const requiredCols = Math.max(tickers.length * 6 + 10, 26);
  const currentCols = cacheSheet.getMaxColumns();
  if (currentCols < requiredCols) {
    cacheSheet.insertColumnsAfter(currentCols, requiredCols - currentCols);
  }

  // Populate GOOGLEFINANCE formulas for all tickers across columns
  // E.g. Stock 0 in col 1 (A), Stock 1 in col 7 (G), etc.
  const formulaRow = [];
  for (let i = 0; i < tickers.length; i++) {
    const ticker = tickers[i];
    const formula = `=IFERROR(GOOGLEFINANCE("${ticker}", "all", TODAY()-450, TODAY(), "WEEKLY"), "")`;
    formulaRow.push(formula, '', '', '', '', '');
  }

  // Write formulas in Row 1
  cacheSheet.getRange(1, 1, 1, formulaRow.length).setFormulas([formulaRow]);
  SpreadsheetApp.flush();

  // Allow Google's internal servers to populate the data array
  Utilities.sleep(1500);
  SpreadsheetApp.flush();

  // Polling wait if formulas are still evaluating (up to 4 seconds)
  let waitLoops = 0;
  while (cacheSheet.getLastRow() < 2 && waitLoops < 4) {
    Utilities.sleep(1000);
    SpreadsheetApp.flush();
    waitLoops++;
  }

  const finalLastRow = Math.max(cacheSheet.getLastRow(), 2);
  const finalLastCol = formulaRow.length;
  const values = cacheSheet.getRange(1, 1, finalLastRow, finalLastCol).getValues();

  const barsByTicker = {};

  for (let i = 0; i < tickers.length; i++) {
    const ticker = tickers[i];
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
      const b = bars[r];
      if (consolidatedBars.length > 0) {
        const prev = consolidatedBars[consolidatedBars.length - 1];
        const diffDays = (b.date.getTime() - prev.date.getTime()) / (1000 * 3600 * 24);
        if (diffDays < 5) {
          prev.high = Math.max(prev.high, b.high);
          prev.low = Math.min(prev.low, b.low);
          prev.close = b.close;
          continue;
        }
      }
      consolidatedBars.push(b);
    }

    barsByTicker[ticker] = consolidatedBars;
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

  const lastWeekBar = bars[currentCompletedIdx];         // Last Week (Col J)
  const lastToLastWeekBar = bars[prevWeekIdx];           // Last to Last Week (Col I)

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

  // Populate Column O: '20W Low Breakdown' if 20-week low was touched in recently completed week
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
    prevWeekHigh: lastToLastWeekHigh.toFixed(2),  // Col I: High of Last to Last Week
    lastWeekClose: lastWeekClose.toFixed(2),      // Col J: Close of Last Week
    buySignal: buySignal,                        // Col K: Buy Signal
    breakoutPct: breakoutPct,                    // Col L: Breakout % (Rise)
    colO_breakdown: colO_breakdown,              // Col O: 20W Low Breakdown
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
 * Dedicated menu function to force execution via GoogleFinance backup engine.
 */
function runDarvasScannerGoogleFinanceOnly() {
  runDarvasScanner(true);
}

/**
 * Ensures required formulas are placed in Row 6 (E6, F6, M6, N6).
 * Notice: Since Col J is Close of Last Week, M6 formula uses J6:J.
 */
function ensureRow6Formulas(sheet) {
  const formulas = {
    'E6': "=IFERROR(ARRAYFORMULA(XLOOKUP(G6:G,'Current Holdings'!B:B,'Current Holdings'!C:C,,,-1)))",
    'F6': "=IFERROR(ARRAYFORMULA(IF(E6:E=\"\",,N6:N/E6:E-1)))",
    'M6': "=IFERROR(ARRAYFORMULA(IF(K6:K=\"\",,CEILING(J6:J*1.005,0.05))))",
    'N6': "=IFERROR(MAP(G6:G,LAMBDA(ticker, IF(ticker=\"\",, GOOGLEFINANCE(ticker,\"price\")))))"
  };

  for (const cell in formulas) {
    sheet.getRange(cell).setFormula(formulas[cell]);
  }
}

/**
 * Formats columns G:O with clean numbers, percentages, and currencies.
 */
function formatScannerDataRange(sheet, startRow, numRows) {
  if (numRows <= 0) return;

  const FMT_PRICE = '#,##0.00';
  const FMT_PERCENT = '0.00%';

  // Format Col E & F
  sheet.getRange(startRow, 5, numRows, 1).setNumberFormat(FMT_PRICE);   // Col E: Last Buy Price
  sheet.getRange(startRow, 6, numRows, 1).setNumberFormat(FMT_PERCENT); // Col F: Distance %

  // Format Col I, J: Prices (Col I: Prev Week High, Col J: Last Week Close)
  sheet.getRange(startRow, 9, numRows, 2).setNumberFormat(FMT_PRICE);   // Col I, J: High, Close

  // Format Col L: Breakout %
  sheet.getRange(startRow, 12, numRows, 1).setNumberFormat(FMT_PERCENT); // Col L: Breakout %

  // Format Col M, N: Prices
  sheet.getRange(startRow, 13, numRows, 2).setNumberFormat(FMT_PRICE);  // Col M, N: Ceiling, CMP

  // Format Col O: Center alignment
  sheet.getRange(startRow, 15, numRows, 1).setHorizontalAlignment('center'); // Col O
}

/**
 * Populates top executive summary KPI cards in Rows 1-2 across Columns G:O.
 * Displays:
 * 1. Col G:I (Row 1-2) -> Bullish Buy Triggered (number of stocks below it in Row 2)
 * 2. Col J:L (Row 1-2) -> Bearish Buy Triggered (number of stocks below it in Row 2)
 * 3. Col M:O (Row 1-2) -> Last Scan ran on (dd-mmm-yyyy HH:MM format in Row 2)
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

  // Safely clear old contents, formats & reset merges across G1:O3
  const oldHeaderRange = sheet.getRange('G1:O3');
  oldHeaderRange.breakApart();
  oldHeaderRange.clearContent();
  oldHeaderRange.clearFormat();

  // --- CARD 1: Bullish Buy Triggered (Cols G:I, Rows 1-2) ---
  sheet.getRange('G1:I1').merge()
    .setValue('Bullish Buy Triggered')
    .setBackground('#D1FAE5')
    .setFontColor('#065F46')
    .setFontSize(11)
    .setFontWeight('bold')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  sheet.getRange('G2:I2').merge()
    .setValue(bullishCount)
    .setBackground('#ECFDF5')
    .setFontColor('#047857')
    .setFontSize(20)
    .setFontWeight('bold')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  sheet.getRange('G1:I2').setBorder(true, true, true, true, false, false, '#A7F3D0', SpreadsheetApp.BorderStyle.SOLID_MEDIUM);

  // --- CARD 2: Bearish Buy Triggered (Cols J:L, Rows 1-2) ---
  sheet.getRange('J1:L1').merge()
    .setValue('Bearish Buy Triggered')
    .setBackground('#DBEAFE')
    .setFontColor('#1E40AF')
    .setFontSize(11)
    .setFontWeight('bold')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  sheet.getRange('J2:L2').merge()
    .setValue(bearishCount)
    .setBackground('#EFF6FF')
    .setFontColor('#1D4ED8')
    .setFontSize(20)
    .setFontWeight('bold')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  sheet.getRange('J1:L2').setBorder(true, true, true, true, false, false, '#BFDBFE', SpreadsheetApp.BorderStyle.SOLID_MEDIUM);

  // --- CARD 3: Last Scan ran on (Cols M:O, Rows 1-2) ---
  sheet.getRange('M1:O1').merge()
    .setValue('Last Scan ran on')
    .setBackground('#E2E8F0')
    .setFontColor('#1E293B')
    .setFontSize(11)
    .setFontWeight('bold')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  sheet.getRange('M2:O2').merge()
    .setValue(timestampStr)
    .setBackground('#F8FAFC')
    .setFontColor('#0F172A')
    .setFontSize(13)
    .setFontWeight('bold')
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  sheet.getRange('M1:O2').setBorder(true, true, true, true, false, false, '#CBD5E1', SpreadsheetApp.BorderStyle.SOLID_MEDIUM);
}

/**
 * Applies visual conditional formatting rules to highlight signals, statuses, and breakdowns.
 */
function applyScannerFormattingRules(sheet) {
  const rules = [];

  // 1. Buy Signal Column (Col K) Highlights
  // Bullish Buy Triggered -> Soft Emerald Green
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo('Bullish Buy Triggered')
    .setBackground('#D1FAE5') // Light Emerald
    .setFontColor('#065F46')  // Dark Emerald
    .setBold(true)
    .setRanges([sheet.getRange('K7:K500')])
    .build());

  // Bearish Buy Triggered -> Soft Cyan / Blue
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo('Bearish Buy Triggered')
    .setBackground('#DBEAFE') // Light Blue
    .setFontColor('#1E40AF')  // Dark Blue
    .setBold(true)
    .setRanges([sheet.getRange('K7:K500')])
    .build());

  // 2. Status Column (Col H) Highlights (In Priority Order)
  // 1. Bullish Buy Triggered -> Soft Emerald
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo('Bullish Buy Triggered')
    .setBackground('#D1FAE5')
    .setFontColor('#065F46')
    .setBold(true)
    .setRanges([sheet.getRange('H7:H500')])
    .build());

  // 2. Bearish Buy Triggered -> Soft Blue
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo('Bearish Buy Triggered')
    .setBackground('#DBEAFE')
    .setFontColor('#1E40AF')
    .setBold(true)
    .setRanges([sheet.getRange('H7:H500')])
    .build());

  // 3. Bullish Buy Running -> Soft Mint / Teal
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo('Bullish Buy Running')
    .setBackground('#CCFBF1') // Light Teal
    .setFontColor('#0F766E')  // Dark Teal
    .setBold(true)
    .setRanges([sheet.getRange('H7:H500')])
    .build());

  // 4. Tracking for Bearish Buy Signal -> Soft Amber / Orange
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo('Tracking for Bearish Buy Signal')
    .setBackground('#FEF3C7') // Light Amber
    .setFontColor('#92400E')  // Dark Amber
    .setRanges([sheet.getRange('H7:H500')])
    .build());

  // 5. Col O (20W Low Breakdown) -> Soft Red Alert Badge
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .whenTextEqualTo('20W Low Breakdown')
    .setBackground('#FEE2E2') // Light Red
    .setFontColor('#991B1B')  // Dark Red
    .setBold(true)
    .setRanges([sheet.getRange('O7:O500')])
    .build());

  // 4. Distance between CMP and Last Buy Price (Col F)
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

  // 5. Breakout % (Rise) (Col L) Color Gradient (Low = Green, High = Yellow/Orange)
  rules.push(SpreadsheetApp.newConditionalFormatRule()
    .setGradientMinpointWithValue('#D1FAE5', SpreadsheetApp.InterpolationType.MIN, '')
    .setGradientMidpointWithValue('#FEF9C3', SpreadsheetApp.InterpolationType.PERCENTILE, '50')
    .setGradientMaxpointWithValue('#FED7AA', SpreadsheetApp.InterpolationType.MAX, '')
    .setRanges([sheet.getRange('L7:L500')])
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
          <td style="padding: 6px; border: 1px solid #cbd5e1;">Close of Last Week (Col J) > 20-Week High (Fresh Breakout)</td>
          <td style="padding: 6px; border: 1px solid #cbd5e1;">Deploy Slot 1 Macro Trend Compounder</td>
        </tr>
        <tr>
          <td style="padding: 6px; border: 1px solid #cbd5e1; font-weight: bold; color: #1e40af;">2. Bearish Buy Triggered</td>
          <td style="padding: 6px; border: 1px solid #cbd5e1;">20W Low Touched & Close of Last Week (Col J) > High of Last to Last Week (Col I)</td>
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
          <td style="padding: 6px; border: 1px solid #cbd5e1; font-weight: bold; color: #b91c1c;">Col O: 20W Low Breakdown</td>
          <td style="padding: 6px; border: 1px solid #cbd5e1;">Low of recently completed week <= 20W Low</td>
          <td style="padding: 6px; border: 1px solid #cbd5e1;">Alert: Fresh 20W low touched this week!</td>
        </tr>
      </table>

      <p><b>Columns:</b><br>
      • <b>Col I:</b> High of Last to Last Week<br>
      • <b>Col J:</b> Close of Last Week<br>
      • <b>Col L:</b> Breakout % = (Col J - Col I) / Col I<br>
      • <b>Col M:</b> Buy Limit Ceiling = CEILING(Col J * 1.005, 0.05)<br>
      • <b>Col O:</b> 20W Low Breakdown (Alert for fresh breakdown this week)</p>

      <p><b>Sorting Order in Column H:</b><br>
      1. Bullish Buy Triggered (sorted by least Breakout % rise first)<br>
      2. Bearish Buy Triggered (sorted by least Breakout % rise first)<br>
      3. Tracking for Bearish Buy Signal<br>
      4. Bullish Buy Running (holding above 20W floor)<br>
      5. Neutral / Inside 20W Range</p>
      <p style="color: #64748b; font-size: 11px;">Powered by Google Apps Script, Yahoo Finance v8 API & GoogleFinance native engine.</p>
    </div>
  `;
  const htmlOutput = HtmlService.createHtmlOutput(htmlContent)
    .setWidth(550)
    .setHeight(430);
  SpreadsheetApp.getUi().showModalDialog(htmlOutput, 'About Darvas Strategy Scanner');
}

/**
 * Helper to convert Google Finance ticker format to Yahoo Finance ticker format.
 * E.g., 'NSE:INFY' -> 'INFY.NS', 'NSE:YESBANK' -> 'YESBANK.NS', 'BSE:500209' -> '500209.BO'
 */
function convertToYfTicker(ticker) {
  let clean = String(ticker).trim().toUpperCase();
  if (clean.startsWith('NSE:')) {
    clean = clean.substring(4).trim() + '.NS';
  } else if (clean.startsWith('BSE:')) {
    clean = clean.substring(4).trim() + '.BO';
  } else if (!clean.endsWith('.NS') && !clean.endsWith('.BO')) {
    clean = clean + '.NS';
  }
  return clean;
}
