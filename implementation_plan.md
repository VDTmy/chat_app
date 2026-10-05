# Monorepo Chat App Setup Plan

This plan outlines the creation and configuration of the "chat-app" monorepo workspace, including a FastAPI backend (with virtual environment and core libraries), a React + Vite + TypeScript frontend, and a Docker Compose setup for PostgreSQL and Redis.

## User Review Required

> [!IMPORTANT]
> The backend `.env` configuration contains a database URL pointing to `localhost:5432` and a Redis URL pointing to `localhost:6379`. Since only PostgreSQL and Redis are dockerized in the `docker-compose.yml`, the backend runs locally on the host machine and communicates directly with the Docker containers on localhost.

## Open Questions

None at this time. All requirements are clear.

## Proposed Changes

### Root Configurations

#### [NEW] [.gitignore](file:///d:/Đại%20học/Dự%20án/chat-app/.gitignore)
Create a comprehensive root gitignore to exclude python venv, node_modules, build directories, `.env` files, and IDE settings.

#### [NEW] [docker-compose.yml](file:///d:/Đại%20học/Dự%20án/chat-app/docker-compose.yml)
Create docker-compose configuration definition with:
- `postgres` (port 5432, default user/db `postgres`/`chat_db`)
- `redis` (port 6379)

---

### Backend (FastAPI)

#### [NEW] [requirements.txt](file:///d:/Đại%20học/Dự%20án/chat-app/backend/requirements.txt)
Write a requirements list containing the packages to install:
`fastapi`, `uvicorn[standard]`, `sqlalchemy[asyncio]`, `alembic`, `asyncpg`, `pydantic[email]`, `pydantic-settings`, `python-jose[cryptography]`, `passlib[bcrypt]`, `python-multipart`, `redis[asyncio]`, `aiofiles`.

#### [NEW] [.env](file:///d:/Đại%20học/Dự%20án/chat-app/backend/.env)
Define backend environment variables:
- `DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/chat_db`
- `SECRET_KEY` (secure generated hex string)
- `REDIS_URL=redis://localhost:6379/0`
- `ACCESS_TOKEN_EXPIRE_MINUTES=15`
- `REFRESH_TOKEN_EXPIRE_DAYS=7`

#### [NEW] [config.py](file:///d:/Đại%20học/Dự%20án/chat-app/backend/app/core/config.py)
A Pydantic Settings class to load from `.env`.

#### [NEW] [main.py](file:///d:/Đại%20học/Dự%20án/chat-app/backend/main.py)
A basic FastAPI server with CORS middleware allowing all origins for development, reading from config settings, and defining a simple check endpoint.

---

### Frontend (React + Vite)

The frontend boilerplate is already generated and dependencies are defined in `package.json` (`axios`, `zustand`, `react-router-dom`, `tailwindcss`, etc.).
We will run `npm install` inside the `frontend/` directory to ensure all dependencies are resolved and ready.

## Verification Plan

### Automated Tests / Execution Check
1. Start Postgres and Redis using:
   ```bash
   docker-compose up -d
   ```
2. Activate python virtual environment and install dependencies:
   ```bash
   cd backend
   .\venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. Run the backend local server:
   ```bash
   uvicorn main:app --reload
   ```
4. Query the backend health check endpoint `http://127.0.0.1:8000/` using curl/browser.
5. In `frontend/`, run:
   ```bash
   npm install
   npm run dev
   ```
   and check that it launches correctly.
