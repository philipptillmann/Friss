FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd --uid 10001 --create-home friss
COPY --chown=10001:10001 app ./app
RUN find /app/app -type d -exec chmod 755 {} + \
    && find /app/app -type f -exec chmod 644 {} +
USER friss
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
