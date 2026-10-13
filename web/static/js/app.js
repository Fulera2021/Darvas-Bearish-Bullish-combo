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
    });
  });
}

function initModeToggle() {
  const btns = document.querySelectorAll('.mode-toggle-btn');
  const stockGroup = document.getElementById('stock-input-group');
  const universeGroup = document.getElementById('universe-input-group');
  const maxStocksGroup = document.getElementById('max-stocks-group');

  btns.forEach(btn => {
    btn.addEventListener('click', () => {
      btns.forEach(b => b.classList.remove('active'));
      btn.classList.add('active');
      state.mode = btn.dataset.mode;

      if (state.mode === 'stock') {
        stockGroup.classList.remove('d-none');
        universeGroup.classList.add('d-none');
        maxStocksGroup.classList.add('d-none');
      } else {
        stockGroup.classList.add('d-none');
        universeGroup.classList.remove('d-none');
        maxStocksGroup.classList.remove('d-none');
      }
      updateTrancheCalcBox();
    });
  });
}

function updateTrancheCalcBox() {
  const capInput = document.getElementById('total-capital');
  const totalCap = capInput ? parseIndianNumber(capInput.value) : 1000000;
  const numParts = parseInt(document.getElementById('num-parts')?.value, 10) || 5;
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

  // Listeners for live recalculation of per tranche buy amount box
  document.getElementById('num-parts')?.addEventListener('change', updateTrancheCalcBox);
  document.getElementById('max-stocks')?.addEventListener('input', updateTrancheCalcBox);
  updateTrancheCalcBox();

  form.addEventListener('submit', async (e) => {
    e.preventDefault();

    // Collect parameters
    const totalCapital = parseIndianNumber(document.getElementById('total-capital').value) || 1000000;
    const maxStocks = parseInt(document.getElementById('max-stocks').value, 10) || 25;
    const numParts = parseInt(document.getElementById('num-parts').value, 10) || 5;
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

    // Set UI loading state
    runBtn.disabled = true;
    spinner.classList.remove('d-none');
    btnText.textContent = state.mode === 'universe' ? 'Simulating Portfolio...' : 'Running Backtest...';

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

  // Render KPI Cards
  document.getElementById('kpi-realized-profit').textContent = formatNum(sum.total_realized_profit);
  document.getElementById('kpi-trade-profit').textContent = formatNum(sum.realized_trade_profit);
  document.getElementById('kpi-magic-profit').textContent = formatNum(sum.total_magic_profit);
  document.getElementById('kpi-idle-interest').textContent = formatNum(sum.idle_capital_interest);

  const divEl = document.getElementById('kpi-dividend-income');
  if (divEl) {
    divEl.textContent = formatNum(sum.dividend_income || 0);
  }

  const unrlEl = document.getElementById('kpi-unrealized-pnl');
  const unrlCard = document.getElementById('kpi-card-unrealized');
  const unrlVal = sum.unrealized_pnl || 0;
  if (unrlEl) {
    const prefix = unrlVal > 0 ? '+' : '';
    unrlEl.textContent = `${prefix}${formatNum(unrlVal)}`;
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
