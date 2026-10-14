import json

from django.test import TestCase
from django.urls import reverse

from attendance.models import Assign_cls, AttendanceClass
from cls.models import Class
from course.models import Course
from student.models import student
from users.models import TeacherProfile, User
from . import assistant, generator
from .models import TimeTable

DEPT = 'Computer Engineering'


def make_user(email, **flags):
    return User.objects.create_user(email, 'pass-12345-x', first_name=email.split('@')[0].title(),
                                    last_name='Test', department=DEPT, **flags)


class GeneratorTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hod = make_user('hod@x.test', is_staff=True, is_hod=True, is_classteacher=True)
        cls.meera = TeacherProfile.objects.get(user=make_user('meera@x.test', is_staff=True))
        cls.sanjay = TeacherProfile.objects.get(user=make_user('sanjay@x.test', is_staff=True))
        cls.klass = Class.objects.create(class_name='TE-A', department=DEPT)
        cls.other = Class.objects.create(class_name='TE-B', department=DEPT)
        cls.cn = Course.objects.create(code='CSC503', scheme='R19', name='Computer Networks', dept=DEPT, sem=5)
        cls.tcs = Course.objects.create(code='CSC501', scheme='R19', name='Theory', dept=DEPT, sem=5)
        cls.lab = Course.objects.create(code='CSL502', scheme='R19', name='Network Lab', dept=DEPT, sem=5)
        Assign_cls.objects.create(cls=cls.klass, course=cls.cn, teacher=cls.sanjay)
        Assign_cls.objects.create(cls=cls.klass, course=cls.tcs, teacher=cls.meera)
        Assign_cls.objects.create(cls=cls.klass, course=cls.lab, teacher=cls.sanjay)
        # Sanjay already teaches TE-B every morning at 09:00.
        Assign_cls.objects.create(cls=cls.other, course=cls.cn, teacher=cls.sanjay)
        for day in generator.DEFAULT_DAYS:
            TimeTable.objects.create(cls=cls.other, course=cls.cn, lec_type='Lecture', batch='All',
                                     day=day, start_time='09:00', end_time='10:00')

    def config(self):
        return generator.clean_config(self.klass, generator.default_config(self.klass))

    def test_default_config(self):
        rows = {r['code']: r for r in generator.default_config(self.klass)['courses']}
        self.assertEqual((rows['CSC503']['lectures'], rows['CSC503']['labs']), (3, 0))
        self.assertEqual((rows['CSL502']['lectures'], rows['CSL502']['labs'], rows['CSL502']['batches']),
                         (0, 1, ['A', 'B']))

    def test_generate_avoids_other_classes_and_rules(self):
        cfg = self.config()
        cfg['rules']['class_blocked'] = [{'day': 'Wednesday', 'start': '14:00', 'end': '17:00'}]
        result = generator.generate(self.klass, cfg, seed=1, time_budget=0)
        self.assertEqual(result['unplaced'], [])
        self.assertEqual(len(result['slots']), 3 + 3 + 2)
        for s in result['slots']:
            if s['teacher'].startswith('Sanjay'):
                self.assertFalse(s['start'] < '10:00', s)   # never during the TE-B 09:00 lecture
            if s['day'] == 'Wednesday':
                self.assertLess(s['end'], '14:01')
        self.assertTrue(any('other classes' in h for h in result['highlights']))
        self.assertGreater(result['quality'], 0)

    def test_clean_config_rejects_bad_input(self):
        cfg = generator.default_config(self.klass)
        cfg['periods'] = [{'start': '10:00', 'end': '09:00'}]
        with self.assertRaises(generator.ConfigError):
            generator.clean_config(self.klass, cfg)
        cfg = generator.default_config(self.klass)
        cfg['courses'][0]['assign_id'] = 999999   # someone else's course is ignored
        self.assertEqual(len(generator.clean_config(self.klass, cfg)['courses']), 2)

    def test_views_generate_and_apply(self):
        self.client.force_login(self.hod)
        page = self.client.get(reverse('timetable-generator', args=[self.klass.id]))
        self.assertContains(page, 'Timetable generator')
        r = self.client.post(reverse('timetable-generator-run', args=[self.klass.id]),
                             json.dumps({'config': generator.default_config(self.klass), 'seed': 2}),
                             content_type='application/json')
        self.assertEqual(r.status_code, 200)
        slots = r.json()['slots']
        r = self.client.post(reverse('timetable-generator-apply', args=[self.klass.id]), '{}',
                             content_type='application/json')
        self.assertEqual(r.json()['redirect'], reverse('timetable-class', args=[self.klass.id]))
        self.assertEqual(self.klass.timetable_set.count(), len(slots))

    def test_apply_without_generating_and_permissions(self):
        self.client.force_login(self.hod)
        r = self.client.post(reverse('timetable-generator-apply', args=[self.klass.id]), '{}',
                             content_type='application/json')
        self.assertEqual(r.status_code, 400)
        self.client.force_login(self.meera.user)   # a plain teacher
        self.assertEqual(self.client.get(reverse('timetable-generator', args=[self.klass.id])).status_code, 403)

    def test_bad_config_returns_message(self):
        self.client.force_login(self.hod)
        cfg = generator.default_config(self.klass)
        cfg['days'] = []
        r = self.client.post(reverse('timetable-generator-run', args=[self.klass.id]),
                             json.dumps({'config': cfg}), content_type='application/json')
        self.assertEqual(r.status_code, 400)
        self.assertIn('working day', r.json()['error'])


class AssistantTests(TestCase):
    context = {
        'days': ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'],
        'periods': [{'start': s, 'end': e} for s, e in generator.DEFAULT_PERIODS],
        'teachers': [{'id': 1, 'name': 'Meera Iyer'}, {'id': 2, 'name': 'Rahul Kulkarni'}],
        'courses': [{'id': 10, 'name': 'Computer Networks', 'code': 'CSC503'},
                    {'id': 11, 'name': 'Computer Network Lab', 'code': 'CSL502'},
                    {'id': 12, 'name': 'Data Warehousing and Mining', 'code': 'CSC504'}],
    }

    def parse(self, text):
        return assistant.builtin(text, self.context)

    def test_teacher_unavailable(self):
        r = self.parse("Meera can't teach on Friday afternoons")
        self.assertEqual(r['teacher_unavailable'], [{'teacher_id': 1, 'day': 'Friday', 'start': '14:00', 'end': '17:00'}])
        r = self.parse('Rahul is busy after 3pm on Tuesday and Thursday')
        self.assertEqual([b['day'] for b in r['teacher_unavailable']], ['Tuesday', 'Thursday'])
        self.assertEqual(r['teacher_unavailable'][0]['start'], '15:00')

    def test_class_rules_and_preferences(self):
        r = self.parse('Keep Wednesday afternoon free for sports. No more than 5 lectures a day. '
                       'Avoid DWM on Fridays; CN only in the mornings; at most 2 in a row')
        self.assertEqual(r['class_blocked'], [{'day': 'Wednesday', 'start': '14:00', 'end': '17:00'}])
        self.assertEqual(r['max_periods_per_day'], 5)
        self.assertEqual(r['max_consecutive'], 2)
        self.assertEqual(r['avoid_days'], [{'course_id': 12, 'days': ['Friday']}])
        self.assertEqual(r['preferred_time'], [{'course_id': 10, 'time': 'morning'}])   # not the lab
        self.assertEqual(r['unrecognized'], [])

    def test_unrecognised_text_is_reported(self):
        r = self.parse('the moon is made of cheese')
        self.assertEqual(r['unrecognized'], ['the moon is made of cheese'])
        self.assertEqual(r['understood'], [])

    def test_claude_output_is_sanitised(self):
        raw = assistant._empty('claude')
        raw.update(teacher_unavailable=[{'teacher_id': 99, 'day': 'Monday', 'start': '09:00', 'end': '10:00'},
                                        {'teacher_id': 1, 'day': 'Funday', 'start': '09:00', 'end': '10:00'},
                                        {'teacher_id': 2, 'day': 'Monday', 'start': '09:00', 'end': '10:00'}],
                   max_periods_per_day=40, avoid_first_period='maybe')
        clean = assistant._clean(raw, self.context, 'claude')
        self.assertEqual(clean['teacher_unavailable'], [{'teacher_id': 2, 'day': 'Monday', 'start': '09:00', 'end': '10:00'}])
        self.assertEqual(clean['max_periods_per_day'], 0)
        self.assertEqual(clean['avoid_first_period'], 'unchanged')


class LabBatchTests(TestCase):
    def test_batch_lecture_lists_only_that_batch(self):
        hod = make_user('hod@x.test', is_staff=True, is_hod=True)
        klass = Class.objects.create(class_name='TE-A', department=DEPT)
        lab = Course.objects.create(code='CSL502', scheme='R19', name='Network Lab', dept=DEPT, sem=5)
        assign = Assign_cls.objects.create(cls=klass, course=lab, teacher=TeacherProfile.objects.get(user=hod))
        for email, batch in (('a@x.test', 'A'), ('b@x.test', 'B')):
            s = student.objects.get(user=make_user(email))
            s.cls, s.batch = klass, batch
            s.save()
        lecture = AttendanceClass.objects.create(assign=assign, date='2026-01-05', period='14:00 - 16:00', batch='A')
        self.client.force_login(hod)
        r = self.client.get(reverse('attendance', args=[lecture.id]))
        self.assertContains(r, 'a@x.test')
        self.assertNotContains(r, 'b@x.test')


class SeedTests(TestCase):
    def test_seed_demo_builds_every_scenario(self):
        from django.core.management import call_command
        from io import StringIO
        out = StringIO()
        call_command('seed_demo', stdout=out)
        self.assertIn('Demo data ready', out.getvalue())
        self.assertEqual(Class.objects.count(), 4)
        self.assertFalse(Class.objects.get(class_name='TE COMPS B').timetable_set.exists())
        self.assertTrue(Class.objects.get(class_name='SE COMPS A').timetable_set.exists())
        self.assertTrue(AttendanceClass.objects.filter(status=0).exists())
        self.assertTrue(student.objects.filter(cls__isnull=True, user__is_staff=False).exists())
