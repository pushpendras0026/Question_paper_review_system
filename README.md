# Question Paper Review System

A Django-based web application where faculty upload checked answer scripts and students can raise queries on their evaluated answers. Supports four user roles: **Admin**, **Professor**, **Student**, and **TA**.

---

## Prerequisites

Make sure the following are installed and running before you start:

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.10+ | Tested on 3.13.1 |
| XAMPP | 3.3.0+ | Apache + MySQL must be running |
| MySQL (XAMPP) | 10.4+ | Runs on port `3306` |

---

## Setup (First Time Only)

### 1. Start XAMPP

Open **XAMPP Control Panel** and click **Start** for both:
- **Apache**
- **MySQL**

---

### 2. Create the Database

Open a terminal (PowerShell or CMD) and run:

```powershell
C:\xampp\mysql\bin\mysql.exe -u root -e "CREATE DATABASE IF NOT EXISTS question_paper_review;"
```

---

### 3. Clone / Navigate to the Project

```powershell
cd C:\Users\Lenovo\Downloads\Question-Paper-Review-System\Question-Paper-Review-System
```

---

### 4. Create & Activate Virtual Environment

```powershell
python -m venv venv
.\venv\Scripts\activate
```

You should see `(venv)` in your prompt.

---

### 5. Install Dependencies

```powershell
pip install -r requirements.txt
```

> **Note:** This installs Django 4.2.16 (compatible with XAMPP's MariaDB 10.4) and `pymysql` for database connectivity. No C++ build tools required.

---

### 6. Apply Database Migrations

```powershell
python manage.py makemigrations
python manage.py migrate
```

---

### 7. Create Test Users (Optional — already seeded)

To create the four test accounts manually, run:

```powershell
python manage.py shell -c "
from core.models import User

def create(username, email, role, password='Admin@1234'):
    if not User.objects.filter(username=username).exists():
        u = User.objects.create_user(username=username, email=email, password=password)
        u.role = role
        u.save()
        print(f'Created {role}: {username}')

create('admin1',   'admin@test.com',   'admin')
create('prof1',    'prof@test.com',    'professor')
create('student1', 'student@test.com', 'student')
create('ta1',      'ta@test.com',      'ta')
"
```

---

## Running the Server

Every time you want to run the project:

### Step 1 — Start XAMPP (Apache + MySQL)
Open XAMPP Control Panel → Start **Apache** and **MySQL**.

### Step 2 — Activate the virtual environment

```powershell
cd C:\Users\Lenovo\Downloads\Question-Paper-Review-System\Question-Paper-Review-System
.\venv\Scripts\activate
```

### Step 3 — Start the Django server

```powershell
python manage.py runserver
```

### Step 4 — Open in browser

```
http://127.0.0.1:8000/
```

---

## Test Credentials

All test accounts use the password: **`Admin@1234`**

| Username | Role | Login Redirect |
|---|---|---|
| `admin1` | Admin | Admin dashboard |
| `prof1` | Professor | Professor dashboard |
| `student1` | Student | Student dashboard |
| `ta1` | TA | TA dashboard |

---

## Project Structure

```
Question-Paper-Review-System/
├── QuestionReviewSystem/       # Django project settings & URLs
│   ├── settings.py             # Database, apps, middleware config
│   ├── urls.py                 # Root URL config
│   ├── __init__.py             # pymysql patch (MySQL driver)
│   └── wsgi.py
├── core/                       # Main application
│   ├── models.py               # User, Course, Exam, Marks, Queries, TA models
│   ├── views.py                # All role-based views
│   ├── urls.py                 # App-level URL routes
│   ├── forms.py                # Django forms
│   ├── templates/              # HTML templates
│   └── migrations/             # Auto-generated DB migrations
├── static/                     # CSS / JS / images
├── media/                      # Uploaded answer scripts (at runtime)
├── manage.py
└── requirements.txt
```

---

## Database Configuration

The project connects to XAMPP's MySQL with these defaults (see `settings.py`):

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'question_paper_review',
        'USER': 'root',
        'PASSWORD': '',        # default XAMPP root has no password
        'HOST': '127.0.0.1',
        'PORT': '3306',
    }
}
```

If you have set a MySQL root password in XAMPP, update `PASSWORD` accordingly.

---

## Common Issues

| Error | Fix |
|---|---|
| `Can't connect to MySQL server` | Make sure MySQL is running in XAMPP |
| `Unknown database 'question_paper_review'` | Run the `CREATE DATABASE` command in Step 2 |
| `No module named 'pymysql'` | Run `pip install pymysql` inside the activated venv |
| `venv\Scripts\activate` not recognized | Make sure you're in PowerShell and use `.\venv\Scripts\activate` |
| Port 8000 in use | Run `python manage.py runserver 8080` and open `http://127.0.0.1:8080/` |
