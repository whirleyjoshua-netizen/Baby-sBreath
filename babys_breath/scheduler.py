import asyncio
import random
from datetime import datetime, timedelta

from babys_breath.config import (
    MORNING_WINDOW, AFTERNOON_WINDOW, EVENING_WINDOW,
    SURPRISE_PROBABILITY, SURPRISE_QUIET_START, SURPRISE_QUIET_END,
)
from babys_breath import database as db


class BabyScheduler:
    """Background loop that delivers scheduled check-ins and surprise messages."""

    def __init__(self, brain, on_message):
        self.brain = brain
        self.on_message = on_message  # async callback(mom_id, content, message_type)
        self._running = False
        self._task = None

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._loop())

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _loop(self):
        while self._running:
            try:
                await self._deliver_due_messages()
                await self._maybe_surprise()
            except Exception as e:
                print(f"[Scheduler] error: {e}")
            await asyncio.sleep(60)

    async def _deliver_due_messages(self):
        now = datetime.utcnow().isoformat()
        pending = await db.fetch_all(
            "SELECT * FROM scheduled_messages WHERE delivered = 0 AND scheduled_for <= ?",
            (now,)
        )
        for msg in pending:
            try:
                await self.on_message(msg["mom_id"], None, msg["message_type"])
                await db.execute(
                    "UPDATE scheduled_messages SET delivered = 1 WHERE id = ?",
                    (msg["id"],)
                )
            except Exception as e:
                print(f"[Scheduler] delivery error for msg {msg['id']}: {e}")

    async def _maybe_surprise(self):
        mom = await db.fetch_one("SELECT * FROM mom LIMIT 1")
        if not mom:
            return

        now = datetime.utcnow()
        hour = now.hour
        if hour >= SURPRISE_QUIET_START or hour < SURPRISE_QUIET_END:
            return

        if random.random() < SURPRISE_PROBABILITY:
            await self.on_message(mom["id"], None, "surprise")

    async def schedule_daily_checkins(self, mom_id: str):
        """Create tomorrow's 3 check-in schedule entries."""
        tomorrow = datetime.utcnow().date() + timedelta(days=1)

        for window, msg_type in [
            (MORNING_WINDOW, "checkin_morning"),
            (AFTERNOON_WINDOW, "checkin_afternoon"),
            (EVENING_WINDOW, "checkin_evening"),
        ]:
            hour = random.randint(window[0], window[1])
            minute = random.randint(0, 59)
            scheduled_time = datetime(tomorrow.year, tomorrow.month, tomorrow.day, hour, minute)

            await db.execute(
                "INSERT INTO scheduled_messages (mom_id, scheduled_for, message_type) VALUES (?, ?, ?)",
                (mom_id, scheduled_time.isoformat(), msg_type)
            )

    async def schedule_today_remaining(self, mom_id: str):
        """Schedule any remaining check-ins for today (used on first setup)."""
        now = datetime.utcnow()
        today = now.date()

        for window, msg_type in [
            (MORNING_WINDOW, "checkin_morning"),
            (AFTERNOON_WINDOW, "checkin_afternoon"),
            (EVENING_WINDOW, "checkin_evening"),
        ]:
            if now.hour < window[1]:
                hour = max(now.hour + 1, window[0])
                minute = random.randint(0, 59)
                scheduled_time = datetime(today.year, today.month, today.day, hour, minute)
                await db.execute(
                    "INSERT INTO scheduled_messages (mom_id, scheduled_for, message_type) VALUES (?, ?, ?)",
                    (mom_id, scheduled_time.isoformat(), msg_type)
                )
