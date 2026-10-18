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
python manage.py seed_demo    # optional demo data; add --reset to rebuild it
python manage.py runserver
```

Without database settings the app uses a local `db.sqlite3`. To use PostgreSQL, copy `.env.example` to `sas/.env` and fill in the `DATABASE_*` values.

The demo data covers the cases worth trying: two departments, three Computer Engineering classes with eight weeks of history (one without a timetable), lab batches, students who are steady, borderline, chronically absent, slipping, improving, skipping Fridays or 9 am lectures, on an absence streak, on medical leave or late to join, a teacher who forgets to mark attendance, and one with no courses. Demo logins are listed in `users/management/commands/seed_demo.py`.

## AI features

- **Insights** (sidebar) — attendance trends by week, weekday and time of day, plus a written analysis with suggested next steps: for students about themselves, for teachers about their courses, and for HODs and class teachers about the whole department. Staff also see an analysis on each student's page, and a summary card sits on every dashboard.
- **Timetable generator** (a class's timetable page → *Generate timetable*) — set how often each course meets, lab length and batches, the shape of the day and any rules, then generate a clash-free week. It avoids the teachers' lectures in other classes, runs lab batches side by side, spreads courses across the week and explains the result. Rules can be typed in plain English ("Meera can't teach on Friday afternoons", "keep Wednesday after lunch free").

- **Forecasts and early warnings** — every student's attendance projected to the end of the semester (`SEMESTER_END`): who will slip below 75% and when, who can no longer reach it, and how many more lectures each student can afford to miss.
- **Ask SAS** (sidebar) — questions in plain English ("who missed 3+ CN lectures this month?"), answered from read-only data tools scoped to what the person may see.

Both work out of the box with a built-in analyst. Put an Anthropic API key in `AI_TOKEN` (in `sas/.env`) to have Claude write the analyses and read the plain-English rules instead; `AI_MODEL` picks the model (default `claude-opus-5-5`). Claude's analyses are cached until the underlying numbers change.

## More features

- **Live QR check-in** — on any attendance sheet, *Live QR check-in* projects a QR code (and a 6-digit code) that changes every 15 seconds. Students scan it on their own phone; one phone can only check in one student per lecture. *Finish* saves present/absent for everyone. Phones must be able to reach the server, so use the deployed site rather than `localhost`.
- **Swipe and voice roll call** — on the attendance sheet, *Swipe* shows one student at a time (right for present, left for absent); *Voice* reads each name and listens for "present"/"absent" (Chrome, Edge and Safari; needs HTTPS).
- **Leave and medical requests** — students apply (with an optional certificate); class teachers or the HOD approve. Approved leave turns absences into excused absences that don't count against attendance.
- **Defaulter list PDF** — per class or department, plus warning letters for parents (*Defaulter list* in the sidebar).
- **Find cover** — pick a teacher who is away and a date; SAS ranks the free colleagues for each of their lectures and lets the substitute take attendance.
- **Calendar and app** — subscribe to your timetable in Google/Apple Calendar, and install SAS on a phone; attendance saved while offline is sent when the connection returns.

## Tests

```bash
python manage.py test sas insights timetable leave attendance
```

## How the pieces fit

- **Class** — a group of students. Each course the class takes is an assignment (`attendance.Assign_cls`) linking class, course and teacher.
- **Timetable** — weekly slots per class, written by hand or by the generator (`timetable/generator.py` on top of the constraint solver in `timetable/solver.py`). A teacher's dashboard lists today's slots with a one-click *Take attendance*.
- **Lecture** (`AttendanceClass`) — one dated session of an assignment, for the whole class or one lab batch; **Attendance** rows record each student as present or absent.
- **Insights** — `insights/analytics.py` computes the facts, `insights/analyst.py` writes the analysis (built-in or Claude via `sas/ai.py`).
- **Reports** — per class + course, with CSV export; students under the threshold (`ATTENDANCE_THRESHOLD` in `sas/settings.py`) are highlighted.
