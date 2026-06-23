# TrialReads — Monorepo

A modern full-stack application for book summarization, library management, and recommendations.

## Stack

- **Backend**: FastAPI (Python) — LLM orchestration, text-to-SQL, book recommendations
- **Frontend**: Next.js (TypeScript/React) — responsive UI, library management, chat interface
- **Database**: SQLite (local) / PostgreSQL (production-ready upgrade path)
- **LLM**: OpenAI `gpt-4o-mini`

## Folder Structure

```
trialreads/
├── backend/          # FastAPI application
│   ├── app/
│   ├── requirements.txt
│   ├── .env.example
│   └── README.md
├── frontend/         # Next.js application
│   ├── app/
│   ├── package.json
│   ├── .env.example
│   └── README.md
└── README.md         # This file
```

## Quick Start

### Prerequisites
- Python 3.12+ (backend)
- Node.js 18+ (frontend)
- OpenAI API key

### Backend Setup
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in OPENAI_API_KEY in .env
uvicorn app.main:app --reload
# API runs on http://localhost:8000
```

### Frontend Setup
```bash
cd frontend
npm install
cp .env.local.example .env.local
# Fill in NEXT_PUBLIC_API_URL=http://localhost:8000
npm run dev
# Frontend runs on http://localhost:3000
```

## Features

- **Book Summarization**: Get chapter-by-chapter summaries of books via LLM
- **Library Management**: CRUD operations for personal book collection
- **Natural Language Q&A**: Ask questions about your library; queries translate to SQL
- **Smart Recommendations**: Get similar book recommendations with purchase links
- **Chat Interface**: Unified conversational interface powered by ReAct agent

## Architecture

- **API-First Design**: Backend exposes REST API; frontend consumes it
- **Separation of Concerns**: UI logic in Next.js, business logic in FastAPI
- **Scalability**: Easy to deploy backend and frontend independently
- **Developer Experience**: Hot reload for both backend (FastAPI) and frontend (Next.js)

## Development

### Backend Development
```bash
cd backend
# Run tests
pytest

# Run with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend Development
```bash
cd frontend
# Run dev server with hot reload
npm run dev

# Build for production
npm run build
npm start
```

## Environment Variables

See `.env.example` files in `backend/` and `frontend/` directories for required variables.

Key variables:
- `OPENAI_API_KEY` — OpenAI API key (backend)
- `NEXT_PUBLIC_API_URL` — Backend API URL (frontend)

## Contributing

Contributions welcome! Please ensure:
- Code follows project style guide
- Tests pass
- Documentation is updated

## License

MIT

---

**Project Status**: Active Development  
**Last Updated**: 2026-06-23
