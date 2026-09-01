FROM python:3.12-slim
WORKDIR /app
COPY apps/api/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt
COPY apps/api /app
ENV DATA_DIR=/data PORT=4108
EXPOSE 4108
VOLUME ["/data"]
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "4108"]
