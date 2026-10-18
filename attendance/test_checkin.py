import json
import time

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from cls.models import Class
from course.models import Course
from student.models import student
from users.models import TeacherProfile, User
from . import checkin
from .models import Assign_cls, Attendance, AttendanceClass, CheckIn, CheckInSession

DEPT = 'Computer Engineering'


def make_user(email, **flags):
    return User.objects.create_user(email, 'pass-12345-x', first_name=email.split('@')[0].title(),
                                    last_name='Test', department=DEPT, **flags)


class CheckInTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher = make_user('teacher@x.test', is_staff=True)
        cls.klass = Class.objects.create(class_name='TE-A', department=DEPT)
        course = Course.objects.create(code='CS1', scheme='R19', name='Networks', dept=DEPT, sem=5)
        cls.assign = Assign_cls.objects.create(cls=cls.klass, course=course,
                                               teacher=TeacherProfile.objects.get(user=cls.teacher))
        cls.a = student.objects.get(user=make_user('a@x.test'))
        cls.b = student.objects.get(user=make_user('b@x.test'))
        cls.outsider = student.objects.get(user=make_user('out@x.test'))
        for s in (cls.a, cls.b):
            s.cls = cls.klass
            s.save()
        cls.lecture = AttendanceClass.objects.create(assign=cls.assign, date=timezone.localdate(), period='09:00 - 10:00')

    def start(self):
        self.client.force_login(self.teacher)
        self.client.post(reverse('checkin-start', args=[self.lecture.id]))
        return CheckInSession.objects.get()

    def scan_and_confirm(self, user, session, device=None):
        self.client.force_login(user)
        if device:
            self.client.cookies[checkin.DEVICE_COOKIE] = device
        token = checkin.url_token(session, checkin.current_window(session))
        page = self.client.get(reverse('checkin-scan', args=[session.id, token]))
        ticket = page.context.get('ticket')
        if not ticket:
            return page
        return self.client.post(reverse('checkin-scan', args=[session.id, token]), {'ticket': ticket})

    def test_projector_state_has_qr_and_code(self):
        session = self.start()
        data = json.loads(self.client.get(reverse('checkin-state', args=[self.lecture.id])).content)
        self.assertIn('<svg', data['svg'])
        self.assertEqual(data['code'], checkin.short_code(session, checkin.current_window(session)))
        self.assertEqual(data['count'], 0)

    def test_check_in_and_finish(self):
        session = self.start()
        r = self.scan_and_confirm(self.a.user, session, device='a' * 32)
        self.assertContains(r, "You&#x27;re checked in")
        self.assertEqual(CheckIn.objects.count(), 1)
        # Same phone can't check in a second student.
        r = self.scan_and_confirm(self.b.user, session, device='a' * 32)
        self.assertContains(r, 'already used to check in')
        # A student outside the class can't check in.
        r = self.scan_and_confirm(self.outsider.user, session, device='c' * 32)
        self.assertContains(r, "not on its list")
        self.client.force_login(self.teacher)
        self.client.post(reverse('checkin-finish', args=[self.lecture.id]), {'action': 'finish'})
        self.lecture.refresh_from_db()
        self.assertTrue(self.lecture.is_marked)
        self.assertEqual(dict(Attendance.objects.values_list('student_id', 'status')), {self.a.id: True, self.b.id: False})

    def test_expired_token_and_code_entry(self):
        session = self.start()
        old = checkin.url_token(session, checkin.current_window(session) - 5)
        self.client.force_login(self.a.user)
        self.assertContains(self.client.get(reverse('checkin-scan', args=[session.id, old])), 'expired')
        code = checkin.short_code(session, checkin.current_window(session))
        r = self.client.post(reverse('checkin-code'), {'code': code})
        self.assertContains(r, "You&#x27;re checked in")
        r = self.client.post(reverse('checkin-code'), {'code': '000000' if code != '000000' else '111111'})
        self.assertContains(r, "doesn&#x27;t match")

    def test_codes_rotate(self):
        session = CheckInSession(secret='s' * 64, window=15)
        now = time.time()
        self.assertNotEqual(checkin.short_code(session, checkin.current_window(session, now)),
                            checkin.short_code(session, checkin.current_window(session, now + 30)))

    def test_only_the_teacher_can_run_it(self):
        other = make_user('other@x.test', is_staff=True)
        self.client.force_login(other)
        self.assertEqual(self.client.post(reverse('checkin-start', args=[self.lecture.id])).status_code, 403)
        self.client.force_login(self.a.user)
        self.assertEqual(self.client.get(reverse('checkin-state', args=[self.lecture.id])).status_code, 403)
