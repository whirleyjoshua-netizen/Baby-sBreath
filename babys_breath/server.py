import asyncio
import uuid
from contextlib import asynccontextmanager
from datetime import date, datetime
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from babys_breath import database as db
from babys_breath.llm import BabyBrain
from babys_breath.baby import BabyContext, build_system_prompt, get_checkin_prompt, get_surprise_prompt
from babys_breath.pregnancy_data import get_current_week, get_week_info, get_trimester, weeks_remaining
from babys_breath.mood import detect_mood_keyword, calculate_trend, should_nudge
from babys_breath.scheduler import BabyScheduler
from babys_breath.config import CHAT_HISTORY_LIMIT

STATIC_DIR = Path(__file__).parent / "static"

# WebSocket connections
ws_connections: list[WebSocket] = []

# Global references
brain: BabyBrain = None
scheduler: BabyScheduler = None


async def handle_scheduled_message(mom_id: str, _content, message_type: str):
    """Called by scheduler when a message is due."""
    ctx = await build_context(mom_id)

    if message_type == "surprise":
        prompt = get_surprise_prompt()
    else:
        prompt = get_checkin_prompt(message_type)

    system = build_system_prompt(ctx)
    messages = ctx.recent_messages + [{"role": "user", "content": prompt}]
    content = await brain.think(system, messages)

    await db.execute(
        "INSERT INTO messages (mom_id, role, content, message_type) VALUES (?, ?, ?, ?)",
        (mom_id, "baby", content, message_type)
    )

    # Push to any open WebSocket connections
    for ws in ws_connections[:]:
        try:
            await ws.send_json({"type": "baby_message", "content": content, "message_type": message_type})
        except Exception:
            ws_connections.remove(ws)


async def build_context(mom_id: str) -> BabyContext:
    mom = await db.fetch_one("SELECT * FROM mom WHERE id = ?", (mom_id,))
    due = date.fromisoformat(mom["due_date"])
    week = get_current_week(due)
    week_info = get_week_info(week)

    recent_msgs = await db.fetch_all(
        "SELECT role, content FROM messages WHERE mom_id = ? ORDER BY created_at DESC LIMIT ?",
        (mom_id, CHAT_HISTORY_LIMIT)
    )
    recent_msgs.reverse()
    chat_history = [{"role": "user" if m["role"] == "mom" else "assistant", "content": m["content"]} for m in recent_msgs]

    moods = await db.fetch_all(
        "SELECT mood, mood_score, created_at FROM mood_log WHERE mom_id = ? ORDER BY created_at DESC LIMIT 7",
        (mom_id,)
    )
    moods.reverse()
    trend = calculate_trend(moods)
    nudge = should_nudge(moods)

    now = datetime.utcnow()
    hour = now.hour
    if hour < 12:
        tod = "morning"
    elif hour < 17:
        tod = "afternoon"
    elif hour < 21:
        tod = "evening"
    else:
        tod = "night"

    return BabyContext(
        mom_name=mom["name"],
        baby_name=mom["baby_name"] or "Baby",
        due_date=due,
        current_week=week,
        baby_gender=mom["baby_gender"],
        week_info=week_info,
        recent_moods=moods,
        mood_trend=trend,
        recent_messages=chat_history,
        time_of_day=tod,
        needs_nudge=nudge,
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    global brain, scheduler
    await db.init_db()
    brain = BabyBrain()
    scheduler = BabyScheduler(brain, handle_scheduled_message)
    await scheduler.start()

    # Schedule daily check-ins at midnight (simplified: schedule on startup)
    mom = await db.fetch_one("SELECT * FROM mom LIMIT 1")
    if mom:
        await scheduler.schedule_today_remaining(mom["id"])

    yield
    await scheduler.stop()


app = FastAPI(title="Baby's Breath", lifespan=lifespan)


# ─── Static files ───

@app.get("/", response_class=HTMLResponse)
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/manifest.json")
async def manifest():
    return FileResponse(STATIC_DIR / "manifest.json")


@app.get("/sw.js")
async def service_worker():
    return FileResponse(STATIC_DIR / "sw.js", media_type="application/javascript")


app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ─── Setup ───

@app.post("/api/setup")
async def setup(request: Request):
    data = await request.json()
    mom_id = str(uuid.uuid4())

    await db.execute(
        "INSERT INTO mom (id, name, baby_name, due_date, baby_gender, timezone) VALUES (?, ?, ?, ?, ?, ?)",
        (mom_id, data["name"], data.get("baby_name", ""), data["due_date"],
         data.get("baby_gender", "unknown"), data.get("timezone", "America/New_York"))
    )

    # Generate first message from baby
    due = date.fromisoformat(data["due_date"])
    week = get_current_week(due)
    week_info = get_week_info(week)
    baby_name = data.get("baby_name") or "Baby"

    ctx = BabyContext(
        mom_name=data["name"],
        baby_name=baby_name,
        due_date=due,
        current_week=week,
        baby_gender=data.get("baby_gender", "unknown"),
        week_info=week_info,
        time_of_day="afternoon",
    )

    system = build_system_prompt(ctx)
    first_msg_prompt = (
        f"This is your VERY FIRST message to mom! She just set up the app to talk to you. "
        f"Introduce yourself warmly. You're {baby_name} at week {week}. "
        f"Tell her how excited you are to talk to her. Make her feel this is real and special. "
        f"Keep it to 2-3 short sentences."
    )
    content = await brain.think(system, [{"role": "user", "content": first_msg_prompt}])

    await db.execute(
        "INSERT INTO messages (mom_id, role, content, message_type) VALUES (?, ?, ?, ?)",
        (mom_id, "baby", content, "chat")
    )

    # Schedule check-ins
    await scheduler.schedule_today_remaining(mom_id)
    await scheduler.schedule_daily_checkins(mom_id)

    return {"mom_id": mom_id, "first_message": content, "week": week}


# ─── Chat ───

@app.post("/api/chat")
async def chat(request: Request):
    data = await request.json()
    mom = await db.fetch_one("SELECT * FROM mom LIMIT 1")
    if not mom:
        return JSONResponse({"error": "Not set up yet"}, status_code=400)

    mom_id = mom["id"]
    message = data["message"]

    # Save mom's message
    await db.execute(
        "INSERT INTO messages (mom_id, role, content, message_type) VALUES (?, ?, ?, ?)",
        (mom_id, "mom", message, "chat")
    )

    # Detect mood
    mood_detected = None
    mood_result = detect_mood_keyword(message)
    if mood_result:
        mood_label, mood_score = mood_result
        await db.execute(
            "INSERT INTO mood_log (mom_id, mood, mood_score, notes, source) VALUES (?, ?, ?, ?, ?)",
            (mom_id, mood_label, mood_score, message, "chat")
        )
        mood_detected = {"mood": mood_label, "score": mood_score}

    # Build context and respond
    ctx = await build_context(mom_id)
    system = build_system_prompt(ctx)
    messages = ctx.recent_messages + [{"role": "user", "content": message}]
    reply = await brain.think(system, messages)

    # Save baby's reply
    await db.execute(
        "INSERT INTO messages (mom_id, role, content, message_type) VALUES (?, ?, ?, ?)",
        (mom_id, "baby", reply, "chat")
    )

    return {"reply": reply, "mood_detected": mood_detected}


@app.get("/api/messages")
async def get_messages(page: int = 1, per_page: int = 50):
    mom = await db.fetch_one("SELECT * FROM mom LIMIT 1")
    if not mom:
        return {"messages": []}

    offset = (page - 1) * per_page
    messages = await db.fetch_all(
        "SELECT role, content, message_type, created_at FROM messages WHERE mom_id = ? ORDER BY created_at ASC LIMIT ? OFFSET ?",
        (mom["id"], per_page, offset)
    )
    return {"messages": messages}


# ─── Mood ───

@app.get("/api/mood/trend")
async def mood_trend():
    mom = await db.fetch_one("SELECT * FROM mom LIMIT 1")
    if not mom:
        return {"trend": "stable", "entries": []}

    moods = await db.fetch_all(
        "SELECT mood, mood_score, created_at FROM mood_log WHERE mom_id = ? ORDER BY created_at DESC LIMIT 7",
        (mom["id"],)
    )
    moods.reverse()
    trend = calculate_trend(moods)
    return {"trend": trend, "entries": moods}


@app.get("/api/mood/history")
async def mood_history():
    mom = await db.fetch_one("SELECT * FROM mom LIMIT 1")
    if not mom:
        return {"entries": []}

    moods = await db.fetch_all(
        "SELECT mood, mood_score, created_at FROM mood_log WHERE mom_id = ? ORDER BY created_at ASC",
        (mom["id"],)
    )
    return {"entries": moods}


# ─── Pregnancy Info ───

@app.get("/api/week")
async def current_week():
    mom = await db.fetch_one("SELECT * FROM mom LIMIT 1")
    if not mom:
        return JSONResponse({"error": "Not set up yet"}, status_code=400)

    due = date.fromisoformat(mom["due_date"])
    week = get_current_week(due)
    info = get_week_info(week)
    return {
        "week": week,
        "trimester": get_trimester(week),
        "weeks_remaining": weeks_remaining(due),
        "info": info,
    }


@app.get("/api/profile")
async def profile():
    mom = await db.fetch_one("SELECT * FROM mom LIMIT 1")
    if not mom:
        return JSONResponse({"error": "Not set up yet"}, status_code=404)

    due = date.fromisoformat(mom["due_date"])
    week = get_current_week(due)
    return {
        "name": mom["name"],
        "baby_name": mom["baby_name"],
        "due_date": mom["due_date"],
        "baby_gender": mom["baby_gender"],
        "week": week,
        "trimester": get_trimester(week),
        "weeks_remaining": weeks_remaining(due),
    }


# ─── WebSocket ───

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_connections.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        ws_connections.remove(ws)


def main():
    import uvicorn
    uvicorn.run("babys_breath.server:app", host="0.0.0.0", port=8090, reload=True)


if __name__ == "__main__":
    main()
