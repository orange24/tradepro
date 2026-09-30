FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY tradepro ./tradepro
ENV TRADEPRO_DB=/app/data/tradepro.db
VOLUME /app/data
EXPOSE 8000
# One worker so the background auto-scan runs once; threads serve concurrent requests.
CMD ["gunicorn", "-w", "1", "--threads", "8", "--timeout", "120", "-b", "0.0.0.0:8000", "tradepro.web.app:create_app()"]
