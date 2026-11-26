FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt requirements-dev.txt ./
RUN pip install --no-cache-dir -r requirements-dev.txt
COPY shared/ shared/
COPY console/ console/
EXPOSE 5001
# PAYLOAD_KEY etc. injected via env_file / secrets at runtime (V9)
CMD ["python", "-m", "console"]
