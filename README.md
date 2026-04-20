# Question Paper Review System

A Django-based web application where faculty upload checked answer scripts and students can raise queries on their evaluated answers. Supports four user roles: **Admin**, **Professor**, **Student**, and **TA**.

---

## Prerequisites

Make sure the following are installed and running before you start:

| Requirement | Notes |
|---|---|
| Python | 3.10+ |
| MySQL / MariaDB | Must be running locally on port 3306 |

---

## Setup (First Time Only)

### 1. Start MySQL Service

Make sure your local MySQL/MariaDB server is running. Depending on your system (Mac/Linux/Windows), you might use Homebrew, Docker, XAMPP, or a native service:

```bash
# Example for Homebrew on Mac:
brew services start mysql
```

### 2. Create the Database

Open a terminal and run the following command to create the required database `question_paper_review`:

```bash
mysql -u root -e "CREATE DATABASE IF NOT EXISTS question_paper_review;"
```

---

### 3. Navigate to the Project

```bash
cd /path/to/Question_paper_review_system
```

---

### 4. Create & Activate a Virtual Environment

```bash
# Create the environment
python -m venv venv

# Activate it (Mac/Linux)
source venv/bin/activate

# Activate it (Windows)
# .\venv\Scripts\activate
```

You should see `(venv)` in your prompt.

---

### 5. Install Dependencies

Install the required minimal Python packages:

```bash
pip install -r requirements.txt
```

---

### 6. Apply Database Migrations

Apply the Django migrations to create the required tables in your database:

```bash
python manage.py makemigrations
python manage.py migrate
```

---

### 7. Create Test Users

To create test accounts easily, you can use our built-in dummy data script (if available). Check if `populate_dummy_data` or `seed_data` exists:

```bash
python manage.py seed_data
# OR
python manage.py populate_dummy_data
```

*(You can also use `python manage.py createsuperuser` to manually create your own superadmin)*

---

## Running the Server

Every time you want to run the project, follow these steps:

### Step 1 — Verify MySQL is running
Ensure your local MySQL service is active.

### Step 2 — Activate the virtual environment

```bash
cd /path/to/Question_paper_review_system
source venv/bin/activate
```

### Step 3 — Start the Django development server

```bash
python manage.py runserver
```

### Step 4 — Open your browser

```
http://127.0.0.1:8000/
```

---

## Test Credentials

By default, test accounts seeded via our management scripts use the password: **`Admin@1234`**

| Username | Role | Login Redirect |
|---|---|---|
| `admin1` | Admin | Admin dashboard |
| `prof1` | Professor | Professor dashboard |
| `student1` | Student | Student dashboard |
| `ta1` | TA | TA dashboard |

---

## Database Configuration

The project connects to MySQL/MariaDB using these default settings found in `QuestionReviewSystem/settings.py`:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'question_paper_review',
        'USER': 'root',
        'PASSWORD': '',        # Update this if your root user has a password!
        'HOST': '127.0.0.1',
        'PORT': '3306',
    }
}
```

If you have set a MySQL root password, you **must** update the `PASSWORD` field in `settings.py` before migrating or running the server.

---

## Common Issues

| Error | Fix |
|---|---|
| `Can't connect to MySQL server` | Make sure your local MySQL service is actually running. |
| `Unknown database 'question_paper_review'` | You forgot to run the `CREATE DATABASE` command in Setup Step 2. |
| `django.db.utils.OperationalError: Access denied for user 'root'@'localhost' (using password: NO)` | Your MySQL root user has a password. Update `settings.py` to include it. |
| `Port 8000 is already in use` | Run the server on a different port: `python manage.py runserver 8080` |
