"""Universe definitions and constituent catalog for NSE equity backtesting."""

from typing import List, Dict

# Major Nifty 50 constituents (NSE Tickers)
NIFTY_50 = [
    "ADANIENT.NS", "ADANIPORTS.NS", "APOLLOHOSP.NS", "ASIANPAINT.NS", "AXISBANK.NS",
    "BAJAJ-AUTO.NS", "BAJAJFINSV.NS", "BAJFINANCE.NS", "BEL.NS", "BHARTIARTL.NS",
    "BSE.NS", "CIPLA.NS", "COALINDIA.NS", "DRREDDY.NS", "EICHERMOT.NS",
    "ETERNAL.NS", "GRASIM.NS", "HCLTECH.NS", "HDFCBANK.NS", "HDFCLIFE.NS",
    "HINDALCO.NS", "HINDUNILVR.NS", "ICICIBANK.NS", "INDIGO.NS", "INFY.NS",
    "ITC.NS", "JIOFIN.NS", "JSWSTEEL.NS", "KOTAKBANK.NS", "LT.NS",
    "M&M.NS", "MARUTI.NS", "MAXHEALTH.NS", "NESTLEIND.NS", "NTPC.NS",
    "ONGC.NS", "POWERGRID.NS", "RELIANCE.NS", "SBILIFE.NS", "SBIN.NS",
    "SHRIRAMFIN.NS", "SUNPHARMA.NS", "TATACONSUM.NS", "TATASTEEL.NS", "TCS.NS",
    "TECHM.NS", "TITAN.NS", "TMPV.NS", "TRENT.NS", "ULTRACEMCO.NS"
]

# Major Nifty Next 50 constituents
NIFTY_NEXT_50 = [
    "ABB.NS", "ADANIENSOL.NS", "ADANIGREEN.NS", "ADANIPOWER.NS", "AMBUJACEM.NS",
    "BAJAJHLDNG.NS", "BANKBARODA.NS", "BOSCHLTD.NS", "BPCL.NS", "BRITANNIA.NS",
    "CANBK.NS", "CGPOWER.NS", "CHOLAFIN.NS", "CUMMINSIND.NS", "DIVISLAB.NS",
    "DLF.NS", "DMART.NS", "ENRIN.NS", "GAIL.NS", "GODREJCP.NS",
    "HAL.NS", "HDFCAMC.NS", "HINDZINC.NS", "HYUNDAI.NS", "IDEA.NS",
    "IOC.NS", "IRFC.NS", "JINDALSTEL.NS", "LTM.NS", "MAZDOCK.NS",
    "MOTHERSON.NS", "MUTHOOTFIN.NS", "PFC.NS", "PIDILITIND.NS", "PNB.NS",
    "POLYCAB.NS", "POWERINDIA.NS", "SIEMENS.NS", "SOLARINDS.NS", "TATACAP.NS",
    "TATAPOWER.NS", "TMCV.NS", "TORNTPHARM.NS", "TVSMOTOR.NS", "UNIONBANK.NS",
    "VAML.NS", "VBL.NS", "VEDL.NS", "WIPRO.NS", "ZYDUSLIFE.NS"
]

# Combined Nifty 100
NIFTY_100 = NIFTY_50 + NIFTY_NEXT_50

# Nifty F&O universe (218 derivative contracts)
NIFTY_FNO = sorted([
    "360ONE.NS", "ABB.NS", "ABCAPITAL.NS", "ADANIENSOL.NS", "ADANIENT.NS",
    "ADANIGREEN.NS", "ADANIPORTS.NS", "ADANIPOWER.NS", "ALKEM.NS", "AMBER.NS",
    "AMBUJACEM.NS", "ANANDRATHI.NS", "ANGELONE.NS", "APLAPOLLO.NS", "APOLLOHOSP.NS",
    "ASHOKLEY.NS", "ASIANPAINT.NS", "ASTRAL.NS", "ATHERENERG.NS", "AUBANK.NS",
    "AUROPHARMA.NS", "AXISBANK.NS", "BAJAJ-AUTO.NS", "BAJAJFINSV.NS", "BAJFINANCE.NS",
    "BANDHANBNK.NS", "BANKBARODA.NS", "BANKINDIA.NS", "BDL.NS", "BEL.NS",
    "BHARATFORG.NS", "BHARTIARTL.NS", "BHEL.NS", "BIOCON.NS", "BLUESTARCO.NS",
    "BOSCHLTD.NS", "BPCL.NS", "BRITANNIA.NS", "BSE.NS", "CAMS.NS",
    "CANBK.NS", "CDSL.NS", "CGPOWER.NS", "CHOLAFIN.NS", "CIPLA.NS",
    "COALINDIA.NS", "COCHINSHIP.NS", "COFORGE.NS", "COLPAL.NS", "CONCOR.NS",
    "COROMANDEL.NS", "CROMPTON.NS", "CUB.NS", "CUMMINSIND.NS", "DABUR.NS",
    "DATAPATTNS.NS", "DELHIVERY.NS", "DIVISLAB.NS", "DIXON.NS", "DLF.NS",
    "DMART.NS", "DRREDDY.NS", "EICHERMOT.NS", "ENRIN.NS", "ETERNAL.NS",
    "FEDERALBNK.NS", "FORCEMOT.NS", "FORTIS.NS", "GAIL.NS", "GLENMARK.NS",
    "GMRAIRPORT.NS", "GODFRYPHLP.NS", "GODREJCP.NS", "GODREJPROP.NS", "GRASIM.NS",
    "GVT&D.NS", "HAL.NS", "HAVELLS.NS", "HCLTECH.NS", "HDFCAMC.NS",
    "HDFCBANK.NS", "HDFCLIFE.NS", "HEROMOTOCO.NS", "HINDALCO.NS", "HINDPETRO.NS",
    "HINDUNILVR.NS", "HINDZINC.NS", "HYUNDAI.NS", "ICICIBANK.NS", "ICICIGI.NS",
    "ICICILIFE.NS", "IDEA.NS", "IDFCFIRSTB.NS", "IEX.NS", "INDHOTEL.NS",
    "INDIANB.NS", "INDIGO.NS", "INDUSINDBK.NS", "INDUSTOWER.NS", "INFY.NS",
    "INOXWIND.NS", "IOC.NS", "IREDA.NS", "IRFC.NS", "ITC.NS",
    "JINDALSTEL.NS", "JIOFIN.NS", "JSWENERGY.NS", "JSWSTEEL.NS", "JUBLFOOD.NS",
    "KALYANKJIL.NS", "KARURVYSYA.NS", "KAYNES.NS", "KEI.NS", "KFINTECH.NS",
    "KOTAKBANK.NS", "KPITTECH.NS", "LAURUSLABS.NS", "LICHSGFIN.NS", "LICI.NS",
    "LODHA.NS", "LT.NS", "LTF.NS", "LTM.NS", "LUPIN.NS",
    "M&M.NS", "MAHABANK.NS", "MANAPPURAM.NS", "MANKIND.NS", "MARICO.NS",
    "MARUTI.NS", "MAXHEALTH.NS", "MAZDOCK.NS", "MCX.NS", "MFSL.NS",
    "MOTHERSON.NS", "MOTILALOFS.NS", "MPHASIS.NS", "MUTHOOTFIN.NS", "NAM-INDIA.NS",
    "NATIONALUM.NS", "NAUKRI.NS", "NAVINFLUOR.NS", "NBCC.NS", "NESTLEIND.NS",
    "NHPC.NS", "NMDC.NS", "NTPC.NS", "NYKAA.NS", "OBEROIRLTY.NS",
    "OFSS.NS", "OIL.NS", "ONGC.NS", "PAGEIND.NS", "PATANJALI.NS",
    "PAYTM.NS", "PERSISTENT.NS", "PETRONET.NS", "PFC.NS", "PGEL.NS",
    "PHOENIXLTD.NS", "PIDILITIND.NS", "PIIND.NS", "PNB.NS", "PNBHOUSING.NS",
    "POLICYBZR.NS", "POLYCAB.NS", "POWERGRID.NS", "POWERINDIA.NS", "PREMIERENE.NS",
    "PRESTIGE.NS", "RADICO.NS", "RBLBANK.NS", "RECLTD.NS", "RELIANCE.NS",
    "RVNL.NS", "SAGILITY.NS", "SAIL.NS", "SBICARD.NS", "SBILIFE.NS",
    "SBIN.NS", "SHREECEM.NS", "SHRIRAMFIN.NS", "SIEMENS.NS", "SOLARINDS.NS",
    "SONACOMS.NS", "SRF.NS", "SUNPHARMA.NS", "SUPREMEIND.NS", "SUZLON.NS",
    "SWIGGY.NS", "SYRMA.NS", "TATACONSUM.NS", "TATAELXSI.NS", "TATAPOWER.NS",
    "TATASTEEL.NS", "TCS.NS", "TECHM.NS", "TIINDIA.NS", "TITAN.NS",
    "TMPV.NS", "TORNTPHARM.NS", "TRENT.NS", "TVSMOTOR.NS", "UJJIVANSFB.NS",
    "ULTRACEMCO.NS", "UNIONBANK.NS", "UNITDSPR.NS", "UNOMINDA.NS", "UPL.NS",
    "VBL.NS", "VEDL.NS", "VMM.NS", "VOLTAS.NS", "WAAREEENER.NS",
    "WIPRO.NS", "YESBANK.NS", "ZYDUSLIFE.NS"
])

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
    """Normalize input stock ticker (supports NSE, BSE, NASDAQ, NYSE, AMEX, US)."""
    s = symbol.strip().upper()
    for prefix in ("NASDAQ:", "NYSE:", "AMEX:", "US:"):
        if s.startswith(prefix):
            return s[len(prefix):].strip()
    if s.startswith("BSE:"):
        clean = s[4:].strip()
        return clean if clean.endswith(".BO") else f"{clean}.BO"
    if s.startswith("NSE:"):
        clean = s[4:].strip()
        return clean if clean.endswith(".NS") else f"{clean}.NS"
    if s.endswith(".US"):
        return s[:-3]
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
