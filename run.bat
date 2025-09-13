@echo off

:: Check if the virtual environment folder exists
if not exist "venv" (
    echo Creating virtual environment venv...
    python -m venv venv
)

:: Activate the environment and install dependencies, if they don't exist
echo Activating environment and installing dependencies...
call venv\Scripts\activate.bat
pip install PyQt5

:: Run the main Python script
echo Starting the program...
python main.py

echo.
pause