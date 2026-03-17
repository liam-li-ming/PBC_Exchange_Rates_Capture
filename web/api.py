import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import pandas as pd
import io, json, threading, math
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

import access_main_web
import parse_text_to_dataframe

app = FastAPI(title="PBC Exchange Rates")

_lock = threading.Lock()
_store: dict = {"df": None, "fetched_at": None}

_prog_lock = threading.Lock()
_prog: dict  = {"status": "idle", "phase": "idle", "current": 0, "total": 0}


class FetchRequest(BaseModel):
    records: int


# ── scraper (runs in FastAPI's thread pool via sync def endpoint) ─────────────

def _scrape(num_rows: int) -> pd.DataFrame:
    web = access_main_web.mainWeb()
    par = parse_text_to_dataframe.TextToDataFrameParser()

    pages_needed = min(math.ceil(num_rows / 20) + 2, 100)
    with _prog_lock:
        _prog.update({"status": "running", "phase": "indexing", "current": 0, "total": pages_needed})

    def on_index_done():
        with _prog_lock:
            _prog["current"] += 1

    links = web.fetch_links_for_rows(num_rows, on_progress=on_index_done)
    links = links.drop_duplicates(subset='url').reset_index(drop=True)

    with _prog_lock:
        _prog.update({"phase": "fetching", "current": 0, "total": len(links)})

    def process(d, url):
        try:
            html  = par.fetch_html_with_curl(url)
            text  = par.extract_text(html)
            parts = par.separate_Chinese_text(text)
            df    = par.extract_fx(parts)
            df.insert(0, "date", d)
            return df
        except Exception as e:
            print(f"  skip {d}: {e}")
            return None

    results = []
    cap = 1000
    with ThreadPoolExecutor(max_workers=cap) as ex:
        futures = {ex.submit(process, row["date"], row["url"]): row["date"]
                   for _, row in links.iterrows()}
        for future in as_completed(futures):
            r = future.result()
            if r is not None:
                results.append(r)
            with _prog_lock:
                _prog["current"] += 1

    with _prog_lock:
        _prog["status"] = "done"

    if not results:
        raise ValueError("No data was successfully processed")

    return (pd.concat(results, ignore_index=True)
              .drop_duplicates(subset='date')
              .sort_values("date")
              .reset_index(drop=True))


# ── API endpoints ─────────────────────────────────────────────────────────────

@app.post("/api/fetch")
def fetch(req: FetchRequest):
    if not 1 <= req.records <= 2000:
        raise HTTPException(400, "records must be 1–2000")
    try:
        df = _scrape(req.records)
    except Exception as e:
        raise HTTPException(500, str(e))

    with _lock:
        _store["df"]         = df
        _store["fetched_at"] = datetime.now().isoformat()

    # Side-effect: save Excel to parent dir (same as CLI)
    today      = datetime.now().strftime("%Y-%m-%d")
    parent_dir = os.path.join(os.path.dirname(__file__), "..")
    df.to_excel(os.path.join(parent_dir, f"PBC_Exchange_Rates_{today}.xlsx"), index=False)

    return {
        "status": "ok",
        "records": len(df),
        "fetched_at": _store["fetched_at"],
        "columns": list(df.columns),
        "data": json.loads(df.to_json(orient="records")),
    }


@app.get("/api/progress")
async def get_progress():
    with _prog_lock:
        p = dict(_prog)
    pct = round(p["current"] / p["total"] * 100) if p["total"] > 0 else 0
    return {**p, "percent": pct}


@app.get("/api/rates")
def rates():
    with _lock:
        df, ts = _store["df"], _store["fetched_at"]
    if df is None:
        raise HTTPException(404, "No data loaded. POST /api/fetch first.")
    return {
        "records": len(df),
        "fetched_at": ts,
        "columns": list(df.columns),
        "data": json.loads(df.to_json(orient="records")),
    }


@app.get("/api/download")
def download(format: str = "xlsx"):
    with _lock:
        df = _store["df"]
    if df is None:
        raise HTTPException(404, "No data loaded.")
    today = datetime.now().strftime("%Y-%m-%d")

    df = df.sort_values("date", ascending=False).reset_index(drop=True)

    if format == "csv":
        buf = io.BytesIO(df.to_csv(index=False).encode())
        return StreamingResponse(
            buf, media_type="text/csv",
            headers={"Content-Disposition": f"attachment; filename=PBC_Exchange_Rates_{today}.csv"},
        )

    buf = io.BytesIO()
    df.to_excel(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename=PBC_Exchange_Rates_{today}.xlsx"},
    )


# ── serve frontend (must come last) ──────────────────────────────────────────
static_dir = os.path.join(os.path.dirname(__file__), "static")
app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")
