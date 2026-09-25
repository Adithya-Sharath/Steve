# build context = repo root (the API needs engine/ and data/)
FROM python:3.12-slim
WORKDIR /srv
COPY engine ./engine
COPY api ./api
COPY data ./data
COPY eval/results ./eval/results
RUN pip install --no-cache-dir ./engine ./api
ENV SAMJHA_DATA_DIR=/srv/data SAMJHA_EVAL_DIR=/srv/eval/results
WORKDIR /srv/api
# default port; the server binds to $PORT when the platform sets one
EXPOSE 8000
# PaaS hosts (Render, Railway, Fly, Cloud Run...) inject $PORT. Shell form so ${PORT:-8000} is expanded; `exec` keeps
# uvicorn as PID 1 so it receives SIGTERM.
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
