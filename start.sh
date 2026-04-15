#!/bin/bash
set -e

cd "$(dirname "$0")"

# Create .env if not present
if [ ! -f .env ]; then
  cp .env.example .env
  echo "⚠️  Created .env from .env.example — please fill in your API keys"
  exit 1
fi

# Create venv if needed
if [ ! -d backend/.venv ]; then
  echo "📦 Creating Python virtual environment…"
  python3 -m venv backend/.venv
fi

source backend/.venv/bin/activate

echo "📦 Installing dependencies…"
pip install -q -r backend/requirements.txt

echo ""
echo "⚖️ Starting Mr. Burns 合规离职顾问"
echo "   http://localhost:8000"
echo ""

cd backend
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
