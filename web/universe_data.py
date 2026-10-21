"""Universe definitions and constituent catalog for NSE equity backtesting."""

from typing import List, Dict

# Major Nifty 50 constituents (NSE Tickers)
NIFTY_50 = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS",
    "BAJAJ-AUTO.NS", "BAJFINANCE.NS", "BAJAJFINSV.NS", "BEL.NS", "BPCL.NS",
    "BHARTIARTL.NS", "BRITANNIA.NS", "CIPLA.NS", "COALINDIA.NS", "DRREDDY.NS",
    "EICHERMOT.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
    "HEROMOTOCO.NS", "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "ITC.NS",
    "INDUSINDBK.NS", "INFY.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS",
    "M&M.NS", "MARUTI.NS", "NTPC.NS", "NESTLEIND.NS", "ONGC.NS",
    "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SHRIRAMFIN.NS", "SBIN.NS",
    "SUNPHARMA.NS", "TCS.NS", "TATACONSUM.NS", "TMPV.NS", "TATASTEEL.NS",
    "TECHM.NS", "TITAN.NS", "TRENT.NS", "ULTRACEMCO.NS", "WIPRO.NS"
]

# Major Nifty Next 50 constituents
NIFTY_NEXT_50 = [
    "ABB.NS", "ADANIENSOL.NS", "ADANIGREEN.NS", "ADANIPOWER.NS", "ATGL.NS",
    "AMBUJACEM.NS", "BANKBARODA.NS", "BERGEPAINT.NS", "BOSCHLTD.NS", "CANBK.NS",
    "CHOLAFIN.NS", "COLPAL.NS", "DLF.NS", "DABUR.NS", "DIVISLAB.NS",
    "GAIL.NS", "GODREJCP.NS", "HAL.NS", "HAVELLS.NS", "ICICIGI.NS",
    "ICICIPRULI.NS", "IOC.NS", "IRCTC.NS", "IRFC.NS", "JINDALSTEL.NS",
    "JIOFIN.NS", "LTM.NS", "MARICO.NS", "MOTHERSON.NS", "NAUKRI.NS",
    "NHPC.NS", "PFC.NS", "PIDILITIND.NS", "PNB.NS", "RECLTD.NS",
    "RVNL.NS", "SBICARD.NS", "SIEMENS.NS", "SRF.NS", "SUNTV.NS",
    "TVSMOTOR.NS", "TORNTPHARM.NS", "UNITDSPR.NS", "VBL.NS", "VEDL.NS",
    "ZYDUSLIFE.NS", "ETERNAL.NS", "POLICYBZR.NS", "PERSISTENT.NS", "CUMMINSIND.NS"
]

# Combined Nifty 100
NIFTY_100 = sorted(list(set(NIFTY_50 + NIFTY_NEXT_50)))

# Nifty F&O universe (highly liquid derivative contracts)
NIFTY_FNO = sorted(list(set(NIFTY_100 + [
    "AARTIIND.NS", "ABFRL.NS", "ACC.NS", "ALKEM.NS", "APOLLOTYRE.NS",
    "ASHOKLEY.NS", "ASTRAL.NS", "AUBANK.NS", "AUROPHARMA.NS", "BALKRISIND.NS",
    "BANDHANBNK.NS", "BATAINDIA.NS", "BHARATFORG.NS", "BHEL.NS", "BIOCON.NS",
    "BSOFT.NS", "CANFINHOME.NS", "CHAMBLFERT.NS", "COFORGE.NS", "CONCOR.NS",
    "COROMANDEL.NS", "CROMPTON.NS", "DEEPAKNTR.NS", "DELHIVERY.NS", "DIXON.NS",
    "ESCORTS.NS", "EXIDEIND.NS", "FEDERALBNK.NS", "GLENMARK.NS", "GMRAIRPORT.NS",
    "GNFC.NS", "GODREJPROP.NS", "GRANULES.NS", "GUJENERGY.NS", "HDFCAMC.NS",
    "HINDCOPPER.NS", "HINDPETRO.NS", "IDFCFIRSTB.NS", "IEX.NS",
    "IGL.NS", "INDHOTEL.NS", "INDIACEM.NS", "INDIAMART.NS", "INDIGO.NS",
    "INDUSTOWER.NS", "IPCALAB.NS", "JPPOWER.NS", "JUBLFOOD.NS", "KALYANKJIL.NS",
    "LTF.NS", "LALPATHLAB.NS", "LICHSGFIN.NS", "LUPIN.NS", "M&MFIN.NS",
    "MANAPPURAM.NS", "MCX.NS", "METROPOLIS.NS", "MFSL.NS", "MGL.NS",
    "MPHASIS.NS", "MRF.NS", "MUTHOOTFIN.NS", "NATIONALUM.NS", "NAVINFLUOR.NS",
    "NMDC.NS", "OBEROIRLTY.NS", "OFSS.NS", "PAGEIND.NS", "PIRAMALFIN.NS",
    "PETRONET.NS", "PVRINOX.NS", "RAMCOCEM.NS", "RBLBANK.NS", "SAIL.NS",
    "SUPREMEIND.NS", "SYNGENE.NS", "TATACHEM.NS", "TATACOMM.NS", "TATAPOWER.NS",
    "TORNTPOWER.NS", "UBL.NS", "VOLTAS.NS"
])))

# Load Nifty 500 constituents if available
import os
import json
from pathlib import Path

EXCLUDED_NIFTY500 = {"BAGMANE.NS", "BAGMANE", "DUMMYHEG.NS", "DUMMYHEG"}

NIFTY500_FILE = Path(__file__).parent.parent / "data" / "nifty500_symbols.json"
NIFTY_500: List[str] = []
if NIFTY500_FILE.exists():
    try:
        with open(NIFTY500_FILE, "r", encoding="utf-8") as _f:
            raw_symbols = json.load(_f)
            NIFTY_500 = [s for s in raw_symbols if s not in EXCLUDED_NIFTY500 and s.replace(".NS", "") not in EXCLUDED_NIFTY500]
    except Exception:
        pass

UNIVERSES: Dict[str, List[str]] = {
    "Nifty 50": NIFTY_50,
    "Nifty Next 50": NIFTY_NEXT_50,
    "Nifty 100": NIFTY_100,
    "Nifty F&O": NIFTY_FNO
}
if NIFTY_500:
    UNIVERSES["Nifty 500"] = NIFTY_500

def normalize_symbol(symbol: str) -> str:
    """Normalize input stock ticker to standard NSE format (e.g. RELIANCE, NSE:RELIANCE -> RELIANCE.NS)."""
    s = symbol.strip().upper()
    for prefix in ("NSE:", "BSE:"):
        if s.startswith(prefix):
            s = s[len(prefix):].strip()
    if s.startswith("^") or s.endswith(".NS") or s.endswith(".BO"):
        return s
    return f"{s}.NS"

def get_universe_symbols(name: str) -> List[str]:
    """Retrieve symbols list for a specified universe name."""
    if name not in UNIVERSES:
        raise ValueError(f"Unknown universe '{name}'. Available: {list(UNIVERSES.keys())}")
    return UNIVERSES[name]

def get_all_universes() -> Dict[str, int]:
    """Return dictionary of universe names and their constituent counts."""
    return {name: len(syms) for name, syms in UNIVERSES.items()}
