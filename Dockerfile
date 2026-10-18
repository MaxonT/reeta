# One image for Railway (or any container host): builds the frontend, runs the API and serves both.
FROM node:20-slim AS frontend
WORKDIR /build
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend/ backend/
COPY content/ content/
COPY --from=frontend /build/dist frontend/dist
WORKDIR /app/backend
# unpack the Oracle wallet from env vars, then start the server on Railway's $PORT
CMD ["sh", "-c", "python unpack_secrets.py && uvicorn app.prod:root --host 0.0.0.0 --port ${PORT:-8000}"]
