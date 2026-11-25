FROM python:3.12-slim

# Não roda como root dentro do contêiner
RUN useradd --create-home --uid 10001 gateway

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

USER gateway
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
# O gateway é o único serviço com porta publicada (veja o docker-compose.yml).
# Sem --forwarded-allow-ips: ele não confia em X-Forwarded-For vindo de fora.
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
