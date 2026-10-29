FROM python:3.13-slim

WORKDIR /app
COPY src/erp_simulator/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY src/erp_simulator/*.py .
CMD ["python", "erp_simulator.py"]
