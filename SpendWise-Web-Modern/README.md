# SpendWise Modern Web Application

Python Flask + MySQL web application for personal expense management.

## Features
- Modern colorful responsive UI
- Login and registration
- Password hashing
- Dashboard with income, expenses and balance
- Chart.js monthly and category charts
- Transaction CRUD
- Category CRUD
- Search transactions
- MySQL via WampServer/phpMyAdmin
- Parameterized SQL queries

## Run locally
1. Start WampServer and MySQL.
2. Open phpMyAdmin at `http://localhost/phpmyadmin` and import `database/spendwise.sql`.
3. Create and activate a virtual environment:
   `python -m venv .venv`
   `.venv\\Scripts\\Activate.ps1`
4. Install packages: `pip install -r requirements.txt`
5. Copy `.env.example` to `.env` and set your MySQL password if required.
6. Run: `python app.py`
7. Open `http://127.0.0.1:5000`

Apache is not required by Flask; WampServer is being used here for its local MySQL server and phpMyAdmin.
