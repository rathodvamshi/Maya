# Dockerfile for the backend FastAPI application

# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Build metadata (populated by CI)
ARG BUILD_SHA=dev
ARG BUILD_DATE=unknown
ENV BUILD_SHA=${BUILD_SHA} \
	BUILD_DATE=${BUILD_DATE}

# Set the working directory in the container
WORKDIR /app

# Copy the requirements file and install dependencies
COPY ./backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the backend application code
COPY ./backend /app

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
