"""Fill a local SQLite database with realistic demo data.

    python manage.py migrate
    python manage.py seed_demo            # first time
    python manage.py seed_demo --reset    # wipe everything and start again

What you get (dates are relative to today, so the data never goes stale):
- Computer Engineering: HOD, class teachers, subject and lab teachers, one teacher
  who forgets to mark attendance and one with no courses yet.
- Three classes: SE COMPS A and TE COMPS A with timetables built by the generator
  and eight weeks of attendance; TE COMPS B with ad-hoc lectures and no timetable.
- Students with different habits: steady, borderline, chronically absent, slipping
  recently, improving, skipping Fridays, skipping 9 am lectures, on a current absence
  streak, a week of medical leave, a late joiner, and one not in any class yet.
- Information Technology: a second, smaller department to show the data stays separate.

Every demo account uses DEMO_PASSWORD below. Refuses to run against any database
other than SQLite so it can never touch a real deployment.
"""
import datetime
import random

from django.conf import settings
from django.contrib.auth.hashers import make_password
from django.core.management import call_command
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from attendance.models import Assign_cls, Attendance, AttendanceClass
from cls.models import Class
from course.models import Course
from leave.models import LeaveRequest
from leave.services import sync_excuses
from student.models import student
from timetable import generator
from timetable.models import Substitution, TimeTable
from users.models import TeacherProfile, User

DEMO_PASSWORD = 'sas-demo-2026'
CE, IT = 'Computer Engineering', 'Information Technology'
WEEKS = 8

# email, first, last, department, hod, can be class teacher
TEACHERS = [
    ('hod@sas.test', 'Anita', 'Deshpande', CE, True, True),
    ('rahul@sas.test', 'Rahul', 'Kulkarni', CE, False, True),
    ('priya@sas.test', 'Priya', 'Menon', CE, False, True),
    ('neelam@sas.test', 'Neelam', 'Joshi', CE, False, True),
    ('meera@sas.test', 'Meera', 'Iyer', CE, False, False),
    ('sanjay@sas.test', 'Sanjay', 'Patil', CE, False, False),
    ('farhan@sas.test', 'Farhan', 'Shaikh', CE, False, False),
    ('kiran@sas.test', 'Kiran', 'Rao', CE, False, False),
    ('vikram@sas.test', 'Vikram', 'Bhatt', CE, False, False),
    ('hod.it@sas.test', 'Kavita', 'Nair', IT, True, True),
    ('arjun@sas.test', 'Arjun', 'Bose', IT, False, False),
]

# code, name, department, semester, elective
COURSES = [
    ('CSC301', 'Engineering Mathematics III', CE, 3, False),
    ('CSC302', 'Discrete Structures and Graph Theory', CE, 3, False),
    ('CSC303', 'Data Structures', CE, 3, False),
    ('CSC304', 'Digital Logic and Computer Architecture', CE, 3, False),
    ('CSC305', 'Computer Graphics', CE, 3, False),
    ('CSL301', 'Data Structures Lab', CE, 3, False),
    ('CSL302', 'Digital Systems Lab', CE, 3, False),
    ('CSC501', 'Theoretical Computer Science', CE, 5, False),
    ('CSC502', 'Software Engineering', CE, 5, False),
    ('CSC503', 'Computer Networks', CE, 5, False),
    ('CSC504', 'Data Warehousing and Mining', CE, 5, False),
    ('CSDLO5013', 'Advanced Algorithms', CE, 5, True),
    ('CSL501', 'Software Engineering Lab', CE, 5, False),
    ('CSL502', 'Computer Network Lab', CE, 5, False),
    ('CSC601', 'System Programming and Compiler Construction', CE, 6, False),
    ('CSC602', 'Cryptography and System Security', CE, 6, False),
    ('ITC301', 'Data Structures and Analysis', IT, 3, False),
    ('ITC302', 'Database Management Systems', IT, 3, False),
    ('ITC303', 'Principles of Communication', IT, 3, False),
    ('ITL301', 'Data Structures Lab', IT, 3, False),
]

# class, department, class teacher, [(course, teacher)], student habits, timetable?, weeks of history
CLASSES = [
    ('SE COMPS A', CE, 'priya@sas.test',
     [('CSC301', 'meera'), ('CSC302', 'priya'), ('CSC303', 'farhan'), ('CSC304', 'sanjay'),
      ('CSC305', 'neelam'), ('CSL301', 'farhan'), ('CSL302', 'kiran')],
     ['steady'] * 5 + ['good'] * 4 + ['average'] * 3 +
     ['borderline', 'chronic', 'declining', 'friday', 'morning', 'late'], True, WEEKS),
    ('TE COMPS A', CE, 'rahul@sas.test',
     [('CSC501', 'meera'), ('CSC502', 'rahul'), ('CSC503', 'sanjay'), ('CSC504', 'hod'),
      ('CSDLO5013', 'neelam'), ('CSL501', 'rahul'), ('CSL502', 'kiran')],
     ['steady'] * 5 + ['good'] * 4 + ['average'] * 2 +
     ['borderline', 'chronic', 'declining', 'improving', 'friday', 'morning', 'streak', 'medical', 'late'],
     True, WEEKS),
    ('TE COMPS B', CE, 'neelam@sas.test',
     [('CSC501', 'neelam'), ('CSC502', 'rahul'), ('CSC503', 'sanjay'), ('CSC504', 'hod'),
      ('CSL501', 'farhan'), ('CSL502', 'kiran')],
     ['steady'] * 5 + ['good'] * 5 + ['average'] * 3 + ['borderline', 'chronic', 'streak'], False, 3),
    ('SE IT A', IT, 'hod.it@sas.test',
     [('ITC301', 'arjun'), ('ITC302', 'hod.it'), ('ITC303', 'arjun'), ('ITL301', 'arjun')],
     ['steady'] * 4 + ['good'] * 3 + ['average', 'borderline', 'chronic'], True, 4),
]

FIRST = ['Aarav', 'Diya', 'Ishaan', 'Kavya', 'Arjun', 'Ananya', 'Vihaan', 'Saanvi', 'Reyansh', 'Myra',
         'Kabir', 'Anika', 'Advait', 'Ira', 'Rohan', 'Tara', 'Dhruv', 'Meher', 'Aditya', 'Riya',
         'Krish', 'Navya', 'Yash', 'Pari', 'Atharv', 'Siya', 'Om', 'Aditi', 'Parth', 'Nisha',
         'Shaurya', 'Kiara', 'Neil', 'Ahana', 'Vivaan', 'Zoya', 'Aryan', 'Esha', 'Laksh', 'Mira',
         'Rudra', 'Sana', 'Dev', 'Tanvi', 'Harsh', 'Avni', 'Ayaan', 'Prisha', 'Samar', 'Jiya',
         'Veer', 'Ruhi', 'Nikhil', 'Pooja', 'Kunal', 'Sneha', 'Manav', 'Trisha', 'Varun', 'Leela']
LAST = ['Shah', 'Nair', 'Joshi', 'Reddy', 'Mehta', 'Rao', 'Gupta', 'Kapoor', 'Pillai', 'Singh',
        'Bhat', 'Das', 'Kulkarni', 'Iyer', 'Patil', 'Desai', 'Chopra', 'Sawant', 'Gokhale', 'Banerjee',
        'Menon', 'Kamat', 'Pandey', 'Verma', 'Naik', 'Shetty', 'Agarwal', 'Ghosh', 'Jain', 'More']

HABIT = {'steady': .97, 'good': .91, 'average': .83, 'borderline': .75, 'chronic': .52,
         'declining': .94, 'improving': .55, 'friday': .93, 'morning': .93, 'streak': .9,
         'medical': .92, 'late': .94}
# Some courses are simply less popular; labs a little more.
COURSE_MOOD = {'CSC301': -.12, 'CSC503': -.07, 'ITC303': -.08}


class Command(BaseCommand):
    help = 'Create realistic demo data (SQLite only). Use --reset to wipe and recreate it.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Delete all data first.')

    def handle(self, *args, **options):
        if settings.DATABASES['default']['ENGINE'] != 'django.db.backends.sqlite3':
            raise CommandError('seed_demo only runs against the local SQLite database.')
        if options['reset']:
            call_command('flush', interactive=False, verbosity=0)
        elif User.objects.exists():
            raise CommandError('The database already has data. Run with --reset to replace it with demo data.')
        self.rng = random.Random(2026)
        self.today = timezone.localdate()
        with transaction.atomic():
            self._seed()
        self.stdout.write(self.style.SUCCESS('Demo data ready.'))
        for line in self.summary:
            self.stdout.write('  ' + line)
        self.stdout.write('Sign in as hod@sas.test (HOD), rahul@sas.test (class teacher), '
                          'sanjay@sas.test (teacher) or a student such as %s. Every account uses '
                          'DEMO_PASSWORD from users/management/commands/seed_demo.py.' % self.example_student)

    # ------------------------------------------------------------------
    def _user(self, email, first, last, dept, **flags):
        # Hashing once and reusing the hash keeps seeding fast.
        user = User(email=email, first_name=first, last_name=last, department=dept,
                    password=self.password_hash, **flags)
        user.save()
        return user

    def _seed(self):
        self.summary = []
        self.password_hash = make_password(DEMO_PASSWORD)
        User.objects.create_superuser('admin@sas.test', DEMO_PASSWORD)

        teachers = {}
        for email, first, last, dept, hod, ct in TEACHERS:
            user = self._user(email, first, last, dept, is_staff=True, is_hod=hod, is_classteacher=ct)
            teachers[email.split('@')[0]] = TeacherProfile.objects.get(user=user)
        courses = {code: Course.objects.create(code=code, name=name, scheme='R2019', dept=dept, sem=sem,
                                               is_elective=elective)
                   for code, name, dept, sem, elective in COURSES}

        names = [(f, l) for l in LAST for f in FIRST]
        self.rng.shuffle(names)
        firsts = set()
        self.example_student = None

        def next_name():
            # Prefer a first name nobody has yet, so demo students are easy to tell apart.
            for i, (f, l) in enumerate(names):
                if f not in firsts or len(firsts) == len(FIRST):
                    firsts.add(f)
                    return names.pop(i)
            return names.pop()

        self.lecture_count = self.record_count = 0
        self.rosters = {}
        self.teachers = teachers
        for class_name, dept, ct_email, plan, habits, timetabled, weeks in CLASSES:
            cls = Class.objects.create(class_name=class_name, department=dept,
                                       class_teacher=teachers[ct_email.split('@')[0]])
            assigns = {code: Assign_cls.objects.create(cls=cls, course=courses[code], teacher=teachers[t])
                       for code, t in plan}
            roster = []
            for roll, habit in enumerate(habits, start=1):
                first, last = next_name()
                user = self._user('%s.%s@sas.test' % (first.lower(), last.lower()), first, last, dept)
                stu = student.objects.get(user=user)
                stu.roll_no, stu.cls = roll, cls
                stu.batch = 'A' if roll <= (len(habits) + 1) // 2 else 'B'
                stu.save()
                stu.course.add(*[c.id for c in (courses[code] for code, _ in plan)])
                roster.append((stu, habit))
                if habit == 'chronic' and class_name == 'TE COMPS A':
                    self.example_student = user.email
            self.rosters[class_name] = roster

            if timetabled:
                self._timetable(cls, class_name)
                self._history_from_timetable(cls, assigns, roster, weeks)
            else:
                self._adhoc_history(cls, assigns, roster, weeks)
            self.summary.append('%s: %d students, %d courses%s' % (
                class_name, len(roster), len(plan), '' if timetabled else ', no timetable yet'))

        # A registered student who hasn't been placed in a class.
        first, last = next_name()
        self._user('%s.%s@sas.test' % (first.lower(), last.lower()), first, last, CE)
        self._leave()
        self._cover()
        self.summary.append('%d lectures and %d attendance records over %d weeks'
                            % (self.lecture_count, self.record_count, WEEKS))

    def _leave(self):
        """Leave requests in every state, with approved medical leave excusing absences."""
        day = datetime.timedelta(days=1)
        certificate = (b'%PDF-1.4\n1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj 2 0 obj<</Type/Pages/Kids[]/Count 0>>'
                       b'endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n')
        by_habit = {(c, h): s for c, roster in self.rosters.items() for s, h in roster}
        rahul = User.objects.get(email='rahul@sas.test')
        priya = User.objects.get(email='priya@sas.test')
        made = []

        stu = by_habit.get(('TE COMPS A', 'medical'))
        if stu:
            leave = LeaveRequest.objects.create(
                student=stu, kind='medical', start_date=self.today - 27 * day, end_date=self.today - 21 * day,
                reason='Dengue fever; the doctor advised a week of rest. Certificate attached.',
                document=certificate, document_name='medical-certificate.pdf', document_type='application/pdf',
                status='approved', reviewed_by=rahul, reviewed_at=timezone.now() - 20 * day,
                review_note='Get well soon. Please collect the notes from your batchmates.')
            sync_excuses(stu, leave.start_date, leave.end_date)
            made.append('approved')
        stu = by_habit.get(('TE COMPS A', 'good'))
        if stu:
            LeaveRequest.objects.create(
                student=stu, kind='event', start_date=self.today + day, end_date=self.today + 2 * day,
                reason='Representing the college at the inter-university hackathon in Pune.')
            made.append('pending')
        stu = by_habit.get(('TE COMPS A', 'chronic'))
        if stu:
            LeaveRequest.objects.create(
                student=stu, kind='other', start_date=self.today - 9 * day, end_date=self.today - 7 * day,
                reason='Was travelling for a family function.', status='rejected', reviewed_by=rahul,
                reviewed_at=timezone.now() - 5 * day,
                review_note='Leave has to be requested before travelling, not afterwards.')
            made.append('rejected')
        stu = by_habit.get(('SE COMPS A', 'friday'))
        if stu:
            last_friday = self.today - ((self.today.weekday() - 4) % 7 or 7) * day
            LeaveRequest.objects.create(
                student=stu, kind='medical', start_date=last_friday, end_date=last_friday,
                reason='Migraine; attached the clinic slip.', document=certificate,
                document_name='clinic-slip.pdf', document_type='application/pdf')
            made.append('pending')
        self.summary.append('Leave requests: %s' % ', '.join(made))

    def _cover(self):
        """Meera is away today; Vikram covers her first lecture."""
        meera, vikram = self.teachers['meera'], self.teachers['vikram']
        pairs = Assign_cls.objects.filter(teacher=meera).values_list('cls_id', 'course_id')
        slots = [s for s in TimeTable.objects.filter(day=self.today.strftime('%A')).order_by('start_time')
                 if (s.cls_id, s.course_id) in set(pairs)]
        if slots:
            Substitution.objects.create(slot=slots[0], date=self.today, absent_teacher=meera, substitute=vikram,
                                        created_by=User.objects.get(email='hod@sas.test'))
            self.summary.append('Meera Iyer is away today; Vikram Bhatt covers %s at %s'
                                % (slots[0].course.name, slots[0].period))

    def _timetable(self, cls, class_name):
        config = generator.default_config(cls)
        if class_name == 'SE COMPS A':
            # Wednesday afternoon is kept free for sports.
            config['rules']['class_blocked'] = [{'day': 'Wednesday', 'start': '14:00', 'end': '17:00'}]
        if class_name == 'TE COMPS A':
            config['rules']['preferred_time'] = [{'course_id': Course.objects.get(code='CSC503').id,
                                                   'time': 'morning'}]
        config = generator.clean_config(cls, config)
        result = generator.generate(cls, config, seed=7, time_budget=0)
        generator.apply(cls, result['slots'])
        if result['unplaced']:
            self.stdout.write(self.style.WARNING('%s: %d sessions left unplaced'
                                                 % (class_name, len(result['unplaced']))))

    # ------------------------------------------------------------------ attendance
    def _dates(self, weeks):
        monday = self.today - datetime.timedelta(days=self.today.weekday())
        start = monday - datetime.timedelta(weeks=weeks - 1)
        holiday = monday - datetime.timedelta(weeks=3) + datetime.timedelta(days=2)
        day = start
        while day < self.today:
            if day.weekday() < 6 and day != holiday:
                yield day
            day += datetime.timedelta(days=1)

    def _chance(self, habit, day, start_hour, code, kind, joined):
        if day < joined:
            return None
        days_ago = (self.today - day).days
        p = HABIT[habit] + COURSE_MOOD.get(code, 0) + (0.04 if kind == 'Lab' else 0)
        if start_hour < 10:
            p -= 0.03
        if habit == 'declining' and days_ago <= 18:
            p = 0.4
        elif habit == 'improving' and days_ago <= 24:
            p = 0.93
        elif habit == 'friday' and day.weekday() == 4:
            p = 0.3
        elif habit == 'morning' and start_hour < 10:
            p = 0.25
        elif habit == 'medical' and 21 <= days_ago <= 27:
            p = 0
        elif habit == 'streak' and days_ago <= 4:
            p = 0
        return max(0.0, min(1.0, p))

    def _record(self, assign, day, start, end, batch, roster, status=1):
        lecture = AttendanceClass.objects.create(
            assign=assign, date=day, day=day.strftime('%A'), period='%s - %s' % (start, end),
            batch=batch, status=status)
        self.lecture_count += 1
        if not status:
            return
        rows = []
        for stu, habit in roster:
            if batch != 'All' and stu.batch != batch:
                continue
            joined = self.today - datetime.timedelta(days=21) if habit == 'late' else datetime.date.min
            p = self._chance(habit, day, int(start[:2]), assign.course.code,
                             'Lab' if batch != 'All' else 'Lecture', joined)
            if p is None:
                continue
            rows.append(Attendance(course=assign.course, student=stu, date=day, attendanceclass=lecture,
                                   status=self.rng.random() < p))
        Attendance.objects.bulk_create(rows)
        self.record_count += len(rows)

    def _history_from_timetable(self, cls, assigns, roster, weeks):
        by_course = {a.course_id: a for a in assigns.values()}
        slots = list(cls.timetable_set.all())
        forgetful = {a.id for a in assigns.values() if a.teacher.user.email == 'sanjay@sas.test'}
        for day in self._dates(weeks):
            for slot in (s for s in slots if s.day == day.strftime('%A')):
                assign = by_course[slot.course_id]
                recent = (self.today - day).days <= 14
                if assign.id in forgetful and recent and self.rng.random() < 0.4:
                    continue  # never recorded
                status = 0 if assign.id in forgetful and recent and self.rng.random() < 0.15 else 1
                self._record(assign, day, slot.start_time.strftime('%H:%M'), slot.end_time.strftime('%H:%M'),
                             slot.batch, roster, status)
        # The class teacher's most recent lecture was started but never saved.
        latest = AttendanceClass.objects.filter(assign__cls=cls, assign__teacher=cls.class_teacher,
                                                status=1).order_by('-date', '-period').first()
        if latest and cls.class_name == 'TE COMPS A':
            latest.attendance_set.all().delete()
            latest.status = 0
            latest.save()

    def _adhoc_history(self, cls, assigns, roster, weeks):
        """Lectures entered by hand, as a class without a timetable would have."""
        periods = generator.DEFAULT_PERIODS
        for assign in assigns.values():
            lab = generator.is_lab(assign.course)
            for day in self._dates(weeks):
                if day.weekday() > 4 or self.rng.random() > (0.2 if lab else 0.5):
                    continue
                if lab:
                    start, _ = periods[4]
                    end = periods[5][1]
                    for batch in ('A', 'B'):
                        self._record(assign, day, start, end, batch, roster)
                else:
                    start, end = periods[self.rng.randrange(len(periods))]
                    self._record(assign, day, start, end, 'All', roster)
