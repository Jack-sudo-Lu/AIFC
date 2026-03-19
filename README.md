# AIFC — AI Fact Checker

An AI-powered fact-checking system that extracts verifiable claims from text or URLs, retrieves evidence from authoritative sources, and delivers structured verdicts with confidence scores.

## Architecture

- **Backend** — FastAPI + OpenAI + Tavily search + ChromaDB vector store
- **Frontend** — Next.js 14 + React 18 + Tailwind CSS

### Pipeline

Input → Claim Extraction → Query Rewrite → Evidence Retrieval → Rerank → Alignment → Verification → Confidence Scoring → Output

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- OpenAI API key
- Tavily API key

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Fill in your API keys in .env
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

## License

MIT
