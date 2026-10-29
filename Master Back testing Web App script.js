/**@OnlyCurrentDoc */

/**
 * ============================================================================
 * DARVAS BEARISH + BULLISH COMBO SYSTEMATIC BACKTEST ENGINE - MASTER WEB APP
 * ============================================================================
 * 
 * This master script serves both:
 * 1. Local execution inside the Master Sheet (via UI Menu)
 * 2. Centralized Web App Engine for all copied user sheets (via doPost endpoint)
 * ============================================================================
 */

function onOpen() {
  const ui = SpreadsheetApp.getUi();
  ui.createMenu('🚀 Darvas Backtest')
    .addItem('▶ Run Backtest (Using Sheet Data)', 'runBacktestFromSheet')
    .addItem('🌐 Run Backtest (Sync from Yahoo Finance)', 'runBacktestFromYahooFinance')
    .addSeparator()
    .addSubMenu(ui.createMenu('🎨 Apply Executive Theme (Rows 5-9)')
      .addItem('⭐ Option 1: Institutional Navy & Ice Blue', 'applyThemeNavy')
      .addItem('💜 Option 2: Royal Indigo & Lilac', 'applyThemeIndigo')
      .addItem('🌿 Option 3: Bloomberg Emerald & Mint', 'applyThemeEmerald')
      .addSeparator()
      .addItem('🔄 Option 4: Clean Minimal Slate Gray', 'applyThemeCleanGray'))
    .addToUi();
}

function runBacktestFromSheet() {
  executeBacktestEngine(false);
}

function runBacktestFromYahooFinance() {
  executeBacktestEngine(true);
}

/**
 * Local Execution Runner: Reads inputs from master sheet and writes results locally
 */
function executeBacktestEngine(useYahooFinance) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const inputSheet = ss.getSheetByName('Input - Output');
  const dataSheet = ss.getSheetByName('Historical Data and Trades');
  const monthlySheet = ss.getSheetByName('Monthly Summary') || ss.getSheetByName('Monthly summary');
  const dividendSheet = ss.getSheetByName('Dividend Events') || ss.getSheetByName('Dividend events') || ss.getSheetByName('Dividends');

  if (!inputSheet || !dataSheet) {
    SpreadsheetApp.getUi().alert("Error: Ensure tabs 'Input - Output' and 'Historical Data and Trades' exist.");
    return;
  }

  const tickerRaw = String(inputSheet.getRange('A2').getValue()).trim();
  const totalCapital = Number(inputSheet.getRange('B2').getValue()) || 40000;
  const numParts = Number(inputSheet.getRange('C2').getValue()) || 4;
  const startDate = parseDate(inputSheet.getRange('D2').getValue());
  const endDate = parseDate(inputSheet.getRange('E2').getValue());

  let targetPct = inputSheet.getRange('F2').getValue();
  targetPct = (typeof targetPct === 'number') ? (targetPct > 1 ? targetPct / 100 : targetPct) : 0.05;

  let bullishMinReturnPct = inputSheet.getRange('G2').getValue();
  bullishMinReturnPct = (typeof bullishMinReturnPct === 'number') ? (bullishMinReturnPct > 1 ? bullishMinReturnPct : bullishMinReturnPct * 100) : 15.0;

  ss.toast("Running strategy simulation...", "Darvas Backtester", 10);

  const cleanSym = tickerRaw.replace(/^(NSE:|BSE:)/i, '').trim();
  const yfTicker = cleanSym.includes('.') ? cleanSym : `${cleanSym}.NS`;

  let dailyBars = [];
  let dividendMap = {};

  if (useYahooFinance) {
    const fetched = fetchYahooFinanceDailyAndDividends(yfTicker, startDate, endDate);
    dailyBars = fetched.bars;
    dividendMap = fetched.dividends;
  } else {
    const lastRow = dataSheet.getLastRow();
    if (lastRow < 3) {
      SpreadsheetApp.getUi().alert("No price data found in 'Historical Data and Trades' (Row 3 onwards).");
      return;
    }
    const rawData = dataSheet.getRange(3, 2, lastRow - 2, 5).getValues();
    const endStr = Utilities.formatDate(endDate, "Asia/Kolkata", "yyyy-MM-dd");
    for (let i = 0; i < rawData.length; i++) {
      const d = parseDate(rawData[i][0]);
      if (d) {
        const dStr = Utilities.formatDate(d, "Asia/Kolkata", "yyyy-MM-dd");
        if (dStr <= endStr) {
          const o = Number(rawData[i][1]);
          const h = Number(rawData[i][2]);
          const l = Number(rawData[i][3]);
          const c = Number(rawData[i][4]);
          if (!isNaN(c) && c > 0) {
            dailyBars.push({ date: d, open: o, high: h, low: l, close: c });
          }
        }
      }
    }
    dividendMap = fetchYahooFinanceDividendsOnly(yfTicker, startDate, endDate);
  }

  if (dailyBars.length < 20) {
    SpreadsheetApp.getUi().alert("Insufficient daily price data to calculate strategy.");
    return;
  }

  const d = runSimulationEngineCore(
    dailyBars, dividendMap, cleanSym, totalCapital, numParts,
    startDate, endDate, targetPct, bullishMinReturnPct
  );

  // Write Summary to 'Input - Output'
  inputSheet.getRange('A6:F6').setValues([[
    d.totalPortfolioReturnAmt, d.totalRealizedProfit, d.tradeRealizedProfit,
    d.idleInterestTotal, d.dividendTotal, d.unrealizedOpenPnl
  ]]);

  inputSheet.getRange('A9:F9').setValues([[
    d.totalPortfolioReturnPct / 100, d.xirrPct / 100, d.maxDrawdownPct / 100,
    d.tradesRatio, d.endingOverallCapital, d.endingTrancheAmount
  ]]);

  // Write Detailed Trades to 'Historical Data and Trades'
  const tradeHeaders = [
    'Trade #', 'Type', 'Slot #', 'Buy Date', 'Buy Price', 'Shares', 'Invested Amt',
    'Target Price', 'Sell Date', 'Sell Price', 'Realized P&L', 'Return %', 'Holding Days', 'Status', 'Dividend'
  ];

  if (!dataSheet.getRange('H2').getValue()) {
    dataSheet.getRange(2, 8, 1, tradeHeaders.length).setValues([tradeHeaders]);
  }

  const maxTradeRow = Math.max(dataSheet.getLastRow(), d.trades.length + 10);
  if (maxTradeRow > 2) {
    dataSheet.getRange(3, 8, maxTradeRow - 2, tradeHeaders.length).clearContent();
  }

  if (d.trades.length > 0) {
    dataSheet.getRange(3, 8, d.trades.length, tradeHeaders.length).setValues(d.trades);
  }

  // Write Monthly Summary
  if (monthlySheet) {
    const monthlyHeaders = [
      'Year-MMM', 'Buys', 'Sells', 'Trade Realized', 'Magic Profit', 'Dividend',
      'Idle Interest', 'Total Realized', 'Max Capital Blocked', 'Idle Unused Cash', 'Monthly Return %'
    ];

    const maxMonthlyRow = Math.max(monthlySheet.getLastRow(), d.monthly.length + 10);
    if (maxMonthlyRow > 1) {
      monthlySheet.getRange(2, 1, maxMonthlyRow - 1, monthlyHeaders.length).clearContent();
    }

    if (!monthlySheet.getRange('A1').getValue()) {
      monthlySheet.getRange(1, 1, 1, monthlyHeaders.length).setValues([monthlyHeaders]);
    }

    if (d.monthly.length > 0) {
      monthlySheet.getRange(2, 1, d.monthly.length, monthlyHeaders.length).setValues(d.monthly);
    }
  }

  // Write Dividend Events
  if (dividendSheet) {
    const numDivCols = 9;
    const maxDivRow = Math.max(dividendSheet.getLastRow(), d.dividends.length + 10);
    if (maxDivRow > 1) {
      dividendSheet.getRange(2, 1, maxDivRow - 1, numDivCols).clearContent();
    }

    if (!dividendSheet.getRange('A1').getValue()) {
      const divHeaders = [
        'Event ID', 'Ex-Date', 'Symbol', 'Trade ID', 'Slot ID', 'Buy Date', 'Shares Held', 'Dividend / Share', 'Total Payout'
      ];
      dividendSheet.getRange(1, 1, 1, numDivCols).setValues([divHeaders]);
    }

    if (d.dividends.length > 0) {
      dividendSheet.getRange(2, 1, d.dividends.length, numDivCols).setValues(d.dividends);
    }
  }

  ss.toast("Backtest completed successfully!", "Success", 5);
}

/**
 * Web App Endpoint: Receives requests from external copied sheets
 */
function doPost(e) {
  try {
    const params = JSON.parse(e.postData.contents);
    const tickerRaw = String(params.ticker || 'INFY').trim();
    const totalCapital = Number(params.totalCapital) || 40000;
    const numParts = Number(params.numParts) || 4;
    const startDate = parseDate(params.startDate);
    const endDate = parseDate(params.endDate);

    let targetPct = params.targetPct;
    targetPct = (typeof targetPct === 'number') ? (targetPct > 1 ? targetPct / 100 : targetPct) : 0.05;

    let bullishMinReturnPct = params.bullishMinReturnPct;
    bullishMinReturnPct = (typeof bullishMinReturnPct === 'number') ? (bullishMinReturnPct > 1 ? bullishMinReturnPct : bullishMinReturnPct * 100) : 15.0;

    const cleanSym = tickerRaw.replace(/^(NSE:|BSE:)/i, '').trim();
    const yfTicker = cleanSym.includes('.') ? cleanSym : `${cleanSym}.NS`;

    const fetched = fetchYahooFinanceDailyAndDividends(yfTicker, startDate, endDate);
    const dailyBars = fetched.bars;
    const dividendMap = fetched.dividends;

    if (!dailyBars || dailyBars.length < 20) {
      return ContentService.createTextOutput(JSON.stringify({
        success: false,
        error: "Insufficient price history for " + cleanSym
      })).setMimeType(ContentService.MimeType.JSON);
    }

    const results = runSimulationEngineCore(
      dailyBars, dividendMap, cleanSym, totalCapital, numParts,
      startDate, endDate, targetPct, bullishMinReturnPct
    );

    return ContentService.createTextOutput(JSON.stringify({
      success: true,
      data: results
    })).setMimeType(ContentService.MimeType.JSON);

  } catch (err) {
    return ContentService.createTextOutput(JSON.stringify({
      success: false,
      error: err.toString()
    })).setMimeType(ContentService.MimeType.JSON);
  }
}

/**
 * Core Strategy Simulation Engine: 100% mathematical parity with Python engine
 */
function runSimulationEngineCore(dailyBars, dividendMap, cleanSym, totalCapital, numParts, startDate, endDate, targetPct, bullishMinReturnPct) {
  dailyBars.sort((a, b) => a.date - b.date);

  const weeklyBars = buildWeeklyBars(dailyBars);
  addWeeklyIndicators(weeklyBars);

  const weeklyLookup = {};
  weeklyBars.forEach(w => {
    weeklyLookup[`${w.isoYear}-${w.isoWeek}`] = w;
  });

  const weekLastDays = {};
  dailyBars.forEach(d => {
    const iso = getIsoYearWeek(d.date);
    d.isoYear = iso.year;
    d.isoWeek = iso.week;
    const key = `${iso.year}-${iso.week}`;
    if (!weekLastDays[key] || d.date > weekLastDays[key]) {
      weekLastDays[key] = d.date;
    }
  });

  let isTracking20w = false;
  weeklyBars.forEach(w => {
    if (w.weekEnd < startDate) {
      if (w.rolling20wLow !== null && w.close < w.rolling20wLow) isTracking20w = true;
      if (w.rolling20wHigh !== null && w.close > w.rolling20wHigh) isTracking20w = false;
    }
  });

  let activeTranches = {};
  let availableSlots = [];
  for (let s = 1; s <= numParts; s++) availableSlots.push(s);

  let allTrades = [];
  let tradeCounter = 0;
  let cumulativeRealizedProfit = 0.0;
  let totalDividendAccum = 0.0;
  let totalIdleInterestAccum = 0.0;
  let prevIdleDate = null;
  let peakPortfolioEquity = totalCapital;
  let portfolioEquitySeries = [];
  let dailySnapshots = [];
  let availableCash = totalCapital;

  const dividendEvents = [];
  let dividendIdSeq = 1;

  for (let idx = 0; idx < dailyBars.length; idx++) {
    const day = dailyBars[idx];
    const dayDate = day.date;
    const dayOpen = day.open;
    const dayHigh = day.high;
    const dayLow = day.low;
    const dayClose = day.close;
    const weekKey = `${day.isoYear}-${day.isoWeek}`;
    const wBar = weeklyLookup[weekKey];

    let dayTradeRealized = 0.0;
    let dayDividend = 0.0;

    // STEP 0: Dividends on Open Tranches (T-2 Rule)
    const dayDateStr = Utilities.formatDate(dayDate, "Asia/Kolkata", "yyyy-MM-dd");
    if (dividendMap && dividendMap[dayDateStr] && Object.keys(activeTranches).length > 0) {
      const divPerShare = Number(dividendMap[dayDateStr]);
      let tMinus2Date = null;
      if (idx >= 2) {
        tMinus2Date = dailyBars[idx - 2].date;
      } else {
        tMinus2Date = new Date(dayDate.getTime() - (2 * 86400000));
      }

      Object.keys(activeTranches).forEach(slotId => {
        const tranche = activeTranches[slotId];
        if (tranche.buyDate <= tMinus2Date) {
          const payout = Math.round(tranche.shares * divPerShare * 100) / 100;
          tranche.dividendTotal += payout;
          totalDividendAccum += payout;
          dayDividend += payout;
          availableCash += payout;

          dividendEvents.push({
            eventId: dividendIdSeq++,
            exDate: dayDate,
            symbol: cleanSym,
            tradeId: tranche.tradeId,
            slotId: slotId,
            buyDate: tranche.buyDate,
            shares: tranche.shares,
            dividendPerShare: divPerShare,
            totalPayout: payout
          });
        }
      });
    }

    // STEP 1: Check Exits
    Object.keys(activeTranches).forEach(slotId => {
      const tranche = activeTranches[slotId];
      const isSubsequentDay = dayDate > tranche.buyDate;
      const isSameDayTarget = (dayDate.getTime() === tranche.buyDate.getTime() && dayHigh >= tranche.targetPrice);

      if (isSubsequentDay || isSameDayTarget) {
        let exited = false;
        let sellPrice = null;

        if (tranche.trancheType === 'BEARISH' && dayHigh >= tranche.targetPrice) {
          sellPrice = tranche.targetPrice;
          exited = true;
        }

        if (exited) {
          tranche.sellDate = dayDate;
          tranche.sellPrice = sellPrice;
          tranche.realizedPnl = Math.round((tranche.sellPrice - tranche.buyPrice) * tranche.shares * 100) / 100;
          tranche.returnPct = Math.round(((tranche.sellPrice - tranche.buyPrice) / tranche.buyPrice) * 10000) / 100;
          tranche.holdingDays = Math.round((tranche.sellDate - tranche.buyDate) / 86400000);
          tranche.status = 'CLOSED';

          cumulativeRealizedProfit += tranche.realizedPnl;
          dayTradeRealized += tranche.realizedPnl;
          availableCash += tranche.investedAmt + tranche.realizedPnl;

          delete activeTranches[slotId];
          availableSlots.push(Number(slotId));
          availableSlots.sort((a, b) => a - b);
        }
      }
    });

    // STEP 2: Pending Buy Order Evaluation
    if (dayDate >= startDate && wBar && wBar.breakoutSignal && availableSlots.length > 0) {
      const isFridayOrLastDay = (weekLastDays[weekKey] && dayDate.getTime() === weekLastDays[weekKey].getTime());
      if (isFridayOrLastDay && dayClose > wBar.prevWeekHigh) {
        // Pending order queued
      }
    }

    if (dayDate >= startDate && availableSlots.length > 0) {
      const prevWeekDate = new Date(dayDate.getTime() - (7 * 86400000));
      const prevIso = getIsoYearWeek(prevWeekDate);
      const prevWBar = weeklyLookup[`${prevIso.year}-${prevIso.week}`];

      if (prevWBar && prevWBar.breakoutSignal) {
        const ceiling = Math.round(prevWBar.referenceClose * 1.005 * 100) / 100;
        if (dayLow <= ceiling) {
          const buyPrice = Math.min(dayOpen, ceiling);
          const currentTrancheCapital = (totalCapital + cumulativeRealizedProfit) / numParts;
          const shares = Math.floor(currentTrancheCapital / buyPrice);

          if (shares > 0) {
            const slotId = availableSlots.shift();
            tradeCounter++;
            const investedAmt = Math.round(shares * buyPrice * 100) / 100;
            const trancheType = isTracking20w ? 'BULLISH' : 'BEARISH';
            const targetPrice = (trancheType === 'BEARISH') ? Math.round(buyPrice * (1 + targetPct) * 100) / 100 : 0.0;

            const newTranche = {
              tradeId: tradeCounter,
              slotId: slotId,
              symbol: cleanSym,
              buyDate: dayDate,
              buyPrice: buyPrice,
              shares: shares,
              investedAmt: investedAmt,
              targetPrice: targetPrice,
              sellDate: null,
              sellPrice: null,
              realizedPnl: null,
              returnPct: null,
              holdingDays: null,
              status: 'OPEN',
              trancheType: trancheType,
              dividendTotal: 0.0,
              requiredReturnPct: (trancheType === 'BULLISH') ? bullishMinReturnPct : null,
              achievedReturnPct: null,
              yearsHeld: null
            };

            activeTranches[slotId] = newTranche;
            allTrades.push(newTranche);
            availableCash -= investedAmt;
          }
        }
      }
    }

    // STEP 3: Weekly Trailing Exits for Bullish Tranches
    const isWeekEnd = (weekLastDays[weekKey] && dayDate.getTime() === weekLastDays[weekKey].getTime());
    if (isWeekEnd && wBar) {
      if (!isTracking20w && wBar.rolling20wLow !== null && dayClose < wBar.rolling20wLow) {
        isTracking20w = true;
      }
      if (isTracking20w && wBar.rolling20wHigh !== null && dayClose > wBar.rolling20wHigh) {
        isTracking20w = false;
      }

      if (isTracking20w && wBar.rolling20wLow !== null && dayClose < wBar.rolling20wLow) {
        Object.keys(activeTranches).forEach(slotId => {
          const tranche = activeTranches[slotId];
          if (tranche.trancheType === 'BULLISH') {
            const holdingDays = Math.round((dayDate - tranche.buyDate) / 86400000);
            const yearsHeld = holdingDays / 365.25;
            const returnPct = ((dayClose - tranche.buyPrice) / tranche.buyPrice) * 100.0;
            const annualReturnPct = yearsHeld > 0 ? (returnPct / yearsHeld) : returnPct;

            if (annualReturnPct >= bullishMinReturnPct) {
              tranche.sellDate = dayDate;
              tranche.sellPrice = dayClose;
              tranche.realizedPnl = Math.round((dayClose - tranche.buyPrice) * tranche.shares * 100) / 100;
              tranche.returnPct = Math.round(returnPct * 100) / 100;
              tranche.holdingDays = holdingDays;
              tranche.yearsHeld = Math.round(yearsHeld * 100) / 100;
              tranche.achievedReturnPct = Math.round(annualReturnPct * 100) / 100;
              tranche.status = 'CLOSED';

              cumulativeRealizedProfit += tranche.realizedPnl;
              dayTradeRealized += tranche.realizedPnl;
              availableCash += tranche.investedAmt + tranche.realizedPnl;

              delete activeTranches[slotId];
              availableSlots.push(Number(slotId));
              availableSlots.sort((a, b) => a - b);
            }
          }
        });
      }
    }

    // STEP 4: Idle Cash Interest (5% p.a.)
    let dailyInterest = 0.0;
    if (dayDate >= startDate) {
      if (prevIdleDate !== null) {
        const daysElapsed = Math.round((dayDate - prevIdleDate) / 86400000);
        if (daysElapsed > 0) {
          const openInvestedCash = Object.values(activeTranches).reduce((acc, t) => acc + t.investedAmt, 0);
          const currentTrancheAmount = (totalCapital + cumulativeRealizedProfit) / numParts;
          const idleCash = Math.max(0.0, (totalCapital + cumulativeRealizedProfit) - openInvestedCash - currentTrancheAmount);
          dailyInterest = idleCash * (0.05 / 365.0) * daysElapsed;
          totalIdleInterestAccum += dailyInterest;
        }
      }
      prevIdleDate = dayDate;
    }

    // Equity Curve Tracking
    const openInvestedNow = Object.values(activeTranches).reduce((acc, t) => acc + t.investedAmt, 0);
    const openMtmVal = Object.values(activeTranches).reduce((acc, t) => acc + (t.shares * dayClose), 0);
    const unrealizedNow = openMtmVal - openInvestedNow;
    const dailyEquity = totalCapital + cumulativeRealizedProfit + totalIdleInterestAccum + totalDividendAccum + unrealizedNow;

    if (dayDate >= startDate) {
      portfolioEquitySeries.push(dailyEquity);
      if (dailyEquity > peakPortfolioEquity) peakPortfolioEquity = dailyEquity;
      const dayDd = ((peakPortfolioEquity - dailyEquity) / peakPortfolioEquity) * 100.0;

      const currentTrancheCap = (totalCapital + cumulativeRealizedProfit) / numParts;
      const idleNow = Math.max(0.0, (totalCapital + cumulativeRealizedProfit) - openInvestedNow - currentTrancheCap);

      dailySnapshots.push({
        date: dayDate,
        tradeRealized: dayTradeRealized,
        magicProfit: 0.0,
        dividend: dayDividend,
        idleInterest: dailyInterest,
        openInvested: openInvestedNow,
        idleCash: idleNow,
        unrealizedPnl: unrealizedNow,
        dailyEquity: dailyEquity,
        drawdownPct: dayDd
      });
    }
  }

  // Final Summary Metrics
  const lastClose = dailyBars[dailyBars.length - 1].close;
  const closedTrades = allTrades.filter(t => t.status === 'CLOSED');
  const openTrades = allTrades.filter(t => t.status === 'OPEN');

  const tradeRealizedProfit = closedTrades.reduce((acc, t) => acc + (t.realizedPnl || 0), 0);
  const idleInterestTotal = Math.round(totalIdleInterestAccum * 100) / 100;
  const dividendTotal = Math.round(totalDividendAccum * 100) / 100;
  const totalRealizedProfit = Math.round((tradeRealizedProfit + idleInterestTotal + dividendTotal) * 100) / 100;

  const openPositionsInvested = openTrades.reduce((acc, t) => acc + t.investedAmt, 0);
  const openPositionsCurrentVal = openTrades.reduce((acc, t) => acc + (t.shares * lastClose), 0);
  const unrealizedOpenPnl = Math.round((openPositionsCurrentVal - openPositionsInvested) * 100) / 100;

  const totalPortfolioReturnAmt = Math.round((totalRealizedProfit + unrealizedOpenPnl) * 100) / 100;
  const totalPortfolioReturnPct = Math.round((totalPortfolioReturnAmt / totalCapital) * 10000) / 100;

  let maxDrawdownPct = 0.0;
  let runningPeak = totalCapital;
  for (let i = 0; i < portfolioEquitySeries.length; i++) {
    const eq = portfolioEquitySeries[i];
    if (eq > runningPeak) runningPeak = eq;
    const dd = ((runningPeak - eq) / runningPeak) * 100.0;
    if (dd > maxDrawdownPct) maxDrawdownPct = dd;
  }
  maxDrawdownPct = Math.round(maxDrawdownPct * 100) / 100;

  const lastTradingDate = dailyBars[dailyBars.length - 1].date;
  const cashFlows = [];
  allTrades.forEach(t => {
    cashFlows.push({ date: t.buyDate, amount: -t.investedAmt });
    if (t.status === 'CLOSED') {
      cashFlows.push({ date: t.sellDate, amount: Math.round(t.shares * t.sellPrice * 100) / 100 });
    } else {
      cashFlows.push({ date: lastTradingDate, amount: Math.round(t.shares * lastClose * 100) / 100 });
    }
  });
  dividendEvents.forEach(ev => {
    cashFlows.push({ date: ev.exDate, amount: ev.totalPayout });
  });
  const xirrPct = calculateXIRR(cashFlows);

  const endingOverallCapital = Math.round((totalCapital + totalRealizedProfit) * 100) / 100;
  const endingTrancheAmount = Math.round((endingOverallCapital / numParts) * 100) / 100;

  const tradeRows = allTrades.map(t => [
    t.tradeId,
    t.trancheType,
    `Slot ${t.slotId}`,
    formatDateStr(t.buyDate),
    t.buyPrice,
    t.shares,
    t.investedAmt,
    t.targetPrice > 0 ? t.targetPrice : '20W Low Exit',
    t.sellDate ? formatDateStr(t.sellDate) : '-',
    t.sellPrice ? t.sellPrice : '-',
    t.realizedPnl !== null ? t.realizedPnl : 0,
    t.returnPct !== null ? t.returnPct / 100 : 0,
    t.holdingDays !== null ? t.holdingDays : '-',
    t.status,
    t.dividendTotal
  ]);

  const monthlyRecords = generateMonthlySummaries(dailySnapshots, totalCapital, allTrades);
  let monthlyRows = [];
  if (monthlyRecords.length > 0) {
    let sumBuys = 0, sumSells = 0, sumTrade = 0, sumMagic = 0, sumDiv = 0, sumIdle = 0, sumRealized = 0;
    let peakBlocked = 0;

    monthlyRows = monthlyRecords.map(m => {
      sumBuys += m.numBuys;
      sumSells += m.numSells;
      sumTrade += m.tradeRealizedProfit;
      sumMagic += m.magicProfit;
      sumDiv += m.dividendIncome;
      sumIdle += m.idleInterest;
      sumRealized += m.totalRealizedProfit;
      if (m.maxCapitalBlocked > peakBlocked) peakBlocked = m.maxCapitalBlocked;

      return [
        m.yearMmm,
        m.numBuys,
        m.numSells,
        m.tradeRealizedProfit,
        m.magicProfit,
        m.dividendIncome,
        m.idleInterest,
        m.totalRealizedProfit,
        m.maxCapitalBlocked,
        m.idleUnusedCash,
        m.monthlyReturnPct
      ];
    });

    const overallReturn = peakBlocked > 0 ? (sumRealized / peakBlocked) : 0.0;
    const latestIdle = monthlyRecords[monthlyRecords.length - 1].idleUnusedCash;
    monthlyRows.push([
      'Total / Peak',
      sumBuys,
      sumSells,
      Math.round(sumTrade * 100) / 100,
      Math.round(sumMagic * 100) / 100,
      Math.round(sumDiv * 100) / 100,
      Math.round(sumIdle * 100) / 100,
      Math.round(sumRealized * 100) / 100,
      Math.round(peakBlocked * 100) / 100,
      latestIdle,
      overallReturn
    ]);
  }

  const divRows = dividendEvents.map(ev => [
    ev.eventId,
    formatDateStr(ev.exDate),
    ev.symbol,
    `Trade #${ev.tradeId}`,
    `Slot ${ev.slotId}`,
    formatDateStr(ev.buyDate),
    ev.shares,
    ev.dividendPerShare,
    ev.totalPayout
  ]);

  return {
    totalPortfolioReturnAmt: totalPortfolioReturnAmt,
    totalRealizedProfit: totalRealizedProfit,
    tradeRealizedProfit: tradeRealizedProfit,
    idleInterestTotal: idleInterestTotal,
    dividendTotal: dividendTotal,
    unrealizedOpenPnl: unrealizedOpenPnl,
    totalPortfolioReturnPct: totalPortfolioReturnPct,
    xirrPct: xirrPct,
    maxDrawdownPct: maxDrawdownPct,
    tradesRatio: `${closedTrades.length} / ${allTrades.length}`,
    endingOverallCapital: endingOverallCapital,
    endingTrancheAmount: endingTrancheAmount,
    trades: tradeRows,
    monthly: monthlyRows,
    dividends: divRows
  };
}

// ==========================================
// MONTHLY SUMMARY GENERATOR
// ==========================================

function generateMonthlySummaries(dailySnapshots, totalCapital, allTrades) {
  if (!dailySnapshots || dailySnapshots.length === 0) return [];

  const monthMap = {};
  const monthKeys = [];
  const monthNames = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  dailySnapshots.forEach(s => {
    const yr = s.date.getFullYear();
    const mo = s.date.getMonth();
    const key = `${yr}-${String(mo + 1).padStart(2, '0')}`;
    if (!monthMap[key]) {
      monthMap[key] = {
        yearMmm: `${yr}-${monthNames[mo]}`,
        snaps: []
      };
      monthKeys.push(key);
    }
    monthMap[key].snaps.push(s);
  });

  const buysMap = {};
  const sellsMap = {};
  allTrades.forEach(t => {
    if (t.buyDate) {
      const yr = t.buyDate.getFullYear();
      const mo = t.buyDate.getMonth();
      const bKey = `${yr}-${String(mo + 1).padStart(2, '0')}`;
      buysMap[bKey] = (buysMap[bKey] || 0) + 1;
    }
    if (t.sellDate && t.status === 'CLOSED') {
      const yr = t.sellDate.getFullYear();
      const mo = t.sellDate.getMonth();
      const sKey = `${yr}-${String(mo + 1).padStart(2, '0')}`;
      sellsMap[sKey] = (sellsMap[sKey] || 0) + 1;
    }
  });

  const records = [];
  monthKeys.forEach(key => {
    const group = monthMap[key];
    const snaps = group.snaps;
    const tRealized = snaps.reduce((acc, s) => acc + (s.tradeRealized || 0), 0);
    const mProfit = 0.0;
    const divInc = snaps.reduce((acc, s) => acc + (s.dividend || 0), 0);
    const idleInt = snaps.reduce((acc, s) => acc + (s.idleInterest || 0), 0);
    const totRealized = Math.round((tRealized + mProfit + divInc + idleInt) * 100) / 100;

    const maxBlocked = Math.round(Math.max(...snaps.map(s => s.openInvested || 0)) * 100) / 100;
    const idleUnused = Math.round((snaps[snaps.length - 1].idleCash || 0) * 100) / 100;
    const monthlyReturnPct = maxBlocked > 0 ? (totRealized / maxBlocked) : 0.0;

    records.push({
      yearMmm: group.yearMmm,
      numBuys: buysMap[key] || 0,
      numSells: sellsMap[key] || 0,
      tradeRealizedProfit: Math.round(tRealized * 100) / 100,
      magicProfit: 0.0,
      dividendIncome: Math.round(divInc * 100) / 100,
      idleInterest: Math.round(idleInt * 100) / 100,
      totalRealizedProfit: totRealized,
      maxCapitalBlocked: maxBlocked,
      idleUnusedCash: idleUnused,
      monthlyReturnPct: monthlyReturnPct
    });
  });

  return records;
}

// ==========================================
// HELPER FUNCTIONS & INDICATORS
// ==========================================

function getIsoYearWeek(date) {
  const d = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
  const dayNum = d.getUTCDay() || 7;
  d.setUTCDate(d.getUTCDate() + 4 - dayNum);
  const yearStart = new Date(Date.UTC(d.getUTCFullYear(), 0, 1));
  const weekNo = Math.ceil((((d - yearStart) / 86400000) + 1) / 7);
  return { year: d.getUTCFullYear(), week: weekNo };
}

function buildWeeklyBars(dailyBars) {
  const weeklyMap = {};
  dailyBars.forEach(d => {
    const iso = getIsoYearWeek(d.date);
    const key = `${iso.year}-${iso.week}`;
    if (!weeklyMap[key]) {
      weeklyMap[key] = {
        isoYear: iso.year,
        isoWeek: iso.week,
        weekStart: d.date,
        weekEnd: d.date,
        open: d.open,
        high: d.high,
        low: d.low,
        close: d.close,
        tradingDays: 1
      };
    } else {
      const w = weeklyMap[key];
      if (d.date < w.weekStart) {
        w.weekStart = d.date;
        w.open = d.open;
      }
      if (d.date > w.weekEnd) {
        w.weekEnd = d.date;
        w.close = d.close;
      }
      if (d.high > w.high) w.high = d.high;
      if (d.low < w.low) w.low = d.low;
      w.tradingDays++;
    }
  });

  return Object.values(weeklyMap).sort((a, b) => a.weekStart - b.weekStart);
}

function addWeeklyIndicators(weeklyBars) {
  for (let i = 0; i < weeklyBars.length; i++) {
    const w = weeklyBars[i];
    w.prevWeekHigh = (i > 0) ? weeklyBars[i - 1].high : null;
    w.prevWeekLow = (i > 0) ? weeklyBars[i - 1].low : null;
    w.breakoutSignal = (w.prevWeekHigh !== null && w.close > w.prevWeekHigh);
    w.referenceClose = w.close;
    w.entryCeiling = Math.round(w.close * 1.005 * 100) / 100;

    if (i >= 20) {
      let minLow = Infinity;
      let maxHigh = -Infinity;
      for (let j = i - 20; j < i; j++) {
        if (weeklyBars[j].low < minLow) minLow = weeklyBars[j].low;
        if (weeklyBars[j].high > maxHigh) maxHigh = weeklyBars[j].high;
      }
      w.rolling20wLow = minLow;
      w.rolling20wHigh = maxHigh;
    } else {
      w.rolling20wLow = null;
      w.rolling20wHigh = null;
    }
  }
}

function parseDate(v) {
  if (!v) return null;
  if (v instanceof Date) return v;
  const s = String(v).trim();

  const dmyMatch = s.match(/^(\d{1,2})[-/ ]([A-Za-z]{3})[-/ ](\d{2,4})$/);
  if (dmyMatch) {
    const day = parseInt(dmyMatch[1], 10);
    const monStr = dmyMatch[2].toLowerCase();
    let year = parseInt(dmyMatch[3], 10);
    if (year < 100) year += 2000;
    const months = { jan: 0, feb: 1, mar: 2, apr: 3, may: 4, jun: 5, jul: 6, aug: 7, sep: 8, oct: 9, nov: 10, dec: 11 };
    if (months[monStr] !== undefined) {
      return new Date(year, months[monStr], day, 0, 0, 0);
    }
  }

  const dmyNumMatch = s.match(/^(\d{1,2})[-/ ](\d{1,2})[-/ ](\d{2,4})$/);
  if (dmyNumMatch) {
    const day = parseInt(dmyNumMatch[1], 10);
    const month = parseInt(dmyNumMatch[2], 10) - 1;
    let year = parseInt(dmyNumMatch[3], 10);
    if (year < 100) year += 2000;
    return new Date(year, month, day, 0, 0, 0);
  }

  const ymdMatch = s.match(/^(\d{4})[-/ ](\d{1,2})[-/ ](\d{1,2})$/);
  if (ymdMatch) {
    return new Date(parseInt(ymdMatch[1], 10), parseInt(ymdMatch[2], 10) - 1, parseInt(ymdMatch[3], 10), 0, 0, 0);
  }

  const d = new Date(s);
  return isNaN(d.getTime()) ? null : d;
}

function formatDateStr(d) {
  if (!d) return '-';
  return Utilities.formatDate(d, "GMT", "dd-MMM-yy");
}

function calculateXIRR(cashFlows) {
  if (!cashFlows || cashFlows.length < 2) return 0.0;
  const hasPos = cashFlows.some(c => c.amount > 0);
  const hasNeg = cashFlows.some(c => c.amount < 0);
  if (!hasPos || !hasNeg) return 0.0;

  const d0 = cashFlows[0].date.getTime();
  let r = 0.1;
  for (let iter = 0; iter < 100; iter++) {
    let fVal = 0.0;
    let fPrime = 0.0;
    for (let i = 0; i < cashFlows.length; i++) {
      const yrs = (cashFlows[i].date.getTime() - d0) / (365.25 * 86400000);
      const denom = Math.pow(1.0 + r, yrs);
      fVal += cashFlows[i].amount / denom;
      fPrime -= (yrs * cashFlows[i].amount) / (denom * (1.0 + r));
    }
    if (Math.abs(fPrime) < 1e-12) break;
    const rNew = r - fVal / fPrime;
    if (Math.abs(rNew - r) < 1e-6) return Math.round(rNew * 10000) / 100;
    r = rNew;
    if (r <= -0.99) r = -0.9;
  }
  return Math.round(r * 10000) / 100;
}

function fetchYahooFinanceDailyAndDividends(yfTicker, startDate, endDate) {
  const startSec = Math.floor((startDate.getTime() - (365 * 86400000)) / 1000);
  const endSec = Math.floor(endDate.getTime() / 1000) + 86400;
  const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(yfTicker)}?period1=${startSec}&period2=${endSec}&interval=1d&events=div`;

  const response = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
  const json = JSON.parse(response.getContentText());
  const result = json.chart.result[0];

  const timestamps = result.timestamp || [];
  const quote = result.indicators.quote[0];
  const opens = quote.open || [];
  const highs = quote.high || [];
  const lows = quote.low || [];
  const closes = quote.close || [];

  const endStr = Utilities.formatDate(endDate, "Asia/Kolkata", "yyyy-MM-dd");

  const bars = [];
  for (let i = 0; i < timestamps.length; i++) {
    if (closes[i] !== null && opens[i] !== null) {
      const bDate = new Date(timestamps[i] * 1000);
      const bStr = Utilities.formatDate(bDate, "Asia/Kolkata", "yyyy-MM-dd");
      if (bStr <= endStr) {
        bars.push({
          date: bDate,
          open: Number(opens[i].toFixed(2)),
          high: Number(highs[i].toFixed(2)),
          low: Number(lows[i].toFixed(2)),
          close: Number(closes[i].toFixed(2))
        });
      }
    }
  }

  const dividends = {};
  if (result.events && result.events.dividends) {
    Object.values(result.events.dividends).forEach(div => {
      const dt = new Date(div.date * 1000);
      const dtStr = Utilities.formatDate(dt, "Asia/Kolkata", "yyyy-MM-dd");
      if (dtStr <= endStr) {
        dividends[dtStr] = div.amount;
      }
    });
  }

  return { bars: bars, dividends: dividends };
}

function fetchYahooFinanceDividendsOnly(yfTicker, startDate, endDate) {
  try {
    const startSec = Math.floor((startDate.getTime() - (365 * 86400000)) / 1000);
    const endSec = Math.floor(endDate.getTime() / 1000) + 86400;
    const url = `https://query1.finance.yahoo.com/v8/finance/chart/${encodeURIComponent(yfTicker)}?period1=${startSec}&period2=${endSec}&interval=1d&events=div`;

    const response = UrlFetchApp.fetch(url, { muteHttpExceptions: true });
    const json = JSON.parse(response.getContentText());
    const result = json.chart && json.chart.result && json.chart.result[0];

    const endStr = Utilities.formatDate(endDate, "Asia/Kolkata", "yyyy-MM-dd");
    const dividends = {};
    if (result && result.events && result.events.dividends) {
      Object.values(result.events.dividends).forEach(div => {
        const dt = new Date(div.date * 1000);
        const dtStr = Utilities.formatDate(dt, "Asia/Kolkata", "yyyy-MM-dd");
        if (dtStr <= endStr) {
          dividends[dtStr] = div.amount;
        }
      });
    }
    return dividends;
  } catch (err) {
    Logger.log("Could not fetch dividends: " + err);
    return {};
  }
}

// ==========================================
// EXECUTIVE KPI CARD THEMES (ROWS 5-9)
// ==========================================

function applyThemeNavy() { applyKpiTheme('navy'); }
function applyThemeIndigo() { applyKpiTheme('indigo'); }
function applyThemeEmerald() { applyKpiTheme('emerald'); }
function applyThemeCleanGray() { applyKpiTheme('gray'); }

function applyKpiTheme(themeKey) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('Input - Output');
  if (!sheet) return;

  const themes = {
    navy: { name: "Institutional Navy & Ice Blue", hdrBg: "#0f2744", hdrColor: "#ffffff", valBg: "#eef5fc", valColor: "#0a192f", borderColor: "#c6d9ed" },
    indigo: { name: "Royal Indigo & Lilac", hdrBg: "#2d1b69", hdrColor: "#ffffff", valBg: "#f3f0fa", valColor: "#1d0f47", borderColor: "#cfc5eb" },
    emerald: { name: "Bloomberg Emerald & Mint", hdrBg: "#0d3b2e", hdrColor: "#ffffff", valBg: "#edf7f2", valColor: "#06241b", borderColor: "#bde3d2" },
    gray: { name: "Clean Minimal Slate Gray", hdrBg: "#24292e", hdrColor: "#ffffff", valBg: "#f6f8fa", valColor: "#1f2328", borderColor: "#d0d7de" }
  };

  const t = themes[themeKey] || themes.navy;

  sheet.getRange('A5:F5').setBackground(t.hdrBg).setFontColor(t.hdrColor).setFontWeight('bold').setFontSize(10).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('A6:F6').setBackground(t.valBg).setFontColor(t.valColor).setFontWeight('bold').setFontSize(12).setHorizontalAlignment('right').setVerticalAlignment('middle').setNumberFormat('₹#,##0');
  sheet.getRange('A8:F8').setBackground(t.hdrBg).setFontColor(t.hdrColor).setFontWeight('bold').setFontSize(10).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('A9:C9').setBackground(t.valBg).setFontColor(t.valColor).setFontWeight('bold').setFontSize(12).setHorizontalAlignment('right').setVerticalAlignment('middle').setNumberFormat('0.00%');
  sheet.getRange('D9').setBackground(t.valBg).setFontColor(t.valColor).setFontWeight('bold').setFontSize(11).setHorizontalAlignment('center').setVerticalAlignment('middle');
  sheet.getRange('E9:F9').setBackground(t.valBg).setFontColor(t.valColor).setFontWeight('bold').setFontSize(11).setHorizontalAlignment('right').setVerticalAlignment('middle').setNumberFormat('₹#,##0');

  sheet.getRange('A5:F6').setBorder(true, true, true, true, true, true, t.borderColor, SpreadsheetApp.BorderStyle.SOLID);
  sheet.getRange('A8:F9').setBorder(true, true, true, true, true, true, t.borderColor, SpreadsheetApp.BorderStyle.SOLID);

  sheet.setRowHeight(5, 28);
  sheet.setRowHeight(6, 34);
  sheet.setRowHeight(7, 12);
  sheet.setRowHeight(8, 28);
  sheet.setRowHeight(9, 34);

  ss.toast(`Theme '${t.name}' applied to Rows 5-9!`, '🎨 Styling Applied', 4);
}
