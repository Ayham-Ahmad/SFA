import logging
import time
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

# Configure Logging
logging.basicConfig(
    filename="audit.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("audit")

class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Process Request
        response = await call_next(request)
        
        process_time = time.time() - start_time
        
        # Log Details
        log_data = {
            "method": request.method,
            "url": str(request.url),
            "status_code": response.status_code,
            "process_time": f"{process_time:.4f}s",
            "client": request.client.host if request.client else "unknown"
        }
        
        logger.info(f"Request: {log_data}")
        
        return response
