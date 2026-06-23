"""
TrialReads Backend - FastAPI Application

Main entry point for the REST API.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Initialize FastAPI app
app = FastAPI(
    title="TrialReads API",
    description="REST API for book summarization, library management, and recommendations",
    version="0.1.0",
)

# CORS Configuration
CORS_ORIGINS = os.getenv("CORS_ORIGINS", "http://localhost:3000").strip('[]').replace("'", "").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint - health check"""
    return {
        "message": "TrialReads API",
        "status": "running",
        "version": "0.1.0",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "ok"}


@app.get("/api/config")
async def get_config():
    """Get client configuration"""
    return {
        "app_name": os.getenv("NEXT_PUBLIC_APP_NAME", "TrialReads"),
        "debug": os.getenv("DEBUG", "False").lower() == "true",
    }


# TODO: Import and include routers
# from routes import books, library, chat, recommendations
# app.include_router(books.router, prefix="/api/books", tags=["books"])
# app.include_router(library.router, prefix="/api/library", tags=["library"])
# app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
# app.include_router(recommendations.router, prefix="/api/recommendations", tags=["recommendations"])


@app.exception_handler(Exception)
async def general_exception_handler(request, exc):
    """Global exception handler"""
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc)},
    )


if __name__ == "__main__":
    import uvicorn

    debug = os.getenv("DEBUG", "False").lower() == "true"
    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")

    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=debug,
        log_level="info" if not debug else "debug",
    )
