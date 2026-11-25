FROM python:3.12-slim

# Não roda como root dentro do contêiner. /dados é onde fica o banco deste serviço (volume).
RUN useradd --create-home --uid 10001 servico && mkdir /dados && chown servico /dados

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app

USER servico
ENV DATABASE_URL=sqlite:////dados/notificacoes.db \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1
# Sem EXPOSE e sem porta publicada: este serviço só é alcançado pelo gateway, dentro da rede do Docker.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
