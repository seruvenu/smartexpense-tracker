# SmartExpense - Personal Expense Tracker with Budget Alerts

Django + SQLite + Bootstrap 5. SVCET Hackathon (LEARNSQUARE).

## Run it
```bash
python -m venv venv
venv\Scripts\activate          # Windows  (Mac/Linux: source venv/bin/activate)
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_data     # optional demo data (user: demo / password123)
python manage.py runserver
```
Open http://127.0.0.1:8080  (default port is set by `DEFAULT_PORT` in `manage.py`; or run `python manage.py runserver 9000`)

## Tests
```bash
python manage.py test
```

## Features
- Register / log in / log out; every record is private to its owner
- Category CRUD, monthly budget per category, expense logging (`POST /expenses/create/`)
- Dashboard: spent / budget / left, overall gauge, categories sorted by urgency, spending chart, month-end forecast
- Alerts: normal below 80%, warning from 80%, danger from 100% (one shared function: `tracker/alerts.py`)
- Notification bell in the navbar lists every category in warning or danger
- Currency: set `CURRENCY_SYMBOL` in `config/settings.py` (default ₹)
- Themes: Standard, Light, Dark (saved in the browser)

## Forgot password
Log in page -> "Forgot password?". The reset email is printed in the `runserver` terminal (console mailer).

## Production settings
`DJANGO_DEBUG=0`, `DJANGO_SECRET_KEY=<long random value>`, `DJANGO_ALLOWED_HOSTS=your.domain` (enables secure cookies and HTTPS redirect).
