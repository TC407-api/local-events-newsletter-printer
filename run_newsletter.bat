@echo off
cd /d C:\Users\Travi\Projects\local-events-newsletter-printer
for /f "tokens=*" %%a in ('powershell -Command "[System.Environment]::GetEnvironmentVariable('SERPAPI_KEY', 'User')"') do set SERPAPI_KEY=%%a
echo Key loaded successfully
python generate_newsletter.py
