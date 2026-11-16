FROM python:3.12-slim
RUN useradd --system --uid 10001 --no-create-home app && mkdir /data && chown 10001:10001 /data
WORKDIR /srv
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY static ./static
ARG GIT_COMMIT=dev
ENV GIT_COMMIT=${GIT_COMMIT} PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 SHAPEAI_DADOS=/data HOME=/tmp
USER 10001
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips", "*"]
