# SAS — Student Attendance System

A Django app for colleges to run attendance by department: heads of department set up courses and teachers, class teachers organise classes and students, teachers mark lectures (straight from their timetable), and students see where they stand against the 75% requirement.

## Who can do what

| Role | How to set it | Can |
| --- | --- | --- |
| Student | any non-staff account | See their own attendance per course |
| Teacher | `is_staff` | Take and edit attendance for their courses, view the timetable, classes and students |
| Class teacher | `is_staff` + `is_classteacher` | Everything a teacher can, plus manage classes, students and timetables |
| Head of department | `is_staff` + `is_hod` | Everything above, plus manage courses and teachers, and mark any lecture in the department |
| Superuser | `createsuperuser` | Everything, across departments, plus the Django admin |

Everyone except superusers only sees their own department.

## Running it locally

```bash
python -m venv env
env/Scripts/activate          # macOS/Linux: source env/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_demo    # optional demo data; logins are listed in users/management/commands/seed_demo.py
python manage.py runserver
```

Without database settings the app uses a local `db.sqlite3`. To use PostgreSQL, copy `.env.example` to `sas/.env` and fill in the `DATABASE_*` values.

## Tests

```bash
python manage.py test sas
```

## How the pieces fit

- **Class** — a group of students. Each course the class takes is an assignment (`attendance.Assign_cls`) linking class, course and teacher.
- **Timetable** — weekly slots per class. A teacher's dashboard lists today's slots with a one-click *Take attendance*.
- **Lecture** (`AttendanceClass`) — one dated session of an assignment; **Attendance** rows record each student as present or absent.
- **Reports** — per class + course, with CSV export; students under the threshold (`ATTENDANCE_THRESHOLD` in `sas/settings.py`) are highlighted.
