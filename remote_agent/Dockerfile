FROM python:3.11-slim

WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn docker kubernetes httpx pydantic

COPY remote_agent/ /app/remote_agent/
COPY supervisor/ /app/supervisor/

EXPOSE 8090

CMD ["uvicorn", "remote_agent.app:app", "--host", "0.0.0.0", "--port", "8090"]
