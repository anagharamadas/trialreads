# TrialReads Backend

FastAPI-based REST API for TrialReads application.

## Overview

The backend handles:
- **Book Summarization**: Integration with OpenAI for chapter summaries
- **Library Management**: CRUD operations for the book library (SQLite/PostgreSQL)
- **Text-to-SQL**: Natural language queries converted to SQL via LlamaIndex
- **Recommendations**: LLM-powered book recommendations with Amazon links
- **ReAct Agent**: Multi-tool LLM orchestration for intelligent routing

## Architecture

```
app/
├── main.py              # FastAPI app initialization
├── routes/
│   ├── books.py         # Book summary endpoints
│   ├── library.py       # Library CRUD endpoints
│   └── chat.py          # Chat/agent endpoints
├── services/
│   ├── summarizer.py    # Book summarization logic
│   ├── library_manager.py # Library queries (text-to-SQL)
│   └── recommendations.py # Recommendation engine
├── models/
│   ├── book.py          # Pydantic models
│   └── responses.py     # Response schemas
├── db/
│   ├── database.py      # Database connection & ORM setup
│   └── models.py        # SQLAlchemy models
└── config.py            # Configuration & environment variables
```

## Setup

1. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Create .env file**:
   ```bash
   cp .env.example .env
   # Fill in OPENAI_API_KEY
   ```

3. **Initialize database** (if needed):
   ```bash
   python -m app.db.init_db
   ```

4. **Run the server**:
   ```bash
   uvicorn app.main:app --reload
   ```

   API will be available at `http://localhost:8000`

## API Endpoints

### Books
- `POST /api/books/summary` — Get book summary
- `GET /api/books/summary/{book_id}` — Retrieve stored summary

### Library
- `GET /api/library` — List all books
- `POST /api/library` — Add a book
- `PUT /api/library/{book_id}` — Update a book
- `DELETE /api/library/{book_id}` — Delete a book
- `POST /api/library/query` — Natural language library query

### Chat
- `POST /api/chat` — Send a message to the ReAct agent
- `GET /api/chat/history` — Get chat history

### Recommendations
- `POST /api/recommendations` — Get recommendations for a book

## Environment Variables

```env
# OpenAI
OPENAI_API_KEY=sk-...

# Database
DATABASE_URL=sqlite:///./trialreads.db
# Or for PostgreSQL: postgresql://user:password@localhost/trialreads

# Server
DEBUG=False
PORT=8000
HOST=0.0.0.0

# CORS (for frontend)
CORS_ORIGINS=["http://localhost:3000"]
```

## Testing

```bash
pytest
pytest -v  # verbose
pytest --cov  # with coverage
```

## Development

### Hot Reload
```bash
uvicorn app.main:app --reload --port 8000
```

### Database Migrations (if using SQLAlchemy)
```bash
# Create migration
alembic revision --autogenerate -m "Initial migration"

# Apply migration
alembic upgrade head
```

## Deployment

For production:
1. Use a production ASGI server (Gunicorn + Uvicorn)
2. Set `DEBUG=False`
3. Use PostgreSQL instead of SQLite
4. Set up proper CORS origins
5. Use environment-specific config files

Example production command:
```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker
```

## Documentation

- API docs available at `http://localhost:8000/docs` (Swagger UI)
- Alternative docs at `http://localhost:8000/redoc` (ReDoc)

## Contributing

- Follow PEP 8 / Black formatting
- Add tests for new endpoints
- Update README for significant changes
- Use type hints throughout
