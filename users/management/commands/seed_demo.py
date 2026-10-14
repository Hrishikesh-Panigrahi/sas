"""Fill a local SQLite database with demo data to try the app.

    python manage.py migrate
    python manage.py seed_demo

Every demo account uses DEMO_PASSWORD below. Refuses to run against any
database other than SQLite so it can't touch a real deployment.
"""
import datetime
import random

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from attendance.models import Assign_cls, Attendance, AttendanceClass
from cls.models import Class
from course.models import Course
from student.models import student
from timetable.models import TimeTable
from users.models import TeacherProfile, User

DEMO_PASSWORD = 'sas-demo-2026'
DEPT = 'Computer Engineering'

TEACHERS = [
    # email, first, last, hod, class teacher
    ('hod@sas.test', 'Anita', 'Deshpande', True, True),
    ('rahul@sas.test', 'Rahul', 'Kulkarni', False, True),
    ('meera@sas.test', 'Meera', 'Iyer', False, False),
    ('sanjay@sas.test', 'Sanjay', 'Patil', False, False),
]
COURSES = [
    ('CSC501', 'Theoretical Computer Science', 'meera@sas.test'),
    ('CSC502', 'Software Engineering', 'rahul@sas.test'),
    ('CSC503', 'Computer Networks', 'sanjay@sas.test'),
    ('CSC504', 'Data Warehousing and Mining', 'hod@sas.test'),
    ('CSL501', 'Software Engineering Lab', 'rahul@sas.test'),
]
STUDENTS = [
    'Aarav Shah', 'Diya Nair', 'Ishaan Joshi', 'Kavya Reddy', 'Arjun Mehta', 'Ananya Rao',
    'Vihaan Gupta', 'Saanvi Kapoor', 'Reyansh Pillai', 'Myra Singh', 'Kabir Bhat', 'Anika Das',
]
# day -> [(start, end, course code, type)]
TIMETABLE = {
    'Monday': [('09:00', '10:00', 'CSC501', 'Lecture'), ('10:00', '11:00', 'CSC502', 'Lecture'),
               ('11:15', '13:15', 'CSL501', 'Lab')],
    'Tuesday': [('09:00', '10:00', 'CSC503', 'Lecture'), ('10:00', '11:00', 'CSC504', 'Lecture'),
                ('14:00', '15:00', 'CSC501', 'Lecture')],
    'Wednesday': [('09:00', '10:00', 'CSC502', 'Lecture'), ('10:00', '11:00', 'CSC503', 'Lecture'),
                  ('14:00', '15:00', 'CSC504', 'Lecture')],
    'Thursday': [('09:00', '10:00', 'CSC501', 'Lecture'), ('11:15', '13:15', 'CSL501', 'Lab')],
    'Friday': [('09:00', '10:00', 'CSC504', 'Lecture'), ('10:00', '11:00', 'CSC503', 'Lecture'),
               ('14:00', '15:00', 'CSC502', 'Lecture')],
}


class Command(BaseCommand):
    help = 'Create demo users, a class, a timetable and two weeks of attendance (SQLite only).'

    def handle(self, *args, **options):
        if settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
            raise CommandError('seed_demo only runs against the local SQLite database.')
        if User.objects.filter(email='hod@sas.test').exists():
            self.stdout.write('Demo data is already loaded.')
            return
        with transaction.atomic():
            self._seed()
        self.stdout.write(self.style.SUCCESS(
            'Demo data created. Sign in as hod@sas.test, rahul@sas.test (teacher) or '
            'aarav.shah@sas.test (student); the password is DEMO_PASSWORD in this file.'))

    def _user(self, email, first, last, **flags):
        user = User.objects.create_user(email, DEMO_PASSWORD, first_name=first, last_name=last,
                                        department=DEPT, **flags)
        return user

    def _seed(self):
        rng = random.Random(7)
        User.objects.create_superuser('admin@sas.test', DEMO_PASSWORD)

        teachers = {}
        for email, first, last, hod, ct in TEACHERS:
            user = self._user(email, first, last, is_staff=True, is_hod=hod, is_classteacher=ct)
            teachers[email] = TeacherProfile.objects.get(user=user)

        courses = {}
        for code, name, _ in COURSES:
            courses[code] = Course.objects.create(code=code, name=name, scheme='R2019', dept=DEPT,
                                                  sem=5, is_elective=False)
        Course.objects.create(code='CSDLO5011', name='Probabilistic Graphical Models', scheme='R2019',
                              dept=DEPT, sem=5, is_elective=True)
        Course.objects.create(code='CSC601', name='System Programming and Compiler Construction',
                              scheme='R2019', dept=DEPT, sem=6)

        cls = Class.objects.create(class_name='TE COMPS A', department=DEPT,
                                   class_teacher=teachers['rahul@sas.test'])
        Class.objects.create(class_name='TE COMPS B', department=DEPT)

        assigns = {}
        for code, _, teacher_email in COURSES:
            assigns[code] = Assign_cls.objects.create(cls=cls, course=courses[code],
                                                      teacher=teachers[teacher_email])

        students = []
        for roll, name in enumerate(STUDENTS, start=1):
            first, last = name.split()
            user = self._user('%s.%s@sas.test' % (first.lower(), last.lower()), first, last)
            stu = student.objects.get(user=user)
            stu.roll_no, stu.cls = roll, cls
            stu.save()
            stu.course.add(*courses.values())
            students.append(stu)
        self._user('neha.kale@sas.test', 'Neha', 'Kale')  # registered, not yet in a class

        for day, slots in TIMETABLE.items():
            for start, end, code, kind in slots:
                TimeTable.objects.create(cls=cls, course=courses[code], lec_type=kind, batch='All',
                                         day=day, start_time=start, end_time=end)

        # Two weeks of marked lectures before today. A couple of students skip a lot.
        today = timezone.localdate()
        habits = {stu.id: 0.55 if i in (2, 7) else 0.92 for i, stu in enumerate(students)}
        for offset in range(14, 0, -1):
            date = today - datetime.timedelta(days=offset)
            for start, end, code, _ in TIMETABLE.get(date.strftime('%A'), []):
                lecture = AttendanceClass.objects.create(
                    assign=assigns[code], date=date, day=date.strftime('%A'),
                    period='%s - %s' % (start, end), status=1)
                Attendance.objects.bulk_create(
                    Attendance(course=courses[code], student=stu, date=date, attendanceclass=lecture,
                               status=rng.random() < habits[stu.id])
                    for stu in students)
        # One lecture created yesterday but never marked, to show the reminder.
        AttendanceClass.objects.create(assign=assigns['CSC502'], date=today - datetime.timedelta(days=1),
                                       day=(today - datetime.timedelta(days=1)).strftime('%A'),
                                       period='16:00 - 17:00')
