import sys
import datetime

def dlog(message: str):
    """
    Direct log to stderr to ensure visibility in uvicorn console.
    """
    timestamp = datetime.datetime.now().strftime("%H:%M:%S")
    sys.stderr.write(f"[{timestamp}] [SFA-DEBUG] {message}\n")
    sys.stderr.flush()
