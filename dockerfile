FROM python:3.12.4-slim-bookworm

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY openai_descriptions_webhook.py .
RUN chmod +x openai_descriptions_webhook.py

CMD ["python", "openai_descriptions_webhook.py"]