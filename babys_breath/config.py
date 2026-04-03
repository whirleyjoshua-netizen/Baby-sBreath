import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Data directory
DATA_DIR = Path.home() / ".babys-breath"
DATA_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "babys_breath.db"

# API keys
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# LLM settings
LLM_TEMPERATURE = 0.85
LLM_MAX_TOKENS = 256
GROQ_MODEL = "llama-3.1-8b-instant"
GEMINI_MODEL = "gemini-2.0-flash"

# Scheduler settings
MORNING_WINDOW = (8, 9)      # 8am-9am
AFTERNOON_WINDOW = (13, 14)  # 1pm-2pm
EVENING_WINDOW = (19, 20)    # 7pm-8pm
SURPRISE_PROBABILITY = 0.011  # ~1 per 1.5 hours when checking every minute
SURPRISE_QUIET_START = 21     # no surprises after 9pm
SURPRISE_QUIET_END = 8        # no surprises before 8am

# Chat history
CHAT_HISTORY_LIMIT = 20  # messages sent to LLM for context
