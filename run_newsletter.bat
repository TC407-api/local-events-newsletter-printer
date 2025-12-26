@echo off
cd /d C:\Users\Travi\Projects\local-events-newsletter-printer

echo Loading API keys from Windows environment...
for /f "tokens=*" %%a in ('powershell -Command "[System.Environment]::GetEnvironmentVariable('SERPAPI_KEY', 'User')"') do set SERPAPI_KEY=%%a
for /f "tokens=*" %%a in ('powershell -Command "[System.Environment]::GetEnvironmentVariable('FIRECRAWL_API_KEY', 'User')"') do set FIRECRAWL_API_KEY=%%a

echo API keys loaded
echo.
python generate_newsletter.py
