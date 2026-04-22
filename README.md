# Question Paper Review System

A Django-based web application for managing academic assessments. Faculty upload checked answer scripts, TAs assist with grading and query resolution, and students can view their marks and raise queries — all within a structured, role-based workflow.

**Supported Roles:** Admin · Professor · TA · Student

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [First-Time Setup](#first-time-setup)
- [Running the Server](#running-the-server)
- [Test Credentials](#test-credentials)
- [Default Passwords for New Users](#default-passwords-for-new-users)
- [Features by Role](#features-by-role)
- [Project Structure](#project-structure)
- [Database Configuration](#database-configuration)
- [CSV Marks Import](#csv-marks-import)
- [Common Issues](#common-issues)

---

## Prerequisites

Ensure the following are installed and running before you begin:

| Requirement     | Version / Notes                              |
|-----------------|----------------------------------------------|
| Python          | 3.10 or higher                               |
| MySQL / MariaDB | Running locally on port `3306`               |
| pip             | Comes with Python                            |
| Git             | For cloning the repository                   |

---

## First-Time Setup

### 1. Start MySQL Service

```bash
# macOS (Homebrew)
brew services start mysql

# Linux (systemd)
sudo systemctl start mysql
```

```powershell
# Windows — run Command Prompt or PowerShell as Administrator
net start MySQL80
# Note: the service name may be "MySQL80", "MySQL", or "MariaDB" depending on your installation.
# You can also start it from: Task Manager → Services, or the MySQL Notifier in your system tray.
```

### 2. Create the Database

```bash
# macOS / Linux
mysql -u root -e "CREATE DATABASE IF NOT EXISTS question_paper_review;"
```

```powershell
# Windows
mysql -u root -e "CREATE DATABASE IF NOT EXISTS question_paper_review;"
```

> If your MySQL root user has a password, add `-p` flag: `mysql -u root -p -e "CREATE DATABASE ..."`

### 3. Clone and Navigate to the Project

```bash
git clone https://github.com/pushpendras0026/Question_paper_review_system.git
cd Question_paper_review_system
```

### 4. Create and Activate a Virtual Environment

```bash
# macOS / Linux
python -m venv venv
source venv/bin/activate
```

```powershell
# Windows (Command Prompt)
python -m venv venv
venv\Scripts\activate.bat

# Windows (PowerShell)
python -m venv venv
venv\Scripts\Activate.ps1
# If you get a permission error in PowerShell, run first:
# Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

You should see `(venv)` in your terminal prompt.

### 5. Install Dependencies

```bash
pip install -r requirements.txt
```

### 6. Apply Database Migrations

```bash
python manage.py makemigrations
python manage.py migrate
```

### 7. Seed Sample Data

Use the built-in management command to populate the database with test users and courses:

```bash
python manage.py seed_data
```

This creates an admin, 3 professors, 5 students, 2 TAs, sample courses, and enrollments.

> Alternatively, create your own superuser: `python manage.py createsuperuser`

---

## Running the Server

After the first-time setup is complete, follow these steps each time:

#### Step 1 — Ensure MySQL is running

```bash
# macOS
brew services start mysql

# Linux
sudo systemctl start mysql
```

```powershell
# Windows (run as Administrator)
net start MySQL80
```

#### Step 2 — Activate the virtual environment

```bash
# macOS / Linux
source venv/bin/activate
```

```powershell
# Windows (Command Prompt)
venv\Scripts\activate.bat

# Windows (PowerShell)
venv\Scripts\Activate.ps1
```

#### Step 3 — Start the development server

```bash
python manage.py runserver
```

#### Step 4 — Open in your browser

```
http://127.0.0.1:8000/
or 
http://localhost:8000/
```

> To run on a different port: `python manage.py runserver 8080`

---

## Test Credentials

Accounts seeded via `python manage.py seed_data` — **all passwords are `pass`**:

| Username   | Role      | Dashboard Redirect    |
|------------|-----------|-----------------------|
| `admin1`   | Admin     | Admin Dashboard       |
| `prof1`    | Professor | Professor Dashboard   |
| `prof2`    | Professor | Professor Dashboard   |
| `prof3`    | Professor | Professor Dashboard   |
| `student1` | Student   | Student Dashboard     |
| `student2` | Student   | Student Dashboard     |
| `ta1`      | TA        | TA Dashboard          |
| `ta2`      | TA        | TA Dashboard          |

---

## Default Passwords for New Users

When the Admin creates a new user from the dashboard, passwords are automatically assigned:

| Role          | Default Password        | Fallback (if ID is blank) |
|---------------|-------------------------|---------------------------|
| **Professor** | Their `faculty_id`      | `password123!`            |
| **Student**   | Their `roll_number`     | `password`                |
| **TA**        | Their `roll_number`     | `password`                |

All users can change their password after login via the **"Change Password"** link in the navigation bar.

---

## Features by Role

### Admin
- Create and manage courses (set professor, semester, department)
- Add faculty (professors), students, and TAs manually
- End/archive courses
- View course grades
- Send grade-pending notifications to professors

### Professor
- View active and completed courses
- Add and edit exams (with configurable weightage, max marks, query windows)
- Add exam sections (for section-wise marking)
- Upload answer scripts per student (PDF, PNG, JPG, WEBP, BMP, GIF, TIFF)
- Enter marks manually or via **CSV upload**
- Approve/reject student enrollment requests
- Approve enrollment requests as a faculty advisor
- Manage TA assignments (upload, query, marks permissions)
- View and respond to student queries
- Assign final grades

### TA
- View assigned courses
- Upload answer scripts (if permitted)
- Update marks (if permitted)
- View and respond to queries (if permitted)
- Upload marks via CSV

### Student
- Browse and request enrollment in courses (filtered by department)
- View exam details and uploaded answer scripts
- View marks (section-wise and total)
- Raise queries on answer scripts within the query window
- View course statistics (mean, median, percentile) for each exam
- View past/completed course records

---

## Project Structure

```
Question_paper_review_system/
├── manage.py
├── requirements.txt
├── QuestionReviewSystem/          # Django project settings & URLs
│   ├── settings.py
│   ├── urls.py
│   └── wsgi.py
└── core/                          # Main application
    ├── models.py                  # User, Course, Exam, Mark, Query, etc.
    ├── views.py                   # All view logic (auth, student, professor, TA, admin)
    ├── forms.py                   # Django forms for each role
    ├── urls.py                    # URL routing
    ├── admin.py                   # Django admin configuration
    ├── management/
    │   └── commands/
    │       └── seed_data.py       # Minimal test data seeder

    └── templates/
        └── core/
            ├── base.html          # Shared layout and navigation
            ├── login.html
            ├── change_password.html
            ├── admin/             # Admin templates
            ├── professor/         # Professor templates
            ├── student/           # Student templates
            └── ta/                # TA templates
```

---

## Database Configuration

The project connects to MySQL via the settings in `QuestionReviewSystem/settings.py`:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'question_paper_review',
        'USER': 'root',
        'PASSWORD': '',        # Set this if your root user has a password
        'HOST': '127.0.0.1',
        'PORT': '3306',
    }
}
```

> Update `PASSWORD` before running migrations if your root user is password-protected.

---

## CSV Marks Import

Both professors and TAs (if permitted) can bulk-import marks via CSV upload.

**Supported CSV formats:**
- With or without a header row — the system auto-detects it.
- Flexible delimiters: `,` `;` `|` `Tab`
- Student can be identified by: roll number, username, or full name (in any order).
- Marks column is identified by headers like: `marks`, `score`, `total`, `totalscore`.

**Example CSV (with header):**

```csv
Roll Number,Name,Marks
220101001,Student1, 78.5
220101002,Student2,91
```

**Rules:**
- Marks must be `≥ 0` and `≤ max_marks` for the exam.
- Rows that cannot be matched to an enrolled student or have invalid marks are **skipped** (a count is reported).
- Existing marks are **updated** (not duplicated).

---

