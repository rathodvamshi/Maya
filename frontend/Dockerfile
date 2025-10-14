# Dockerfile for the frontend React application

# Use an official Node.js LTS runtime as a parent image (React Router requires >=20)
FROM node:20

# Set the working directory in the container
WORKDIR /app

# Copy dependency manifests (supports both with and without lockfile)
COPY package*.json ./

# Install dependencies
RUN npm install

# Copy the rest of the frontend application code
COPY . /app

# Expose the port the app runs on
EXPOSE 3000

# Command to run the application
CMD ["npm", "start"]
