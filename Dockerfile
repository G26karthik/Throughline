FROM node:22-slim AS frontend-build
WORKDIR /app/src/frontend
COPY src/frontend/package.json src/frontend/package-lock.json ./
RUN npm ci
COPY src/frontend/ ./
RUN npm run build

FROM python:3.13-slim
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir fastapi "uvicorn[standard]" websockets "psycopg[binary]" prometheus-client

COPY src/backend ./src/backend
COPY --from=frontend-build /app/src/frontend/dist ./src/frontend/dist

EXPOSE 8000

CMD ["uvicorn", "src.backend.main:app", "--host", "0.0.0.0", "--port", "8000"]
