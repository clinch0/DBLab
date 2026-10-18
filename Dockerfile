FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1
RUN pip install --no-cache-dir pytest
WORKDIR /app
COPY minidb.py test_minidb.py ./
WORKDIR /data
CMD ["python", "/app/minidb.py"]