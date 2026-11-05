FROM mcr.microsoft.com/playwright/python:v1.49.0-noble

WORKDIR /app

# Install Python requirements
COPY scout_agent/requirements.txt /app/scout_agent/requirements.txt
RUN pip install --no-cache-dir -r /app/scout_agent/requirements.txt

# Copy shared modules and scout_agent code
COPY shared /app/shared
COPY scout_agent /app/scout_agent

ENV PYTHONPATH=/app
EXPOSE 8001

CMD ["uvicorn", "scout_agent.app.main:app", "--host", "0.0.0.0", "--port", "8001"]
