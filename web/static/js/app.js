/**
 * Front-end Application Controller — Weekly 20W Darvas Box Backtester
 */

let state = {
  mode: 'universe',          // 'universe' or 'stock'
  variant: 'vanilla',         // 'vanilla' (default) or 'magic'
  lastRunId: null,
  lastRunData: null,
  activeTab: 'summary'
};

function formatIndianNumber(num) {
  if (isNaN(num) || num === null || num === undefined) return '0';
  return new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0 }).format(Math.floor(num));
}

function parseIndianNumber(str) {
  if (!str) return 0;
  const clean = String(str).replace(/[^\d]/g, '');
  return parseInt(clean, 10) || 0;
}

function getYesterdayDateStr() {
  const d = new Date();
  d.setDate(d.getDate() - 1);
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

function getDefaultStartDateStr() {
  const d = new Date();
  const yyyy = d.getFullYear() - 1;
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  return `${yyyy}-${mm}-01`;
}

document.addEventListener('DOMContentLoaded', () => {
  initVariantToggle();
  initModeToggle();
  initChips();
  initForm();
  initTabs();
  initDownloadBtn();
});

function initVariantToggle() {
  const btns = document.querySelectorAll('.variant-toggle-btn');
  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      btns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.variant = btn.dataset.variant;
      updateMagicCardVisibility();
    });
  });
}

function updateMagicCardVisibility() {
  const magicCard = document.getElementById('kpi-card-magic');
  if (magicCard) {
    if (state.variant === 'vanilla') {
      magicCard.classList.add('d-none');
    } else {
      magicCard.classList.remove('d-none');
    }
  }
}

const UNIVERSE_MAX_LIMITS = {
  'Nifty 50': 50,
  'Nifty Next 50': 50,
  'Nifty 100': 100,
  'Nifty F&O': 200
};

function updateUniverseMaxLimit() {
  const universeSelect = document.getElementById('universe-select');
  const maxStocksInput = document.getElementById('max-stocks');
  if (!universeSelect || !maxStocksInput) return;

  const selectedUniverse = universeSelect.value;
  const maxLimit = UNIVERSE_MAX_LIMITS[selectedUniverse] || 200;
  maxStocksInput.max = maxLimit;

  // If switched to a smaller universe and current input exceeds its universe size, clamp it
  const currentVal = parseInt(maxStocksInput.value, 10);
  if (currentVal > maxLimit) {
    maxStocksInput.value = maxLimit;
    updateTrancheCalcBox();
  }
}

function initModeToggle() {
  const btns = document.querySelectorAll('.mode-toggle-btn');
  const stockGroup = document.getElementById('stock-input-group');
  const universeGroup = document.getElementById('universe-input-group');
  const maxStocksGroup = document.getElementById('max-stocks-group');
  const capInput = document.getElementById('total-capital');
  const startInput = document.getElementById('start-date');

  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      btns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.mode = btn.dataset.mode;

      if (state.mode === 'stock') {
        stockGroup.classList.remove('d-none');
        universeGroup.classList.add('d-none');
        maxStocksGroup.classList.add('d-none');

        // Populate Individual Stock defaults
        if (capInput) {
          capInput.value = formatIndianNumber(40000);
        }
        if (startInput) {
          startInput.value = getDefaultStartDateStr();
        }
      } else {
        stockGroup.classList.add('d-none');
        universeGroup.classList.remove('d-none');
        maxStocksGroup.classList.remove('d-none');

        // Restore Universe defaults if currently on stock defaults
        if (capInput && parseIndianNumber(capInput.value) === 40000) {
          capInput.value = formatIndianNumber(1000000);
        }
        if (startInput && startInput.value === getDefaultStartDateStr()) {
          startInput.value = '2021-01-01';
        }
        updateUniverseMaxLimit();
      }
      updateTrancheCalcBox();
      updateTimePeriodBox();
    });
  });
}

function updateTrancheCalcBox() {
  const capInput = document.getElementById('total-capital');
  const totalCap = capInput ? parseIndianNumber(capInput.value) : 1000000;
  const numParts = parseInt(document.getElementById('num-parts')?.value, 10) || 4;
  const maxStocks = parseInt(document.getElementById('max-stocks')?.value, 10) || 25;

  let perTranche = 0;
  let subText = '';

  if (state.mode === 'stock') {
    perTranche = Math.floor(totalCap / numParts);
    subText = `Total Capital: ${formatIndianNumber(totalCap)} split into ${numParts} Tranches`;
  } else {
    const perStock = Math.floor(totalCap / maxStocks);
    perTranche = Math.floor(perStock / numParts);
    subText = `Capital per Stock: ${formatIndianNumber(perStock)} | ${numParts} Tranches (Max ${maxStocks} Concurrent Stocks)`;
  }

  const amtEl = document.getElementById('tranche-calc-amount');
  const subEl = document.getElementById('tranche-calc-sub');
  if (amtEl) amtEl.textContent = formatIndianNumber(perTranche);
  if (subEl) subEl.textContent = subText;
}

function updateTimePeriodBox() {
  const startInput = document.getElementById('start-date');
  const endInput = document.getElementById('end-date');
  if (!startInput || !endInput) return;

  const sVal = startInput.value;
  const eVal = endInput.value;
  const yearsEl = document.getElementById('time-period-years');
  const subEl = document.getElementById('time-period-sub');

  if (!sVal || !eVal) {
    if (yearsEl) yearsEl.textContent = '-';
    return;
  }

  const sDate = new Date(sVal);
  const eDate = new Date(eVal);
  const diffTime = eDate.getTime() - sDate.getTime();
  const diffDays = diffTime / (1000 * 60 * 60 * 24);

  if (diffDays <= 0 || isNaN(diffDays)) {
    if (yearsEl) yearsEl.textContent = '0.0 Years';
    if (subEl) subEl.textContent = 'Invalid date range';
    return;
  }

  const years = (diffDays / 365.25).toFixed(1);
  if (yearsEl) yearsEl.textContent = `${years} Years`;

  const sFormat = sDate.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
  const eFormat = eDate.toLocaleDateString('en-GB', { day: '2-digit', month: 'short', year: 'numeric' });
  if (subEl) subEl.textContent = `${sFormat} to ${eFormat}`;
}

function initChips() {
  const chips = document.querySelectorAll('.chip-item');
  const stockInput = document.getElementById('stock-symbol');
  chips.forEach(chip => {
    chip.addEventListener('click', () => {
      stockInput.value = chip.dataset.symbol;
    });
  });
}

function initTabs() {
  const tabBtns = document.querySelectorAll('.tab-btn');
  tabBtns.forEach(btn => {
    btn.addEventListener('click', () => {
      tabBtns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.activeTab = btn.dataset.tab;
      switchTab(btn.dataset.tab);
    });
  });
}

function switchTab(tabName) {
  document.querySelectorAll('.tab-pane').forEach(p => p.classList.add('d-none'));
  const targetPane = document.getElementById(`tab-pane-${tabName}`);
  if (targetPane) {
    targetPane.classList.remove('d-none');
  }
}

function initDownloadBtn() {
  const btn = document.getElementById('download-excel-btn');
  btn.addEventListener('click', () => {
    if (!state.lastRunId) return;
    window.location.href = `/api/export-excel?run_id=${encodeURIComponent(state.lastRunId)}`;
  });
}

function initForm() {
  const form = document.getElementById('backtest-form');
  const runBtn = document.getElementById('run-btn');
  const spinner = document.getElementById('run-spinner');
  const btnText = document.getElementById('run-btn-text');

  // Dynamic Yesterday End Date
  const endDateInput = document.getElementById('end-date');
  if (endDateInput) {
    const yestStr = getYesterdayDateStr();
    endDateInput.value = yestStr;
    endDateInput.max = yestStr;
  }

  // Indian Number Format for Total Capital
  const capitalInput = document.getElementById('total-capital');
  if (capitalInput) {
    capitalInput.value = formatIndianNumber(parseIndianNumber(capitalInput.value));
    capitalInput.addEventListener('input', () => {
      const raw = parseIndianNumber(capitalInput.value);
      capitalInput.value = raw > 0 ? formatIndianNumber(raw) : '';
      updateTrancheCalcBox();
    });
  }

  // Dynamic universe max stocks limit and listeners for live recalculation
  const universeSelect = document.getElementById('universe-select');
  if (universeSelect) {
    universeSelect.addEventListener('change', () => {
      updateUniverseMaxLimit();
      updateTrancheCalcBox();
    });
  }
  updateUniverseMaxLimit();

  // Listeners for live recalculation of per tranche buy amount box
  document.getElementById('num-parts')?.addEventListener('change', updateTrancheCalcBox);
  document.getElementById('max-stocks')?.addEventListener('input', updateTrancheCalcBox);
  updateTrancheCalcBox();

  // Listeners for live recalculation of time selection period card
  document.getElementById('start-date')?.addEventListener('change', updateTimePeriodBox);
  document.getElementById('end-date')?.addEventListener('change', updateTimePeriodBox);
  document.getElementById('start-date')?.addEventListener('input', updateTimePeriodBox);
  document.getElementById('end-date')?.addEventListener('input', updateTimePeriodBox);
  updateTimePeriodBox();
  updateMagicCardVisibility();

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    // Collect parameters
    const totalCapital = parseIndianNumber(document.getElementById('total-capital').value) || 1000000;
    const maxStocks = parseInt(document.getElementById('max-stocks').value, 10) || 25;
    const numParts = parseInt(document.getElementById('num-parts').value, 10) || 4;
    const startDate = document.getElementById('start-date').value || '2021-01-01';
    const endDate = document.getElementById('end-date').value || getYesterdayDateStr();
    const targetPct = parseFloat(document.getElementById('target-pct').value) || 5.0;
    const bullishMinReturn = parseFloat(document.getElementById('bullish-min-return').value) || 15.0;

    const payload = {
      mode: state.mode,
      variant: state.variant,
      total_capital: totalCapital,
      max_active_stocks: maxStocks,
      num_parts: numParts,
      start_date: startDate,
      end_date: endDate,
      target_pct: targetPct,
      bullish_min_return_pct: bullishMinReturn
    };

    if (state.mode === 'stock') {
      const sym = document.getElementById('stock-symbol').value.trim() || 'RELIANCE';
      payload.symbol = sym;
    } else {
      payload.universe = document.getElementById('universe-select').value;
    }

    // Set UI loading state and hide previous results to avoid confusion
    runBtn.disabled = true;
    spinner.classList.remove('d-none');
    btnText.textContent = state.mode === 'universe' ? 'Simulating Portfolio...' : 'Running Backtest...';
    document.getElementById('results-section').classList.add('d-none');
    document.getElementById('download-excel-btn').disabled = true;

    try {
      const response = await fetch('/api/backtest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
      });

      if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Backtest execution failed.');
      }

      const data = await response.json();
      state.lastRunId = data.run_id;
      state.lastRunData = data;

      // Render Results
      renderResults(data);
      document.getElementById('results-section').classList.remove('d-none');
      document.getElementById('download-excel-btn').disabled = false;
      document.getElementById('results-section').scrollIntoView({ behavior: 'smooth' });

    } catch (err) {
      alert(`Error: ${err.message}`);
    } finally {
      runBtn.disabled = false;
      spinner.classList.add('d-none');
      btnText.textContent = 'Run Backtest';
    }
  });
}

function formatNum(val, decimals = 2) {
  if (val === null || val === undefined || isNaN(val)) return '-';
  return Number(val).toLocaleString('en-IN', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals
  });
}

function renderResults(data) {
  const sum = data.summary;

  // Render KPI Cards (Amounts without decimal points)
  const returnAmt = (sum.total_portfolio_return_amount !== undefined)
    ? sum.total_portfolio_return_amount
    : (Math.round(((sum.total_realized_profit || 0) + (sum.unrealized_pnl || 0)) * 100) / 100);
  const roundedReturnAmt = Math.round(returnAmt);
  const retAmtEl = document.getElementById('kpi-return-amount');
  const retAmtCard = document.getElementById('kpi-card-return-amt');
  if (retAmtEl) {
    const prefix = roundedReturnAmt > 0 ? '+' : '';
    retAmtEl.textContent = `${prefix}${formatNum(roundedReturnAmt, 0)}`;
  }
  if (retAmtCard) {
    retAmtCard.classList.remove('kpi-emerald', 'kpi-rose', 'kpi-indigo');
    if (roundedReturnAmt > 0) {
      retAmtCard.classList.add('kpi-emerald');
    } else if (roundedReturnAmt < 0) {
      retAmtCard.classList.add('kpi-rose');
    } else {
      retAmtCard.classList.add('kpi-indigo');
    }
  }

  document.getElementById('kpi-realized-profit').textContent = formatNum(Math.round(sum.total_realized_profit || 0), 0);
  document.getElementById('kpi-trade-profit').textContent = formatNum(Math.round(sum.realized_trade_profit || 0), 0);
  const magicEl = document.getElementById('kpi-magic-profit');
  if (magicEl) magicEl.textContent = formatNum(Math.round(sum.total_magic_profit || 0), 0);
  updateMagicCardVisibility();
  document.getElementById('kpi-idle-interest').textContent = formatNum(Math.round(sum.idle_capital_interest || 0), 0);

  const divEl = document.getElementById('kpi-dividend-income');
  if (divEl) {
    divEl.textContent = formatNum(Math.round(sum.dividend_income || 0), 0);
  }

  const unrlEl = document.getElementById('kpi-unrealized-pnl');
  const unrlCard = document.getElementById('kpi-card-unrealized');
  const unrlVal = Math.round(sum.unrealized_pnl || 0);
  if (unrlEl) {
    const prefix = unrlVal > 0 ? '+' : '';
    unrlEl.textContent = `${prefix}${formatNum(unrlVal, 0)}`;
  }
  if (unrlCard) {
    unrlCard.classList.remove('kpi-emerald', 'kpi-rose');
    if (unrlVal > 0) {
      unrlCard.classList.add('kpi-emerald');
    } else if (unrlVal < 0) {
      unrlCard.classList.add('kpi-rose');
    }
  }

  document.getElementById('kpi-return-pct').textContent = `${formatNum(sum.total_portfolio_return_pct)}%`;
  document.getElementById('kpi-deployed-xirr').textContent = `${formatNum(sum.deployed_xirr_pct)}%`;
  document.getElementById('kpi-drawdown').textContent = `${formatNum(sum.max_drawdown_pct)}%`;
  document.getElementById('kpi-trades-count').textContent = `${sum.completed_trades} / ${sum.total_trades}`;

  const endCapEl = document.getElementById('kpi-ending-capital');
  if (endCapEl) {
    const endCapVal = sum.ending_overall_capital || (sum.total_capital + (sum.total_realized_profit || 0));
    endCapEl.textContent = formatNum(Math.round(endCapVal), 0);
  }

  const endTrancheEl = document.getElementById('kpi-ending-tranche-amt');
  if (endTrancheEl) {
    endTrancheEl.textContent = formatNum(Math.round(sum.ending_tranche_amount || 0), 0);
  }

  // Update Dynamic Tab Visibility based on Mode & Events
  const tabBreakdownBtn = document.getElementById('tab-btn-breakdown');
  const tabMagicBtn = document.getElementById('tab-btn-magic');
  const tabDivBtn = document.getElementById('tab-btn-dividends');

  if (data.dividend_events && data.dividend_events.length > 0) {
    tabDivBtn.classList.remove('d-none');
    renderDividendEvents(data.dividend_events);
  } else {
    tabDivBtn.classList.add('d-none');
  }

  // Render Monthly Summary for both single stock and universe modes
  renderMonthlySummary(data.monthly_summary);

  if (data.mode === 'universe') {
    tabBreakdownBtn.classList.remove('d-none');
    tabMagicBtn.classList.add('d-none');
    renderUniverseBreakdown(data.stock_summaries);
    renderTradesTable(data.trades);
    switchTab('breakdown');
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    tabBreakdownBtn.classList.add('active');
  } else {
    tabBreakdownBtn.classList.add('d-none');
    if (data.magic_events && data.magic_events.length > 0) {
      tabMagicBtn.classList.remove('d-none');
      renderMagicEvents(data.magic_events);
    } else {
      tabMagicBtn.classList.add('d-none');
    }
    renderTradesTable(data.trades);
    switchTab('trades');
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.getElementById('tab-btn-trades').classList.add('active');
  }
}

function renderUniverseBreakdown(stocks) {
  const tbody = document.getElementById('breakdown-tbody');
  tbody.innerHTML = '';

  if (!stocks || stocks.length === 0) {
    tbody.innerHTML = '<tr><td colspan="10" class="text-center">No stocks evaluated</td></tr>';
    return;
  }

  stocks.forEach(s => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${s.symbol}</strong></td>
      <td class="text-center">${s.total_trades}</td>
      <td class="text-center">${s.completed_trades}</td>
      <td class="text-center">${s.open_trades}</td>
      <td class="num-cell ${s.realized_trade_profit >= 0 ? 'text-profit' : 'text-loss'}">${formatNum(s.realized_trade_profit)}</td>
      <td class="num-cell text-profit">${formatNum(s.total_magic_profit)}</td>
      <td class="num-cell text-profit">${formatNum(s.dividend_income || 0)}</td>
      <td class="num-cell ${s.total_profit >= 0 ? 'text-profit' : 'text-loss'}"><strong>${formatNum(s.total_profit)}</strong></td>
      <td class="num-cell">${formatNum(s.open_positions_invested)}</td>
      <td class="num-cell ${s.unrealized_pnl >= 0 ? 'text-profit' : 'text-loss'}">${formatNum(s.unrealized_pnl)}</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderTradesTable(trades) {
  const tbody = document.getElementById('trades-tbody');
  tbody.innerHTML = '';

  if (!trades || trades.length === 0) {
    tbody.innerHTML = '<tr><td colspan="17" class="text-center">No trades executed</td></tr>';
    return;
  }

  trades.forEach(t => {
    const tr = document.createElement('tr');
    const badge = t.status === 'CLOSED' ? '<span class="badge-closed">CLOSED</span>' : '<span class="badge-open">OPEN</span>';
    const typeBadge = t.tranche_type === 'BULLISH'
      ? '<span class="badge-bullish">BULLISH</span>'
      : '<span class="badge-bearish">BEARISH</span>';
    const targetDisplay = typeof t.target_price === 'number' ? formatNum(t.target_price) : t.target_price;

    tr.innerHTML = `
      <td class="text-center">${t.trade_id}</td>
      <td><strong>${t.symbol}</strong></td>
      <td class="text-center">${typeBadge}</td>
      <td class="text-center">${t.slot_id}</td>
      <td class="text-center">${t.buy_date}</td>
      <td class="num-cell">${formatNum(t.buy_price)}</td>
      <td class="text-center">${t.shares}</td>
      <td class="num-cell">${formatNum(t.invested_amt)}</td>
      <td class="num-cell">${targetDisplay}</td>
      <td class="text-center">${t.sell_date}</td>
      <td class="num-cell">${t.sell_price ? formatNum(t.sell_price) : '-'}</td>
      <td class="num-cell ${(t.realized_pnl || 0) >= 0 ? 'text-profit' : 'text-loss'}">${formatNum(t.realized_pnl || 0)}</td>
      <td class="num-cell ${(t.return_pct || 0) >= 0 ? 'text-profit' : 'text-loss'}">${formatNum(t.return_pct || 0)}%</td>
      <td class="text-center">${t.holding_days}</td>
      <td class="text-center">${badge}</td>
      <td class="num-cell text-profit">${formatNum(t.magic_profit)}</td>
      <td class="num-cell text-profit">${formatNum(t.dividend || 0)}</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderMagicEvents(events) {
  const tbody = document.getElementById('magic-tbody');
  tbody.innerHTML = '';

  events.forEach(ev => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="text-center">${ev.event_id}</td>
      <td class="text-center">${ev.date}</td>
      <td class="text-center">#${ev.trade_id} (Slot ${ev.slot_id})</td>
      <td class="num-cell">${formatNum(ev.buy_price)}</td>
      <td class="num-cell">${formatNum(ev.rolling_20d_low)}</td>
      <td class="num-cell">${formatNum(ev.close_price)}</td>
      <td class="num-cell text-loss">${formatNum(ev.loss_pct)}%</td>
      <td class="num-cell text-profit"><strong>+${formatNum(ev.profit_credit)}</strong></td>
      <td class="text-center">${ev.open_tranches_in_loss}</td>
    `;
    tbody.appendChild(tr);
  });
}

function renderDividendEvents(events) {
  const tbody = document.getElementById('dividends-tbody');
  tbody.innerHTML = '';

  events.forEach(ev => {
    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td class="text-center">${ev.event_id}</td>
      <td class="text-center">${ev.date}</td>
      <td><strong>${ev.symbol}</strong></td>
      <td class="text-center">#${ev.trade_id}</td>
      <td class="text-center">Slot ${ev.slot_id}</td>
      <td class="text-center">${ev.buy_date}</td>
      <td class="text-center">${ev.shares}</td>
      <td class="num-cell">${formatNum(ev.dividend_per_share)}</td>
      <td class="num-cell text-profit"><strong>+${formatNum(ev.total_payout)}</strong></td>
    `;
    tbody.appendChild(tr);
  });
}

function renderMonthlySummary(records) {
  const tbody = document.getElementById('monthly-tbody');
  const tfoot = document.getElementById('monthly-tfoot');
  if (!tbody) return;
  tbody.innerHTML = '';
  if (tfoot) tfoot.innerHTML = '';

  if (!records || records.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" class="text-center">No monthly records available</td></tr>';
    return;
  }

  let sumTradeRealized = 0;
  let sumMagicProfit = 0;
  let sumDividend = 0;
  let sumIdleInterest = 0;
  let sumTotalRealized = 0;
  let peakCapitalBlocked = 0;

  records.forEach(r => {
    sumTradeRealized += r.trade_realized_profit || 0;
    sumMagicProfit += r.magic_profit || 0;
    sumDividend += r.dividend_income || 0;
    sumIdleInterest += r.idle_interest || 0;
    sumTotalRealized += r.total_realized_profit || 0;
    if ((r.max_capital_blocked || 0) > peakCapitalBlocked) peakCapitalBlocked = r.max_capital_blocked;

    const retPct = (r.max_capital_blocked && r.max_capital_blocked > 0)
      ? (r.total_realized_profit / r.max_capital_blocked) * 100.0
      : (r.monthly_return_pct || 0.0);

    const tr = document.createElement('tr');
    tr.innerHTML = `
      <td><strong>${r.year_mmm}</strong></td>
      <td class="num-cell ${(r.trade_realized_profit || 0) >= 0 ? 'text-profit' : 'text-loss'}">${formatNum(r.trade_realized_profit)}</td>
      <td class="num-cell text-profit">${formatNum(r.magic_profit)}</td>
      <td class="num-cell text-profit">${formatNum(r.dividend_income)}</td>
      <td class="num-cell text-profit">${formatNum(r.idle_interest)}</td>
      <td class="num-cell ${(r.total_realized_profit || 0) >= 0 ? 'text-profit' : 'text-loss'}"><strong>${formatNum(r.total_realized_profit)}</strong></td>
      <td class="num-cell">${formatNum(r.max_capital_blocked)}</td>
      <td class="num-cell">${formatNum(r.idle_unused_cash)}</td>
      <td class="num-cell ${retPct >= 0 ? 'text-profit' : 'text-loss'}"><strong>${retPct >= 0 ? '+' : ''}${formatNum(retPct)}%</strong></td>
    `;
    tbody.appendChild(tr);
  });

  if (tfoot) {
    const overallReturnPct = peakCapitalBlocked > 0 ? (sumTotalRealized / peakCapitalBlocked) * 100.0 : 0.0;
    const latestIdleCash = (records.length > 0) ? (records[records.length - 1].idle_unused_cash || 0) : 0;
    const trFoot = document.createElement('tr');
    trFoot.innerHTML = `
      <td><strong>Total / Peak</strong></td>
      <td class="num-cell ${sumTradeRealized >= 0 ? 'text-profit' : 'text-loss'}"><strong>${formatNum(sumTradeRealized)}</strong></td>
      <td class="num-cell text-profit"><strong>${formatNum(sumMagicProfit)}</strong></td>
      <td class="num-cell text-profit"><strong>${formatNum(sumDividend)}</strong></td>
      <td class="num-cell text-profit"><strong>${formatNum(sumIdleInterest)}</strong></td>
      <td class="num-cell ${sumTotalRealized >= 0 ? 'text-profit' : 'text-loss'}"><strong>${formatNum(sumTotalRealized)}</strong></td>
      <td class="num-cell"><strong>${formatNum(peakCapitalBlocked)}</strong></td>
      <td class="num-cell"><strong>${formatNum(latestIdleCash)}</strong></td>
      <td class="num-cell ${overallReturnPct >= 0 ? 'text-profit' : 'text-loss'}"><strong>${overallReturnPct >= 0 ? '+' : ''}${formatNum(overallReturnPct)}%</strong></td>
    `;
    tfoot.appendChild(trFoot);
  }
}

