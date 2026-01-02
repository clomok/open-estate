# Stage 1: Runtime
FROM python:3.11-slim

# Create a non-root user for security
RUN groupadd -r estate && useradd -r -g estate estate_user

WORKDIR /app

# install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Change ownership
RUN chown -R estate_user:estate /app

# Switch to non-root user
USER estate_user

# EXPLICITLY set the python path to the current directory
ENV PYTHONPATH=/app

# Expose port
EXPOSE 5000

# Command: List files (for debugging logs) then run Gunicorn
CMD echo "--- Checking for app.py ---" && ls -la && echo "--- Starting Gunicorn ---" && gunicorn -w 2 -b 0.0.0.0:5000 app:app