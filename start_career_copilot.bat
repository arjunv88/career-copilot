@echo off

title Career Copilot

cd /d "C:\Users\Arjun Viswanathan\OneDrive\Documents\career-copilot"

echo ============================================
echo          CAREER COPILOT STARTING
echo ============================================
echo.

echo Activating Python environment...
call .venv\Scripts\activate.bat

echo.
echo Starting Streamlit...
echo.

python -m streamlit run app.py

pause