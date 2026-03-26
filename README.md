# Placement Portal (MAD1_project)

A modern campus recruitment management system built with Flask, SQLite, and Bootstrap.

## 🚀 What this project does
- Multi-role portal: `admin`, `company`, and `student`
- Student profile includes picture, resume and academic data
- Resume required to apply for any placement drive
- Smart eligibility checks (CGPA + course/degree matching)
- Application lifecycle: `applied` → `shortlisted` → `selected`/`rejected`
- Admin and Company can view a student profile (with access control)
- Company checks: only students who applied to the company's drives are visible
- Notifications for eligibility changes and status updates

## 🛠️ Tech stack
- Python + Flask
- SQLite (`placement_portal.db`)
- Jinja2 templating
- Bootstrap 5 UI
- File uploads stored under `static/uploads/resumes/`

## ✅ Setup
1. Create a virtual environment (recommended):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate
   ```
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Run the app:
   ```bash
   python app.py
   ```
4. Visit `http://localhost:5000`

### Default Admin
- username: `admin`
- password: `admin123`

## 📁 Folder structure
```
MAD1_project/
├── .gitignore
├── app.py                      # Main Flask app, routes, logic, DB init
├── requirements.txt
├── README.md
├── QUICKSTART.md
├── static/
│   ├── css/
│   │   └── style.css
│   └── uploads/
│       └── resumes/            # Uploaded resumes and profile pictures
└── templates/
    ├── base.html
    ├── index.html
    ├── login.html
    ├── register_company.html
    ├── register_student.html
    ├── forgot_password.html
    ├── reset_password.html
    ├── verify_otp.html
    ├── admin/
    │   ├── dashboard.html
    │   ├── companies.html
    │   ├── students.html
    │   ├── student_profile.html
    │   ├── drives.html
    │   └── applications.html
    ├── company/
    │   ├── dashboard.html
    │   ├── create_drive.html
    │   ├── edit_drive.html
    │   ├── applications.html
    │   └── student_profile.html
    └── student/
        ├── dashboard.html
        ├── profile.html
        └── applications.html
```

## 🔍 Features list
- Student profile: name, ID, contact, course, year (integer), CGPA, resume + profile picture
- Resume required for applying to a drive
- Drive eligibility enforcement in application logic
- Admin can view/manage all students, companies, drives
- Company can manage their own drives and view applicants
- Shareable student profile link button
- Auto-removal of students from drives when profile becomes ineligible
- Upload validation (`.pdf`, `.doc`, `.docx`, `.png`, `.jpg`, `.jpeg`, `.gif`)

## 📌 Notes
- Database and tables are auto-created at first run
- Email OTP is logged to console when SMTP is not configured
- App includes safe defaults for local development
- Force-pushed to `https://github.com/Viji1596/Placement-Portal`


