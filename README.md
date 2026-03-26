# Placement Portal Application

A comprehensive web application for managing campus recruitment activities, built with Flask, SQLite, and Bootstrap.

## Features

### Admin (Institute Placement Cell)
- Approve/reject company registrations
- Approve/reject placement drives
- View and manage all students, companies, and placement drives
- Search students by name, ID, or contact information
- Blacklist/deactivate student and company accounts
- View all applications and placement statistics

### Company
- Register and create company profile
- Login only after admin approval
- Create placement drives (job postings)
- View student applications for their drives
- Shortlist students and update application status
- Edit, delete, or close placement drives

### Student
- Register, login, and update profile
- View approved placement drives
- Apply for placement drives
- View application status and placement history
- Upload resume

## Installation

1. Install Python dependencies:
```bash
pip install -r requirements.txt
```

2. Run the application:
```bash
python app.py
```

3. The application will create the database automatically on first run.

4. Access the application at `http://localhost:5000`

## Default Admin Credentials

- Username: `admin`
- Password: `admin123`

## Database

The application uses SQLite database (`placement_portal.db`) which is created automatically when you run the application for the first time.

## Project Structure

```
MAD1_project/
├── app.py                 # Main Flask application
├── requirements.txt       # Python dependencies
├── placement_portal.db    # SQLite database (created automatically)
├── templates/
│   ├── base.html         # Base template
│   ├── index.html        # Home page
│   ├── login.html        # Login page
│   ├── register_company.html
│   ├── register_student.html
│   ├── admin/
│   │   ├── dashboard.html
│   │   ├── companies.html
│   │   ├── students.html
│   │   ├── drives.html
│   │   └── applications.html
│   ├── company/
│   │   ├── dashboard.html
│   │   ├── create_drive.html
│   │   ├── edit_drive.html
│   │   └── applications.html
│   └── student/
│       ├── dashboard.html
│       ├── profile.html
│       └── applications.html
└── static/
    ├── css/
    │   └── style.css
    └── uploads/
        └── resumes/
```

## Key Features

- Role-based authentication and authorization
- Company approval workflow
- Placement drive approval workflow
- Duplicate application prevention
- Resume upload functionality
- Search functionality for admin
- Responsive Bootstrap UI
- Session management

## Usage

1. **Admin Login**: Use default credentials to login as admin
2. **Company Registration**: Companies can register and wait for admin approval
3. **Student Registration**: Students can register and immediately start using the system
4. **Create Drives**: Approved companies can create placement drives
5. **Apply**: Students can apply for approved placement drives
6. **Manage**: Companies can manage applications and update status

## Notes

- All database tables are created programmatically
- No manual database setup required
- Resume uploads are stored in `static/uploads/resumes/`
- Maximum file size for resumes: 5MB
- Supported resume formats: PDF, DOC, DOCX


