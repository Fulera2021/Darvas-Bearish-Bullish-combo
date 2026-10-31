/**@OnlyCurrentDoc */

/**
 * ============================================================================
 * DARVAS BACKTESTER - CLIENT CONNECTOR FOR COPIED SHEETS
 * ============================================================================
 * 
 * Instructions:
 * 1. Paste your deployed Web App URL into the ENGINE_URL variable below.
 * 2. Save this script.
 * 3. Click "🚀 Darvas Backtest > 🌐 Run Backtest" in your Google Sheet.
 * ============================================================================
 */

// Replace the placeholder below with your Master Web App URL (ends with /exec)
const ENGINE_URL = "PASTE_YOUR_WEB_APP_URL_HERE";

function onOpen() {
  SpreadsheetApp.getUi().createMenu('🚀 Darvas Backtest')
    .addItem('🌐 Run Backtest (Sync from Yahoo Finance)', 'runBacktestClient')
    .addToUi();
}

function runTest() {
  runBacktestClient();
}

function runBacktestFromYahooFinance() {
  runBacktestClient();
}

function executeBacktestEngine() {
  runBacktestClient();
}

function runBacktestClient() {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const inputSheet = ss.getSheetByName('Input - Output');
  const dataSheet = ss.getSheetByName('Historical Data and Trades');
  const monthlySheet = ss.getSheetByName('Monthly Summary') || ss.getSheetByName('Monthly summary');
  const divSheet = ss.getSheetByName('Dividend Events') || ss.getSheetByName('Dividend events');

  if (!inputSheet) {
    SpreadsheetApp.getUi().alert("Error: 'Input - Output' tab not found.");
    return;
  }

  if (ENGINE_URL === "PASTE_YOUR_WEB_APP_URL_HERE" || !ENGINE_URL) {
    SpreadsheetApp.getUi().alert("Please configure ENGINE_URL with your Master Web App URL in Extensions > Apps Script.");
    return;
  }

  ss.toast("Connecting to central Darvas engine...", "Darvas Backtester", 10);

  const payload = {
    ticker: String(inputSheet.getRange('A2').getValue()).trim(),
    totalCapital: Number(inputSheet.getRange('B2').getValue()) || 40000,
    numParts: Number(inputSheet.getRange('C2').getValue()) || 4,
    startDate: inputSheet.getRange('D2').getDisplayValue(),
    endDate: inputSheet.getRange('E2').getDisplayValue(),
    targetPct: inputSheet.getRange('F2').getValue(),
    bullishMinReturnPct: inputSheet.getRange('G2').getValue()
  };

  const options = {
    method: "post",
    contentType: "application/json",
    payload: JSON.stringify(payload),
    muteHttpExceptions: true
  };

  try {
    const response = UrlFetchApp.fetch(ENGINE_URL, options);
    const res = JSON.parse(response.getContentText());

    if (!res.success) {
      SpreadsheetApp.getUi().alert("Engine Error: " + res.error);
      return;
    }

    const d = res.data;

    // 1. Populate Input - Output KPIs
    inputSheet.getRange('A6:F6').setValues([[
      d.totalPortfolioReturnAmt,
      d.totalRealizedProfit,
      d.tradeRealizedProfit,
      d.idleInterestTotal,
      d.dividendTotal,
      d.unrealizedOpenPnl
    ]]);

    inputSheet.getRange('A9:F9').setValues([[
      d.totalPortfolioReturnPct / 100,
      d.xirrPct / 100,
      d.maxDrawdownPct / 100,
      d.tradesRatio,
      d.endingOverallCapital,
      d.endingTrancheAmount
    ]]);

    // 2. Populate Trade Journal (Cols H onwards)
    if (dataSheet && d.trades && d.trades.length > 0) {
      const numCols = d.trades[0].length;
      const maxRow = Math.max(dataSheet.getLastRow(), d.trades.length + 10);
      if (maxRow > 2) {
        dataSheet.getRange(3, 8, maxRow - 2, numCols).clearContent();
      }
      dataSheet.getRange(3, 8, d.trades.length, numCols).setValues(d.trades);
    }

    // 3. Populate Monthly Summary
    if (monthlySheet && d.monthly && d.monthly.length > 0) {
      const numMCols = d.monthly[0].length;
      const maxM = Math.max(monthlySheet.getLastRow(), d.monthly.length + 10);
      if (maxM > 1) {
        monthlySheet.getRange(2, 1, maxM - 1, numMCols).clearContent();
      }
      monthlySheet.getRange(2, 1, d.monthly.length, numMCols).setValues(d.monthly);
    }

    // 4. Populate Dividend Events (Cols A-I)
    if (divSheet && d.dividends && d.dividends.length > 0) {
      const numDCols = d.dividends[0].length;
      const maxD = Math.max(divSheet.getLastRow(), d.dividends.length + 10);
      if (maxD > 1) {
        divSheet.getRange(2, 1, maxD - 1, numDCols).clearContent();
      }
      divSheet.getRange(2, 1, d.dividends.length, numDCols).setValues(d.dividends);
    }

    ss.toast("Backtest completed successfully!", "Success", 5);

  } catch (err) {
    SpreadsheetApp.getUi().alert("Connection error: " + err.toString());
  }
}
