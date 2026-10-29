/**@OnlyCurrentDoc */

/**
 * ============================================================================
 * DARVAS BEARISH + BULLISH COMBO SYSTEMATIC BACKTEST ENGINE FOR GOOGLE SHEETS
 * ============================================================================
 * 
 * File Name: Back testing App script.js
 * 
 * Target Tabs:
 * 1. 'Input - Output'
 *    - Inputs: Row 2 (A2:G2)
 *    - Outputs:
 *      Row 6: Total Portfolio Return, Total Realized Profit, Trade Realized Profit,
 *             Idle Interest, Dividend Income, Unrealized Open P&L
 *      Row 9: Total Portfolio Return %, XIRR %, Max Drawdown %,
 *             Trades (Closed / Total), Ending Overall Capital, Ending Tranche Buy Amount
 * 
 * 2. 'Historical Data and Trades'
 *    - Input Columns: Col B: Date, Col C: Open, Col D: High, Col E: Low, Col F: Close (Row 3 onwards)
 *    - Output Columns: Col H onwards (Row 2 headers, Row 3 onwards trade journal)
 * 
 * 3. 'Monthly Summary'
 *    - Output Columns:
 *      Year-MMM, Buys, Sells, Trade Realized, Magic Profit, Dividend,
 *      Idle Interest, Total Realized, Max Capital Blocked, Idle Unused Cash, Monthly Return %
 *      Includes "Total / Peak" footer row matching web version.
 * 
 * 4. 'Dividend Events'
 *    - Output Columns:
 *      Event ID, Ex-Date, Symbol, Trade ID, Slot ID, Buy Date, Shares Held, Dividend / Share, Total Payout
 * 
 * NOTE: All programmatic formatting (colors, fonts, borders, number formats) has been removed.
 *       The script writes raw values so your custom sheet formatting remains 100% intact.
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

/**
 * Runner 1: Executes backtest using the existing Google Finance data in 'Historical Data and Trades'
 */
function runBacktestFromSheet() {
  executeBacktestEngine(false);
}

/**
 * Runner 2: Fetches clean OHLCV + Dividends with warmup directly from Yahoo Finance
 */
function runBacktestFromYahooFinance() {
  executeBacktestEngine(true);
}

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

  // 1. Read Inputs from 'Input - Output' Row 2 (A2:G2)
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

  // Clean symbol for Yahoo queries
  const cleanSym = tickerRaw.replace(/^(NSE:|BSE:)/i, '').trim();
  const yfTicker = cleanSym.includes('.') ? cleanSym : `${cleanSym}.NS`;

  // 2. Load Daily OHLCV Data
  let dailyBars = [];
  let dividendMap = {};

  if (useYahooFinance) {
    const fetched = fetchYahooFinanceDailyAndDividends(yfTicker, startDate, endDate);
    dailyBars = fetched.bars;
    dividendMap = fetched.dividends;
  } else {
    // Read from 'Historical Data and Trades' (Col B: Date, C: Open, D: High, E: Low, F: Close)
    const lastRow = dataSheet.getLastRow();
    if (lastRow < 3) {
      SpreadsheetApp.getUi().alert("No price data found in 'Historical Data and Trades' (Row 3 onwards).");
      return;
    }
    const rawData = dataSheet.getRange(3, 2, lastRow - 2, 5).getValues();
    for (let i = 0; i < rawData.length; i++) {
      const d = parseDate(rawData[i][0]);
      const o = Number(rawData[i][1]);
      const h = Number(rawData[i][2]);
      const l = Number(rawData[i][3]);
      const c = Number(rawData[i][4]);
      if (d && !isNaN(c) && c > 0) {
        dailyBars.push({ date: d, open: o, high: h, low: l, close: c });
      }
    }
    // Also fetch corporate dividends from Yahoo Finance so Dividend Events can be tracked
    dividendMap = fetchYahooFinanceDividendsOnly(yfTicker, startDate, endDate);
  }

  if (dailyBars.length < 20) {
    SpreadsheetApp.getUi().alert("Insufficient daily price data to calculate strategy.");
    return;
  }

  // Sort daily bars ascending by date
  dailyBars.sort((a, b) => a.date - b.date);

  // 3. Build Weekly Bars and 20-Week Rolling Indicators
  const weeklyBars = buildWeeklyBars(dailyBars);
  addWeeklyIndicators(weeklyBars);

  // Map weekly indicators back to lookup dictionary: Key = "YYYY-WW"
  const weeklyLookup = {};
  weeklyBars.forEach(w => {
    weeklyLookup[`${w.isoYear}-${w.isoWeek}`] = w;
  });

  // Identify last trading day of each week
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

  // 4. Initialize State Machine
  let isTracking20w = false;
  // Cold-start tracking state before start date
  weeklyBars.forEach(w => {
    if (w.weekEnd < startDate) {
      if (w.rolling20wLow !== null && w.close < w.rolling20wLow) isTracking20w = true;
      if (w.rolling20wHigh !== null && w.close > w.rolling20wHigh) isTracking20w = false;
    }
  });

  let activeTranches = {}; // slotId -> Tranche object
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

  // 5. Day-by-Day Simulation Loop
  for (let idx = 0; idx < dailyBars.length; idx++) {
    const day = dailyBars[idx];
    const dayDate = day.date;
    const dayOpen = day.open;
    const dayHigh = day.high;
    const dayLow = day.low;
    const dayClose = day.close;
    const weekKey = `${day.isoYear}-${day.isoWeek}`;

    let dayTradeRealized = 0.0;
    let dayDividend = 0.0;

    // A. Check Dividends (T-2 rule: bought at least 2 days prior to ex-date)
    const dateKey = Utilities.formatDate(dayDate, "GMT", "yyyy-MM-dd");
    if (dividendMap[dateKey] && Object.keys(activeTranches).length > 0) {
      const divPerShare = dividendMap[dateKey];
      Object.keys(activeTranches).forEach(slotStr => {
        const slotId = parseInt(slotStr, 10);
        const tr = activeTranches[slotId];
        const daysDiff = (dayDate - tr.buyDate) / (1000 * 3600 * 24);
        if (daysDiff >= 2) {
          const payout = Math.round(tr.shares * divPerShare * 100) / 100;
          tr.dividendTotal += payout;
          totalDividendAccum += payout;
          dayDividend += payout;
          availableCash += payout;

          dividendEvents.push({
            eventId: dividendIdSeq++,
            exDate: dayDate,
            symbol: tickerRaw,
            tradeId: tr.tradeId,
            slotId: tr.slotId,
            buyDate: tr.buyDate,
            shares: tr.shares,
            dividendPerShare: divPerShare,
            totalPayout: payout
          });
        }
      });
    }

    // B. Check Exits on Open Tranches
    Object.keys(activeTranches).forEach(slotStr => {
      const slotId = parseInt(slotStr, 10);
      const tr = activeTranches[slotId];
      let exited = false;
      let sellPrice = 0;

      // Bearish Tranche exit at exact +5% target
      if (tr.trancheType === 'BEARISH' && dayHigh >= tr.targetPrice) {
        sellPrice = tr.targetPrice;
        exited = true;
      }

      if (exited) {
        tr.sellDate = dayDate;
        tr.sellPrice = sellPrice;
        tr.realizedPnl = Math.round((tr.sellPrice - tr.buyPrice) * tr.shares * 100) / 100;
        tr.returnPct = Math.round(((tr.sellPrice - tr.buyPrice) / tr.buyPrice) * 10000) / 100;
        tr.holdingDays = Math.round((tr.sellDate - tr.buyDate) / (1000 * 3600 * 24));
        tr.status = 'CLOSED';

        cumulativeRealizedProfit += tr.realizedPnl;
        dayTradeRealized += tr.realizedPnl;
        availableCash += tr.investedAmt + tr.realizedPnl;

        delete activeTranches[slotId];
        availableSlots.push(slotId);
        availableSlots.sort((a, b) => a - b);
      }
    });

    // C. Weekly Close Actions (Friday / Last trading day of week)
    const weekLastDate = weekLastDays[weekKey];
    if (weekLastDate && dayDate.getTime() === weekLastDate.getTime()) {
      const wRow = weeklyLookup[weekKey];
      if (wRow) {
        const r20wl = wRow.rolling20wLow;
        const r20wh = wRow.rolling20wHigh;

        // 1. Bullish Tranche Exit check
        if (r20wl !== null && dayClose < r20wl) {
          Object.keys(activeTranches).forEach(slotStr => {
            const slotId = parseInt(slotStr, 10);
            const tr = activeTranches[slotId];
            if (tr.trancheType === 'BULLISH') {
              const daysHeld = (dayDate - tr.buyDate) / (1000 * 3600 * 24);
              const yearsHeld = Math.max(daysHeld / 365.25, 0.0);
              const reqReturnPct = bullishMinReturnPct * yearsHeld;
              const achievedPct = ((dayClose - tr.buyPrice) / tr.buyPrice) * 100.0;

              if (achievedPct >= reqReturnPct) {
                tr.sellDate = dayDate;
                tr.sellPrice = dayClose;
                tr.realizedPnl = Math.round((dayClose - tr.buyPrice) * tr.shares * 100) / 100;
                tr.returnPct = Math.round(achievedPct * 100) / 100;
                tr.holdingDays = Math.round(daysHeld);
                tr.status = 'CLOSED';

                cumulativeRealizedProfit += tr.realizedPnl;
                dayTradeRealized += tr.realizedPnl;
                availableCash += tr.investedAmt + tr.realizedPnl;

                delete activeTranches[slotId];
                availableSlots.push(slotId);
                availableSlots.sort((a, b) => a - b);
              }
            }
          });
        }

        // 2. Bearish Radar Activation
        if (!isTracking20w && r20wl !== null && dayClose < r20wl) {
          isTracking20w = true;
        }

        // 3. 20-Week High Breakout -> Deactivates Bearish Radar & Enters Bullish Tranche
        if (r20wh !== null && dayClose > r20wh) {
          isTracking20w = false;

          // Enter dedicated Bullish Tranche if none open
          const hasOpenBullish = Object.values(activeTranches).some(t => t.trancheType === 'BULLISH');
          if (!hasOpenBullish && availableSlots.length > 0 && dayDate >= startDate) {
            const slotId = availableSlots.shift();
            const buyPrice = dayClose;
            const currentCap = totalCapital + cumulativeRealizedProfit + totalDividendAccum;
            const dynTrancheCap = currentCap / numParts;
            const shares = Math.floor(dynTrancheCap / buyPrice);

            if (shares > 0) {
              tradeCounter++;
              const invested = Math.round(shares * buyPrice * 100) / 100;
              const newTranche = {
                tradeId: tradeCounter,
                slotId: slotId,
                trancheType: 'BULLISH',
                buyDate: dayDate,
                buyPrice: buyPrice,
                shares: shares,
                investedAmt: invested,
                targetPrice: 0, // Exits on 20W low breakdown with min hurdle return
                sellDate: null,
                sellPrice: null,
                realizedPnl: null,
                returnPct: null,
                holdingDays: null,
                status: 'OPEN',
                dividendTotal: 0
              };
              activeTranches[slotId] = newTranche;
              allTrades.push(newTranche);
              availableCash -= invested;
            } else {
              availableSlots.unshift(slotId);
            }
          }
        }
        // 4. Bearish Dip-Buying Tranches (when tracking 20W low)
        else if (isTracking20w) {
          const maxBearish = numParts - 1; // 3 slots for Bearish
          const openBearish = Object.values(activeTranches).filter(t => t.trancheType === 'BEARISH').length;
          const prevWkH = wRow.prevWeekHigh;

          if (prevWkH !== null && dayClose > prevWkH && openBearish < maxBearish && availableSlots.length > 0 && dayDate >= startDate) {
            const slotId = availableSlots.shift();
            const buyPrice = dayClose;
            const currentCap = totalCapital + cumulativeRealizedProfit + totalDividendAccum;
            const dynTrancheCap = currentCap / numParts;
            const shares = Math.floor(dynTrancheCap / buyPrice);

            if (shares > 0) {
              tradeCounter++;
              const invested = Math.round(shares * buyPrice * 100) / 100;
              const target = Math.round(buyPrice * (1.0 + targetPct) * 100) / 100;
              const newTranche = {
                tradeId: tradeCounter,
                slotId: slotId,
                trancheType: 'BEARISH',
                buyDate: dayDate,
                buyPrice: buyPrice,
                shares: shares,
                investedAmt: invested,
                targetPrice: target,
                sellDate: null,
                sellPrice: null,
                realizedPnl: null,
                returnPct: null,
                holdingDays: null,
                status: 'OPEN',
                dividendTotal: 0
              };
              activeTranches[slotId] = newTranche;
              allTrades.push(newTranche);
              availableCash -= invested;
            } else {
              availableSlots.unshift(slotId);
            }
          }
        }
      }
    }

    // D. Daily Idle Capital Interest & Equity Tracking
    if (dayDate >= startDate) {
      const daysElapsed = prevIdleDate ? Math.max((dayDate - prevIdleDate) / (1000 * 3600 * 24), 1) : 1;
      const openInvested = Object.values(activeTranches).reduce((acc, t) => acc + t.investedAmt, 0);
      const currentOverallCap = totalCapital + cumulativeRealizedProfit + totalDividendAccum;
      const dynTrancheCap = currentOverallCap / numParts;
      const idleCash = Math.max(0, currentOverallCap - openInvested);
      const eligibleIdle = Math.max(0, idleCash - dynTrancheCap); // 1 tranche is untouched liquid buffer

      const dailyInterest = eligibleIdle * (0.05 / 365.0) * daysElapsed;
      totalIdleInterestAccum += dailyInterest;
      prevIdleDate = dayDate;

      const currentOpenVal = Object.values(activeTranches).reduce((acc, t) => acc + (t.shares * dayClose), 0);
      const dailyEquity = availableCash + currentOpenVal + totalIdleInterestAccum;
      portfolioEquitySeries.push(dailyEquity);
      if (dailyEquity > peakPortfolioEquity) peakPortfolioEquity = dailyEquity;

      const dayDrawdown = peakPortfolioEquity > 0 ? ((peakPortfolioEquity - dailyEquity) / peakPortfolioEquity) * 100.0 : 0.0;

      dailySnapshots.push({
        date: dayDate,
        tradeRealized: dayTradeRealized,
        dividend: dayDividend,
        idleInterest: dailyInterest,
        openInvested: openInvested,
        idleCash: idleCash,
        dailyEquity: dailyEquity,
        drawdownPct: dayDrawdown
      });
    }
  }

  // 6. Calculate Final Summary Metrics
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

  // Max Drawdown %
  let maxDrawdownPct = 0.0;
  let runningPeak = totalCapital;
  for (let i = 0; i < portfolioEquitySeries.length; i++) {
    const eq = portfolioEquitySeries[i];
    if (eq > runningPeak) runningPeak = eq;
    const dd = ((runningPeak - eq) / runningPeak) * 100.0;
    if (dd > maxDrawdownPct) maxDrawdownPct = dd;
  }
  maxDrawdownPct = Math.round(maxDrawdownPct * 100) / 100;

  // Deployed Capital XIRR %
  const cashFlows = [];
  allTrades.forEach(t => {
    cashFlows.push({ date: t.buyDate, amount: -t.investedAmt });
    if (t.status === 'CLOSED') {
      cashFlows.push({ date: t.sellDate, amount: Math.round(t.shares * t.sellPrice * 100) / 100 });
    } else {
      cashFlows.push({ date: endDate, amount: Math.round(t.shares * lastClose * 100) / 100 });
    }
  });
  const xirrPct = calculateXIRR(cashFlows);

  const endingOverallCapital = Math.round((totalCapital + totalRealizedProfit) * 100) / 100;
  const endingTrancheAmount = Math.round((endingOverallCapital / numParts) * 100) / 100;

  // 7. Write Summary to 'Input - Output' Tab (VALUES ONLY - NO FORMATTING APPLIED)
  // Row 6: Total Portfolio Return, Total Realized Profit, Trade Realized Profit, Idle Interest, Dividend Income, Unrealized Open P&L
  inputSheet.getRange('A6:F6').setValues([[
    totalPortfolioReturnAmt,
    totalRealizedProfit,
    tradeRealizedProfit,
    idleInterestTotal,
    dividendTotal,
    unrealizedOpenPnl
  ]]);

  // Row 9: Total Portfolio Return %, XIRR %, Max Drawdown %, Trades (Closed / Total), Ending Overall Capital, Ending Tranche Buy Amount
  inputSheet.getRange('A9:F9').setValues([[
    totalPortfolioReturnPct / 100,
    xirrPct / 100,
    maxDrawdownPct / 100,
    `${closedTrades.length} / ${allTrades.length}`,
    endingOverallCapital,
    endingTrancheAmount
  ]]);

  // 8. Write Detailed Trades to 'Historical Data and Trades' Tab (Cols H onwards)
  const tradeHeaders = [
    'Trade #', 'Type', 'Slot #', 'Buy Date', 'Buy Price', 'Shares', 'Invested Amt',
    'Target Price', 'Sell Date', 'Sell Price', 'Realized P&L', 'Return %', 'Holding Days', 'Status', 'Dividend'
  ];

  // Set headers in Row 2, Col H (Column 8) only if not already present
  if (!dataSheet.getRange('H2').getValue()) {
    dataSheet.getRange(2, 8, 1, tradeHeaders.length).setValues([tradeHeaders]);
  }

  // Clear old trades if any (content only in columns H to V - preserves formatting/borders)
  const maxTradeRow = Math.max(dataSheet.getLastRow(), allTrades.length + 10);
  if (maxTradeRow > 2) {
    dataSheet.getRange(3, 8, maxTradeRow - 2, tradeHeaders.length).clearContent();
  }

  if (allTrades.length > 0) {
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

    dataSheet.getRange(3, 8, tradeRows.length, tradeHeaders.length).setValues(tradeRows);
  }

  // 9. Write Monthly Summary to 'Monthly Summary' Tab (if tab exists)
  if (monthlySheet) {
    const monthlyRecords = generateMonthlySummaries(dailySnapshots, totalCapital, allTrades);
    const monthlyHeaders = [
      'Year-MMM', 'Buys', 'Sells', 'Trade Realized', 'Magic Profit', 'Dividend',
      'Idle Interest', 'Total Realized', 'Max Capital Blocked', 'Idle Unused Cash', 'Monthly Return %'
    ];

    // Clear old data from Row 2 downwards (content only - preserves user styling and headers in Row 1)
    const maxMonthlyRow = Math.max(monthlySheet.getLastRow(), monthlyRecords.length + 10);
    if (maxMonthlyRow > 1) {
      monthlySheet.getRange(2, 1, maxMonthlyRow - 1, monthlyHeaders.length).clearContent();
    }

    // Only populate headers in Row 1 if currently blank
    if (!monthlySheet.getRange('A1').getValue()) {
      monthlySheet.getRange(1, 1, 1, monthlyHeaders.length).setValues([monthlyHeaders]);
    }

    if (monthlyRecords.length > 0) {
      let sumBuys = 0, sumSells = 0, sumTrade = 0, sumMagic = 0, sumDiv = 0, sumIdle = 0, sumRealized = 0;
      let peakBlocked = 0;

      const monthlyRows = monthlyRecords.map(m => {
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
          m.monthlyReturnPct // decimal fraction for native % formatting
        ];
      });

      // Add "Total / Peak" footer row matching web version
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

      monthlySheet.getRange(2, 1, monthlyRows.length, monthlyHeaders.length).setValues(monthlyRows);
    }
  }

  // 10. Write Dividend Events to 'Dividend Events' Tab (if tab exists)
  // Strictly writes to Columns A-I (1 to 9), Row 2 downwards.
  // Row 1 (including headers and custom summary in K1:L1) is completely protected and untouched.
  if (dividendSheet) {
    const numDivCols = 9; // Strictly Columns A through I

    // Clear old data strictly from Row 2 downwards in Columns A to I
    // Never touches Row 1, and never touches Columns J, K, L (Total Dividend in K1-L1 is preserved)
    const maxDivRow = Math.max(dividendSheet.getLastRow(), dividendEvents.length + 10);
    if (maxDivRow > 1) {
      dividendSheet.getRange(2, 1, maxDivRow - 1, numDivCols).clearContent();
    }

    // Only populate headers in Row 1 if A1 is empty
    if (!dividendSheet.getRange('A1').getValue()) {
      const divHeaders = [
        'Event ID', 'Ex-Date', 'Symbol', 'Trade ID', 'Slot ID', 'Buy Date', 'Shares Held', 'Dividend / Share', 'Total Payout'
      ];
      dividendSheet.getRange(1, 1, 1, numDivCols).setValues([divHeaders]);
    }

    if (dividendEvents.length > 0) {
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
      dividendSheet.getRange(2, 1, divRows.length, numDivCols).setValues(divRows);
    }
  }

  ss.toast("Backtest completed successfully!", "Success", 5);
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
        bars: []
      };
    }
    const w = weeklyMap[key];
    w.weekEnd = d.date;
    if (d.high > w.high) w.high = d.high;
    if (d.low < w.low) w.low = d.low;
    w.close = d.close;
    w.bars.push(d);
  });
  return Object.values(weeklyMap).sort((a, b) => a.weekStart - b.weekStart);
}

function addWeeklyIndicators(weeklyBars) {
  for (let i = 0; i < weeklyBars.length; i++) {
    weeklyBars[i].prevWeekHigh = i > 0 ? weeklyBars[i - 1].high : null;
    weeklyBars[i].prevWeekLow = i > 0 ? weeklyBars[i - 1].low : null;

    if (i >= 20) {
      let rHigh = -Infinity;
      let rLow = Infinity;
      for (let k = i - 20; k < i; k++) {
        if (weeklyBars[k].high > rHigh) rHigh = weeklyBars[k].high;
        if (weeklyBars[k].low < rLow) rLow = weeklyBars[k].low;
      }
      weeklyBars[i].rolling20wHigh = rHigh;
      weeklyBars[i].rolling20wLow = rLow;
    } else {
      weeklyBars[i].rolling20wHigh = null;
      weeklyBars[i].rolling20wLow = null;
    }
  }
}

function parseDate(v) {
  if (!v) return null;
  if (v instanceof Date) return v;
  const d = new Date(v);
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
  const startSec = Math.floor((startDate.getTime() - (365 * 86400000)) / 1000); // 1-year warmup
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

  const bars = [];
  for (let i = 0; i < timestamps.length; i++) {
    if (closes[i] !== null && opens[i] !== null) {
      bars.push({
        date: new Date(timestamps[i] * 1000),
        open: Number(opens[i].toFixed(2)),
        high: Number(highs[i].toFixed(2)),
        low: Number(lows[i].toFixed(2)),
        close: Number(closes[i].toFixed(2))
      });
    }
  }

  const dividends = {};
  if (result.events && result.events.dividends) {
    Object.values(result.events.dividends).forEach(div => {
      const dtStr = Utilities.formatDate(new Date(div.date * 1000), "GMT", "yyyy-MM-dd");
      dividends[dtStr] = div.amount;
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

    const dividends = {};
    if (result && result.events && result.events.dividends) {
      Object.values(result.events.dividends).forEach(div => {
        const dtStr = Utilities.formatDate(new Date(div.date * 1000), "GMT", "yyyy-MM-dd");
        dividends[dtStr] = div.amount;
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

function applyThemeNavy() {
  applyKpiTheme('navy');
}

function applyThemeIndigo() {
  applyKpiTheme('indigo');
}

function applyThemeEmerald() {
  applyKpiTheme('emerald');
}

function applyThemeCleanGray() {
  applyKpiTheme('gray');
}

/**
 * Formats Rows 5-9 in 'Input - Output' into a sleek executive financial scorecard.
 * @param {string} themeKey - 'navy', 'indigo', 'emerald', or 'gray'
 */
function applyKpiTheme(themeKey) {
  const ss = SpreadsheetApp.getActiveSpreadsheet();
  const sheet = ss.getSheetByName('Input - Output');
  if (!sheet) {
    SpreadsheetApp.getUi().alert("Sheet 'Input - Output' not found.");
    return;
  }

  const themes = {
    navy: {
      name: 'Institutional Navy & Ice Blue',
      header1Bg: '#1E3A5F',
      header1Color: '#FFFFFF',
      header2Bg: '#334155',
      header2Color: '#FFFFFF',
      heroBg: '#E0F2FE',
      heroColor: '#0369A1',
      valBg: '#F8FAFC',
      valColor: '#0F172A',
      riskBg: '#FEF2F2',
      riskColor: '#B91C1C',
      borderColor: '#CBD5E1'
    },
    indigo: {
      name: 'Royal Indigo & Lilac',
      header1Bg: '#312E81',
      header1Color: '#FFFFFF',
      header2Bg: '#3730A3',
      header2Color: '#FFFFFF',
      heroBg: '#E0E7FF',
      heroColor: '#3730A3',
      valBg: '#F5F3FF',
      valColor: '#1E1B4B',
      riskBg: '#FEE2E2',
      riskColor: '#991B1B',
      borderColor: '#DDD6FE'
    },
    emerald: {
      name: 'Bloomberg Emerald & Mint',
      header1Bg: '#064E3B',
      header1Color: '#FFFFFF',
      header2Bg: '#1E293B',
      header2Color: '#FFFFFF',
      heroBg: '#D1FAE5',
      heroColor: '#065F46',
      valBg: '#F0FDF4',
      valColor: '#064E3B',
      riskBg: '#FEE2E2',
      riskColor: '#991B1B',
      borderColor: '#A7F3D0'
    },
    gray: {
      name: 'Clean Minimal Slate Gray',
      header1Bg: '#475569',
      header1Color: '#FFFFFF',
      header2Bg: '#64748B',
      header2Color: '#FFFFFF',
      heroBg: '#F1F5F9',
      heroColor: '#0F172A',
      valBg: '#FFFFFF',
      valColor: '#1E293B',
      riskBg: '#FFF1F2',
      riskColor: '#BE123C',
      borderColor: '#E2E8F0'
    }
  };

  const t = themes[themeKey] || themes.navy;

  // 1. Row 5: Group 1 Headers (A5:F5)
  const r5 = sheet.getRange('A5:F5');
  r5.setBackground(t.header1Bg)
    .setFontColor(t.header1Color)
    .setFontWeight('bold')
    .setFontSize(9)
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle')
    .setWrap(true);

  // 2. Row 6: Hero A6 (Total Portfolio Return)
  sheet.getRange('A6')
    .setBackground(t.heroBg)
    .setFontColor(t.heroColor)
    .setFontWeight('bold')
    .setFontSize(13)
    .setHorizontalAlignment('right')
    .setVerticalAlignment('middle')
    .setNumberFormat('₹#,##0');

  // Row 6: Other metrics (B6:F6)
  sheet.getRange('B6:F6')
    .setBackground(t.valBg)
    .setFontColor(t.valColor)
    .setFontWeight('bold')
    .setFontSize(11)
    .setHorizontalAlignment('right')
    .setVerticalAlignment('middle')
    .setNumberFormat('₹#,##0');

  // 3. Row 7: Divider spacer row
  sheet.getRange('A7:F7').setBackground(null);

  // 4. Row 8: Group 2 Headers (A8:F8)
  const r8 = sheet.getRange('A8:F8');
  r8.setBackground(t.header2Bg)
    .setFontColor(t.header2Color)
    .setFontWeight('bold')
    .setFontSize(9)
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle')
    .setWrap(true);

  // 5. Row 9: Hero % (A9:B9 - Total Return % & XIRR %)
  sheet.getRange('A9:B9')
    .setBackground(t.heroBg)
    .setFontColor(t.heroColor)
    .setFontWeight('bold')
    .setFontSize(13)
    .setHorizontalAlignment('right')
    .setVerticalAlignment('middle')
    .setNumberFormat('0.00%');

  // Row 9: Max Drawdown % (C9)
  sheet.getRange('C9')
    .setBackground(t.riskBg)
    .setFontColor(t.riskColor)
    .setFontWeight('bold')
    .setFontSize(11)
    .setHorizontalAlignment('right')
    .setVerticalAlignment('middle')
    .setNumberFormat('0.00%');

  // Row 9: Trades Count (D9)
  sheet.getRange('D9')
    .setBackground(t.valBg)
    .setFontColor(t.valColor)
    .setFontWeight('bold')
    .setFontSize(11)
    .setHorizontalAlignment('center')
    .setVerticalAlignment('middle');

  // Row 9: Ending Capital & Tranche Buy Amount (E9:F9)
  sheet.getRange('E9:F9')
    .setBackground(t.valBg)
    .setFontColor(t.valColor)
    .setFontWeight('bold')
    .setFontSize(11)
    .setHorizontalAlignment('right')
    .setVerticalAlignment('middle')
    .setNumberFormat('₹#,##0');

  // 6. Subtle Modern Borders
  sheet.getRange('A5:F6').setBorder(true, true, true, true, true, true, t.borderColor, SpreadsheetApp.BorderStyle.SOLID);
  sheet.getRange('A8:F9').setBorder(true, true, true, true, true, true, t.borderColor, SpreadsheetApp.BorderStyle.SOLID);

  // 7. Executive Card Row Heights
  sheet.setRowHeight(5, 28);
  sheet.setRowHeight(6, 34);
  sheet.setRowHeight(7, 12);
  sheet.setRowHeight(8, 28);
  sheet.setRowHeight(9, 34);

  ss.toast(`Theme '${t.name}' applied to Rows 5-9!`, '🎨 Styling Applied', 4);
}
