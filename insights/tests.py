import datetime
import json
from types import SimpleNamespace
from unittest import mock

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from attendance.models import Assign_cls, Attendance, AttendanceClass
from cls.models import Class
from course.models import Course
from student.models import student
from users.models import TeacherProfile, User
from .analyst import SCHEMA, analyze, builtin
from .analytics import department_facts, student_facts, teacher_facts, trailing_absences
from .models import AIInsight

DEPT = 'Computer Engineering'


def make_user(email, **flags):
    return User.objects.create_user(email, 'pass-12345-x', first_name=email.split('@')[0].title(),
                                    last_name='Test', department=DEPT, **flags)


class InsightData(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hod = make_user('hod@x.test', is_staff=True, is_hod=True, is_classteacher=True)
        cls.teacher = make_user('teacher@x.test', is_staff=True)
        cls.klass = Class.objects.create(class_name='TE-A', department=DEPT)
        cls.course = Course.objects.create(code='CS1', scheme='R19', name='Networks', dept=DEPT, sem=5)
        cls.assign = Assign_cls.objects.create(cls=cls.klass, course=cls.course,
                                               teacher=TeacherProfile.objects.get(user=cls.teacher))
        cls.good = student.objects.get(user=make_user('good@x.test'))
        cls.poor = student.objects.get(user=make_user('poor@x.test'))
        for s in (cls.good, cls.poor):
            s.cls = cls.klass
            s.save()
        today = timezone.localdate()
        # Ten lectures over five weeks; `poor` attends only the first three.
        for i in range(10):
            day = today - datetime.timedelta(days=35 - i * 3)
            lec = AttendanceClass.objects.create(assign=cls.assign, date=day, period='09:00 - 10:00', status=1)
            Attendance.objects.create(course=cls.course, student=cls.good, date=day, attendanceclass=lec, status=True)
            Attendance.objects.create(course=cls.course, student=cls.poor, date=day, attendanceclass=lec, status=i < 3)
        AttendanceClass.objects.create(assign=cls.assign, date=today, period='10:00 - 11:00', status=0)


class AnalyticsTests(InsightData):
    def test_student_facts(self):
        facts = student_facts(self.poor)
        self.assertEqual(facts['overall']['percent'], 30)
        self.assertEqual(facts['trailing_absences'], 7)
        self.assertEqual(facts['class_average'], 65)
        self.assertEqual(facts['overall']['needed'], 18)   # (3 + 18) / (10 + 18) = 75%
        self.assertEqual(len(facts['trend']), 8)

    def test_teacher_and_department_facts(self):
        t = teacher_facts(self.teacher)
        course = t['courses'][0]
        self.assertEqual(course['num_below'], 1)
        self.assertEqual(course['streaks'][0]['trailing'], 7)
        self.assertEqual(t['unmarked'], 1)
        d = department_facts(self.hod)
        self.assertEqual(d['at_risk']['count'], 1)
        self.assertEqual(d['classes'][0]['num_below'], 1)
        json.dumps(d, default=str)   # facts must be serialisable for the AI prompt

    def test_trailing_absences(self):
        rows = [SimpleNamespace(present=p, date=datetime.date(2026, 1, i + 1), start='09:00', lecture=i)
                for i, p in enumerate([True, False, True, False, False])]
        self.assertEqual(trailing_absences(rows), 2)


class BuiltinAnalystTests(InsightData):
    def test_each_audience_reads_well(self):
        poor = builtin('student', student_facts(self.poor))
        self.assertIn('serious risk', poor['headline'])
        self.assertTrue(any('in a row' in i['title'] for i in poor['insights']))
        staff = builtin('staff_student', student_facts(self.poor))
        self.assertIn('Poor', staff['summary'])
        self.assertNotIn('You ', staff['summary'])
        teacher = builtin('teacher', teacher_facts(self.teacher))
        self.assertIn('follow-up', teacher['headline'])
        dept = builtin('department', department_facts(self.hod))
        self.assertIn('below 75%', dept['headline'])
        for result in (poor, staff, teacher, dept):
            self.assertEqual(result['source'], 'builtin')
            self.assertTrue(all(i['tone'] in ('positive', 'neutral', 'warning', 'critical')
                                for i in result['insights']))

    def test_pages(self):
        self.client.force_login(self.hod)
        r = self.client.get(reverse('insights'))
        self.assertContains(r, 'AI analysis')
        self.assertContains(r, 'built-in analyst')
        self.assertEqual(self.client.get(reverse('insights') + '?view=teaching').status_code, 200)
        r = self.client.get(reverse('insights-analysis') + '?student=%d' % self.poor.id)
        self.assertContains(r, 'serious risk')
        self.client.force_login(self.poor.user)
        self.assertContains(self.client.get(reverse('insights')), 'How your attendance is going')
        self.assertEqual(self.client.get(reverse('insights') + '?view=department').status_code, 200)  # falls back
        self.assertEqual(self.client.get(reverse('insights-analysis') + '?view=department').status_code, 403)
        self.assertEqual(self.client.get(reverse('insights-analysis') + '?student=%d' % self.good.id).status_code, 403)


def fake_response(payload, stop_reason='end_turn'):
    block = SimpleNamespace(type='text', text=json.dumps(payload))
    return SimpleNamespace(content=[block], stop_reason=stop_reason, _request_id='req_test')


@override_settings(AI_TOKEN='test-token', AI_MODEL='claude-opus-5-5')
class ClaudeAnalystTests(InsightData):
    payload = {'headline': 'From Claude', 'summary': 'S', 'insights': [], 'actions': []}

    def test_request_shape_and_cache(self):
        with mock.patch('anthropic.Anthropic') as client_cls:
            create = client_cls.return_value.beta.messages.create
            create.return_value = fake_response(self.payload)
            facts = teacher_facts(self.teacher)
            first = analyze('teacher', facts, self.teacher)
            second = analyze('teacher', facts, self.teacher)
        self.assertEqual(first['headline'], 'From Claude')
        self.assertEqual(first['source'], 'claude')
        self.assertEqual(second['headline'], 'From Claude')
        self.assertEqual(create.call_count, 1)   # cached while the facts are unchanged
        kwargs = create.call_args.kwargs
        self.assertEqual(kwargs['model'], 'claude-opus-5-5')
        self.assertEqual(kwargs['output_config']['format'], {'type': 'json_schema', 'schema': SCHEMA})
        self.assertEqual(kwargs['fallbacks'], 'default')
        self.assertIn('server-side-fallback-2026-07-01', kwargs['betas'])
        self.assertEqual(AIInsight.objects.count(), 1)

    def test_falls_back_to_builtin_on_refusal(self):
        with mock.patch('anthropic.Anthropic') as client_cls:
            client_cls.return_value.beta.messages.create.return_value = fake_response({}, 'refusal')
            result = analyze('teacher', teacher_facts(self.teacher), self.teacher)
        self.assertEqual(result['source'], 'builtin')
        self.assertIn('declined', result['notice'])
