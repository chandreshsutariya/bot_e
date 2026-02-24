from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from loguru import logger
import sys
import time
from prometheus_fastapi_instrumentator import Instrumentator
# from agent.chat import process_user_message
from agent.chat_graph import process_user_message

logger.remove() 
logger.add(sys.stdout, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}", level="INFO")
logger.add("logs/app.log", rotation="10 MB", retention="7 days", compression="zip")

sys.stdout.reconfigure(encoding='utf-8')

app = FastAPI()

templates = Jinja2Templates(directory="templates")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to frontend domain in production
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)

Instrumentator().instrument(app).expose(app)

@app.middleware("http")
async def log_request_time(request: Request, call_next):
    start_time = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception as e:
        logger.exception(f"Unhandled error for {request.method} {request.url}: {e}")
        raise
    process_time = time.perf_counter() - start_time
    logger.info(f"{request.method} {request.url} completed in {process_time:.2f}s")
    return response

class ChatInput(BaseModel):
    session_id: str
    message: str
    username: Optional[str] = None
    user_lang: Optional[str] = "En"    # Language : "En" or "Tr"
    context: str = "customer_support"

@app.get("/", response_class=HTMLResponse)
async def serve_home(request: Request):
    logger.info("Serving homepage")
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/ping")
def ping():
    logger.info("Ping check received")
    return {"status": "ok"}

@app.post("/chat")
async def chat_api(data: ChatInput):
    logger.info(f"Incoming chat: [session={data.session_id}] ({data.username}) ({data.user_lang}), msg={data.message}")
    try:
        response = await process_user_message(
            message=data.message,
            session_id=data.session_id,
            username=data.username,
            user_lang=data.user_lang,
            context=data.context,
        )
        logger.info(f"Chat response sent for session={data.session_id}")
        return response
    except Exception as e:
        logger.exception(f"Internal server error for session={data.session_id}: {e}")
        return JSONResponse(content={"reply": "Sorry! Internal server error. Please try later", "mode": "bot"}, status_code=500)
