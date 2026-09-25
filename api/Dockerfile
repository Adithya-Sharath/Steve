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
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
