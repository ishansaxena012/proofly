#!/bin/bash
echo "Loading .env..."
set -a
source .env
set +a

echo "Starting Backend (Spring Boot)..."
cd backend
./mvnw spring-boot:run
