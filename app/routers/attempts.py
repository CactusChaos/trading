from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime, timezone
import httpx
import logging

from app.database import get_db
from app.models import Attempt, Project
from app.schemas import AttemptCreate, Attempt as AttemptSchema, RunAttemptRequest
from app.backtester import Backtester

logger = logging.getLogger(__name__)
router = APIRouter()

GAMMA_API_URL = "https://gamma-api.polymarket.com"
DEFILLAMA_BLOCK_URL = "https://coins.llama.fi/block/polygon"

async def timestamp_to_block(ts: int) -> int:
    """Convert a Unix timestamp to the nearest Polygon block number via DefiLlama."""
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get(f"{DEFILLAMA_BLOCK_URL}/{ts}")
        resp.raise_for_status()
        return int(resp.json()["height"])

async def resolve_market_blocks(market_slug: str) -> tuple[int, int]:
    """
    Fetch the event's start and end dates from Polymarket Gamma API
    and convert them to Polygon block numbers.

    KEY: We use the *event-level* startDate/endDate, not the sub-market's
    closedTime/endDate, which can be a very narrow window (e.g. 1 hour).
    Returns (start_block, end_block).
    """
    def parse_dt(s: str) -> int:
        """Parse various ISO date strings to Unix timestamp."""
        s = s.strip()
        # Normalise '+00' suffix to '+00:00' so fromisoformat handles it
        if s.endswith("+00"):
            s = s + ":00"
        # Replace space separator with T
        s = s.replace(" ", "T", 1)
        # Normalise trailing Z
        s = s.replace("Z", "+00:00")
        try:
            return int(datetime.fromisoformat(s).astimezone(timezone.utc).timestamp())
        except ValueError as e:
            raise ValueError(f"Could not parse date string '{s}': {e}")

    async with httpx.AsyncClient(timeout=15) as client:
        event = None
        market = None

        # Try fetching as an event slug — events carry the full date range
        resp = await client.get(f"{GAMMA_API_URL}/events", params={"slug": market_slug})
        if resp.status_code == 200 and resp.json():
            event = resp.json()[0]
            markets = event.get("markets", [])
            for m in markets:
                if m.get("clobTokenIds"):
                    market = m
                    break
            if not market and markets:
                market = markets[0]

        # Fallback: try as direct market slug
        if not market:
            resp = await client.get(f"{GAMMA_API_URL}/markets", params={"slug": market_slug})
            if resp.status_code == 200 and resp.json():
                market = resp.json()[0]
                # Try to grab the parent event for better date coverage
                if market.get("events"):
                    event = market["events"][0]

        if not market:
            raise ValueError(f"Could not find market '{market_slug}' on Polymarket.")

        # Prefer event-level dates — they span the full market lifetime.
        # Sub-market closedTime is often very close to createdAt (narrow window).
        if event:
            start_str = event.get("startDate") or event.get("creationDate") or event.get("createdAt")
            end_str = event.get("endDate") or event.get("closedTime")
        else:
            start_str = market.get("startDate") or market.get("createdAt")
            end_str = market.get("endDate") or market.get("closedTime")

        if not start_str:
            raise ValueError("Market/event has no startDate to auto-detect block range.")

        start_ts = parse_dt(start_str)
        end_ts = int(datetime.now(timezone.utc).timestamp()) if not end_str else parse_dt(end_str)

        logger.info(f"Resolving blocks for '{market_slug}': {start_str} → {end_str or 'now'}")

        start_block = await timestamp_to_block(start_ts)
        end_block = await timestamp_to_block(end_ts)

        logger.info(f"Resolved blocks: {start_block} → {end_block} ({end_block - start_block:,} blocks)")
        return start_block, end_block


@router.post("/projects/{project_id}/attempts", response_model=AttemptSchema)
async def create_attempt(project_id: str, attempt: AttemptCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Project).where(Project.id == project_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Project not found")
        
    db_attempt = Attempt(project_id=project_id, **attempt.model_dump())
    db.add(db_attempt)
    await db.commit()
    await db.refresh(db_attempt)
    return db_attempt

@router.get("/attempts/{attempt_id}", response_model=AttemptSchema)
async def get_attempt(attempt_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Attempt).where(Attempt.id == attempt_id))
    attempt = result.scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
    return attempt

@router.post("/attempts/{attempt_id}/run", response_model=AttemptSchema)
async def run_attempt(attempt_id: str, payload: RunAttemptRequest, db: AsyncSession = Depends(get_db)):
    # 1. Fetch Attempt & Project
    result = await db.execute(select(Attempt).where(Attempt.id == attempt_id))
    attempt = result.scalar_one_or_none()
    if not attempt:
        raise HTTPException(status_code=404, detail="Attempt not found")
        
    proj_result = await db.execute(select(Project).where(Project.id == attempt.project_id))
    project = proj_result.scalar_one_or_none()
    if not project or not project.token_id:
        raise HTTPException(status_code=400, detail="Project has no token_id selected")

    attempt.status = "running"
    await db.commit()
    
    try:
        start_block = payload.start_block
        end_block = payload.end_block
        blocks = payload.blocks_to_fetch

        # 2a. Auto-resolve block range from market timeline if requested
        if payload.auto_range:
            if not project.market_slug:
                raise ValueError("Project has no market_slug; cannot auto-detect block range.")
            attempt.results = {"status": "Resolving market timeline via Polymarket & DefiLlama..."}
            await db.commit()
            start_block, end_block = await resolve_market_blocks(project.market_slug)
            blocks = None  # Use explicit range instead

        # 2b. Resolve block range from a relative time period (last N hours)
        elif payload.period_hours is not None:
            now_ts = int(datetime.now(timezone.utc).timestamp())
            start_ts = int(now_ts - payload.period_hours * 3600)
            attempt.results = {"status": f"Resolving last {payload.period_hours}h block range via DefiLlama..."}
            await db.commit()
            start_block = await timestamp_to_block(start_ts)
            end_block = await timestamp_to_block(now_ts)
            blocks = None
            logger.info(f"Period mode: {payload.period_hours}h → blocks {start_block}→{end_block}")

        # 3. Resolve tokens to run
        tokens_to_run = []
        if payload.run_all_outcomes:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(f"{GAMMA_API_URL}/markets", params={"slug": project.market_slug})
                if resp.status_code == 200 and resp.json():
                    import json
                    market_data = resp.json()[0]
                    tokens_to_run = json.loads(market_data.get("clobTokenIds", "[]"))
            if not tokens_to_run:
                tokens_to_run = [project.token_id]
        elif payload.token_id:
            tokens_to_run = [payload.token_id]
        else:
            tokens_to_run = [project.token_id]

        # 4. Run Backtester
        bt = Backtester(initial_capital=payload.initial_capital / len(tokens_to_run))
        all_results = []
        chart_base64 = ""
        
        for tid in tokens_to_run:
            try:
                data = bt.fetch_data(
                    token_id=tid,
                    blocks=blocks,
                    start_block=start_block,
                    end_block=end_block
                )
                if len(data["prices"]) == 0:
                    continue
                signals = bt.execute_model(attempt.model_code, data["prices"], data["volumes"])
                res = bt.run_backtest(data["prices"], signals)
                res["token_id"] = tid
                if not chart_base64:
                    chart_base64 = bt.generate_chart(data["prices"], res["equity_curve"], data["timestamps"])
                all_results.append(res)
            except Exception as e:
                logger.error(f"Error running token {tid}: {e}")

        if not all_results:
            hint = f"Blocks {start_block}→{end_block}" if start_block else f"last {blocks} blocks"
            raise ValueError(f"No trades found in {hint}. Try a different time range.")

        # 5. Combine Results
        if len(all_results) == 1:
            results = all_results[0]
            del results["token_id"]
        else:
            total_trades = sum(r["trades"] for r in all_results)
            total_final_equity = sum(r["final_equity"] for r in all_results)
            total_return = (total_final_equity - payload.initial_capital) / payload.initial_capital * 100
            
            trade_logs = []
            for r in all_results:
                for t in r["trade_log"]:
                    t["type"] = f"{t['type']} ({r['token_id'][:4]})"
                trade_logs.extend(r["trade_log"])
            trade_logs.sort(key=lambda x: x["step"])

            results = {
                "initial_capital": payload.initial_capital,
                "final_equity": total_final_equity,
                "total_return_pct": total_return,
                "max_drawdown_pct": sum(r["max_drawdown_pct"] for r in all_results) / len(all_results),
                "sharpe_ratio": sum(r["sharpe_ratio"] for r in all_results) / len(all_results),
                "trades": total_trades,
                "trade_log": trade_logs
            }

        results["chart_base64"] = chart_base64
        results["block_range"] = {"start": start_block, "end": end_block}
        
        if "equity_curve" in results:
            del results["equity_curve"]

        attempt.results = results
        attempt.status = "completed"
    except Exception as e:
        attempt.status = "failed"
        attempt.results = {"error": str(e)}
        
    await db.commit()
    await db.refresh(attempt)
    return attempt
