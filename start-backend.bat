@echo off
echo Loading .env...
for /f "tokens=1,* delims==" %%a in ('findstr /v /b "#" .env') do set "%%a=%%b"

echo Starting Backend (Spring Boot)...
cd backend
call mvnw spring-boot:run
pause
