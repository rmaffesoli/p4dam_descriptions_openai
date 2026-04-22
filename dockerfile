FROM python:3.12.4-slim-bookworm

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install --no-cache-dir -r requirements.txt

COPY openai_descriptions/* /usr/local/bin/
RUN chmod +x /usr/local/bin/openai_descriptions*

COPY openai_descriptions_webhook.py .

CMD ["python", "openai_descriptions_webhook.py"]