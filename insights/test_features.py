"""Forecasts, substitutes and Ask SAS."""
import datetime

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from attendance.models import Assign_cls, Attendance, AttendanceClass
from attendance.stats import lectures_needed
from cls.models import Class
from course.models import Course
from student.models import student
from timetable.models import Substitution, TimeTable
from timetable.substitutes import suggest
from users.models import TeacherProfile, User
from .ask import answer
from .forecast import _project, forecasts, warnings

DEPT = 'Computer Engineering'


def make_user(email, **flags):
    return User.objects.create_user(email, 'pass-12345-x', first_name=email.split('@')[0].title(),
                                    last_name='Test', department=DEPT, **flags)


class ForecastMathTests(TestCase):
    def test_projection(self):
        # 15 of 20 attended (75%), attending half of the 20 left -> 25/40 = 62%.
        f = _project(15, 20, 20, 0.5, 75, 4)
        self.assertEqual((f['current'], f['projected'], f['best'], f['status']), (75, 62, 88, 'slipping'))
        self.assertEqual(f['can_miss'], 5)          # (15 + 20 - 5) / 40 = 75%
        self.assertEqual(f['crosses_in_weeks'], 1)
        self.assertEqual(_project(5, 20, 4, 1.0, 75, 1)['status'], 'lost')   # best (9/24) < 75%
        self.assertEqual(_project(1, 2, 10, 0.2, 75, 2)['status'], 'at_risk')  # too little data to forecast

    def test_lectures_needed_is_exact(self):
        self.assertEqual(lectures_needed(6, 10, 80), 10)    # (6 + 10) / 20 = 80%
        self.assertEqual(lectures_needed(3, 10), 18)
        self.assertEqual(lectures_needed(8, 10), 0)
        self.assertIsNone(lectures_needed(8, 10, 100))


class Fixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hod = make_user('hod@x.test', is_staff=True, is_hod=True, is_classteacher=True)
        cls.meera = TeacherProfile.objects.get(user=make_user('meera@x.test', is_staff=True))
        cls.sanjay = TeacherProfile.objects.get(user=make_user('sanjay@x.test', is_staff=True))
        cls.vikram = TeacherProfile.objects.get(user=make_user('vikram@x.test', is_staff=True))
        cls.klass = Class.objects.create(class_name='TE-A', department=DEPT)
        cls.cn = Course.objects.create(code='CSC503', scheme='R19', name='Computer Networks', dept=DEPT, sem=5)
        cls.assign = Assign_cls.objects.create(cls=cls.klass, course=cls.cn, teacher=cls.sanjay)
        Assign_cls.objects.create(cls=cls.klass, course=Course.objects.create(
            code='CSC501', scheme='R19', name='Theory', dept=DEPT, sem=5), teacher=cls.meera)
        cls.today = timezone.localdate()
        for day in ('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'):
            TimeTable.objects.create(cls=cls.klass, course=cls.cn, lec_type='Lecture', batch='All',
                                     day=day, start_time='09:00', end_time='10:00')
        cls.slipping = student.objects.get(user=make_user('slip@x.test'))
        cls.steady = student.objects.get(user=make_user('steady@x.test'))
        for s in (cls.slipping, cls.steady):
            s.cls = cls.klass
            s.save()
        # 12 lectures over two months: `slipping` attended the first 9 and missed the last 3
        # (75% now, but the recent pace is poor).
        for i in range(12):
            day = cls.today - datetime.timedelta(days=60 - 4 * i)
            lec = AttendanceClass.objects.create(assign=cls.assign, date=day, period='09:00 - 10:00', status=1)
            Attendance.objects.create(course=cls.cn, student=cls.slipping, date=day, attendanceclass=lec,
                                      status=i < 9)
            Attendance.objects.create(course=cls.cn, student=cls.steady, date=day, attendanceclass=lec, status=True)


class ForecastTests(Fixture):
    @override_settings(SEMESTER_END='2099-01-01')
    def test_warnings_find_the_slipping_student(self):
        f = forecasts(student.objects.filter(pk=self.slipping.pk))[self.slipping.pk]
        self.assertGreater(f['courses'][0]['remaining'], 0)
        names = [w['student'].pk for w in warnings(student.objects.all())]
        self.assertIn(self.slipping.pk, names)
        self.assertNotIn(self.steady.pk, names)

    def test_pages_show_forecasts(self):
        self.client.force_login(self.slipping.user)
        self.assertContains(self.client.get(reverse('index')), 'Semester forecast')
        self.client.force_login(self.hod)
        self.assertContains(self.client.get(reverse('index')), 'Early warnings')
        self.assertContains(self.client.get(reverse('insights')), 'Early warnings')


class CoverTests(Fixture):
    def monday(self):
        return self.today + datetime.timedelta(days=(7 - self.today.weekday()) % 7)

    def test_suggest_and_assign(self):
        date = self.monday()
        # Meera teaches at 09:00 elsewhere on Mondays, so only Vikram (and the HOD) are free.
        other = Class.objects.create(class_name='TE-B', department=DEPT)
        th = Course.objects.get(code='CSC501')
        Assign_cls.objects.create(cls=other, course=th, teacher=self.meera)
        TimeTable.objects.create(cls=other, course=th, lec_type='Lecture', batch='All', day='Monday',
                                 start_time='09:00', end_time='10:00')
        lectures = suggest(self.hod, self.sanjay, date)
        free = [o['teacher'] for o in lectures[0]['options']]
        self.assertIn(self.vikram, free)
        self.assertNotIn(self.meera, free)
        self.client.force_login(self.hod)
        self.assertContains(self.client.get(reverse('cover') + '?teacher=%d&date=%s' % (self.sanjay.pk, date)),
                            'Computer Networks')
        self.client.post(reverse('cover-assign'), {'slot': lectures[0]['slot'].pk, 'absent': self.sanjay.pk,
                                                   'date': date.isoformat(), 'substitute': self.vikram.pk})
        self.assertTrue(Substitution.objects.filter(substitute=self.vikram, date=date).exists())

    def test_substitute_can_take_attendance_today(self):
        slot = TimeTable.objects.filter(day=self.today.strftime('%A')).first()
        if slot is None:   # weekend: nothing timetabled today
            return
        Substitution.objects.create(slot=slot, date=self.today, absent_teacher=self.sanjay, substitute=self.vikram)
        self.client.force_login(self.vikram.user)
        self.assertContains(self.client.get(reverse('index')), 'Covering for')
        r = self.client.post(reverse('attendance-start', args=[slot.id]))
        lecture = AttendanceClass.objects.get(date=self.today)
        self.assertRedirects(r, reverse('attendance', args=[lecture.id]))
        self.assertEqual(self.client.get(reverse('attendance', args=[lecture.id])).status_code, 200)


class AskTests(Fixture):
    def test_builtin_answers(self):
        r = answer(self.hod, 'Who missed 2 or more CN lectures this month?')
        self.assertIn('missed 2 or more', r['answer'])
        self.assertEqual(r['tables'][0]['rows'][0][0], self.slipping.user.full_name)
        r = answer(self.hod, 'Who is below 90%?')
        self.assertIn('below 90%', r['answer'])
        r = answer(self.hod, 'Which class has the lowest attendance?')
        self.assertIn('TE-A', r['answer'])

    def test_students_only_see_themselves(self):
        r = answer(self.steady.user, 'Who is below 100%?')
        self.assertIn("You're at", r['answer'])
        self.assertEqual(len(r['tables']), 1)
        self.assertTrue(r['tables'][0]['title'].startswith('Steady'))

    def test_endpoint(self):
        self.client.force_login(self.hod)
        self.assertContains(self.client.get(reverse('ask')), 'What would you like to know?')
        r = self.client.post(reverse('ask'), '{"question": "who is below 90%"}', content_type='application/json')
        self.assertEqual(r.json()['source'], 'builtin')
