# Quick Start Guide

## Installation & Setup

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Run the application:**
   ```bash
   python app.py
   ```

3. **Access the application:**
   - Open your browser and go to: `http://localhost:5000`

## Default Admin Login

- **Username:** `admin`
- **Password:** `admin123`

## Testing the Application

### 1. Admin Login
- Login with admin credentials
- View dashboard with statistics
- Navigate to Companies, Students, Drives, and Applications

### 2. Company Registration
- Click "Register" → "Company"
- Fill in company details
- Submit registration
- Login attempt will show "pending approval" message

### 3. Approve Company (as Admin)
- Login as admin
- Go to "Companies" page
- Find the registered company
- Click "Approve"

### 4. Create Placement Drive (as Company)
- Login as approved company
- Click "Create New Drive"
- Fill in drive details
- Submit (drive will be pending admin approval)

### 5. Approve Drive (as Admin)
- Login as admin
- Go to "Drives" page
- Find the pending drive
- Click "Approve"

### 6. Student Registration
- Click "Register" → "Student"
- Fill in student details
- Submit registration
- Login immediately (no approval needed)

### 7. Apply for Drive (as Student)
- Login as student
- View available placement drives
- Click "Apply" on a drive
- View application status

### 8. Manage Applications (as Company)
- Login as company
- Go to dashboard
- Click "View Applications" on a drive
- Update application status (Shortlisted/Selected/Rejected)

## Key Features Tested

✅ Authentication and role-based access
✅ Company approval workflow
✅ Drive approval workflow
✅ Duplicate application prevention
✅ Search functionality (admin)
✅ Blacklist functionality
✅ Resume upload
✅ Profile management

## Database

The database (`placement_portal.db`) is created automatically on first run. All tables are created programmatically - no manual setup required.

## Troubleshooting

- **Port already in use:** Change the port in `app.py` (last line): `app.run(debug=True, port=5001)`
- **Database errors:** Delete `placement_portal.db` and restart the application
- **Upload errors:** Ensure `static/uploads/resumes/` directory exists


