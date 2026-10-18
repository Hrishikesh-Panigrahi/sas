"""Tests for the calendar subscription feed and page."""
import datetime
import re

from django.test import TestCase, override_settings
from django.urls import include, path, reverse

from attendance.models import Assign_cls
from cls.models import Class
from course.models import Course
from student.models import student
from timetable import calendar_feed
from timetable.models import TimeTable
from users.models import TeacherProfile, User

# The tests run against the site's URLs plus this feature's, so they pass
# whether or not sas/urls.py includes timetable.calendar_urls yet.
urlpatterns = [
    path('', include('timetable.calendar_urls')),
    path('', include('sas.urls')),
]

DEPT = 'Computer Engineering'


def make_user(email, **flags):
    return User.objects.create_user(email, 'correct-horse-battery', first_name=email.split('@')[0].title(),
                                    last_name='Test', department=DEPT, **flags)


def unfold(ics):
    return ics.replace('\r\n ', '')


@override_settings(ROOT_URLCONF='timetable.test_calendar', TIME_ZONE='Asia/Kolkata', SEMESTER_END='2099-11-30')
class CalendarTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher = make_user('teacher@x.test', is_staff=True)
        cls.other_teacher = make_user('other@x.test', is_staff=True)
        cls.stu_user = make_user('stu@x.test')
        cls.loner = make_user('loner@x.test')
        cls.networks = Course.objects.create(code='CS1', scheme='R19', name='Networks', dept=DEPT, sem=5)
        cls.compilers = Course.objects.create(code='CS2', scheme='R19', name='Compilers', dept=DEPT, sem=5)
        cls.klass = Class.objects.create(class_name='TE-A', department=DEPT)
        cls.other_class = Class.objects.create(class_name='BE-B', department=DEPT)
        stu = student.objects.get(user=cls.stu_user)
        stu.cls, stu.batch = cls.klass, 'A'
        stu.save()
        teacher = TeacherProfile.objects.get(user=cls.teacher)
        Assign_cls.objects.create(cls=cls.klass, course=cls.networks, teacher=teacher)
        Assign_cls.objects.create(cls=cls.klass, course=cls.compilers,
                                  teacher=TeacherProfile.objects.get(user=cls.other_teacher))

        def slot(klass, course, day, start, end, lec_type='Lecture', batch='All'):
            return TimeTable.objects.create(cls=klass, course=course, lec_type=lec_type, batch=batch, day=day,
                                            start_time=start, end_time=end)

        t = datetime.time
        cls.lecture = slot(cls.klass, cls.networks, 'Monday', t(9, 30), t(10, 30))
        cls.lab_a = slot(cls.klass, cls.networks, 'Wednesday', t(14, 0), t(16, 0), 'Lab', 'A')
        cls.lab_b = slot(cls.klass, cls.networks, 'Wednesday', t(14, 0), t(16, 0), 'Lab', 'B')
        cls.compilers_slot = slot(cls.klass, cls.compilers, 'Friday', t(11, 30), t(12, 30))
        # Same course in a class the teacher isn't assigned to.
        cls.elsewhere = slot(cls.other_class, cls.networks, 'Tuesday', t(9, 30), t(10, 30))

    def feed(self, user, **params):
        url = reverse('calendar-feed', args=[calendar_feed.make_token(user)])
        return self.client.get(url, params)

    def uids(self, ics):
        return set(re.findall(r'^UID:slot-(\d+)@sas\r?$', unfold(ics), re.M))

    # ---------- Tokens ----------

    def test_token_round_trip_and_url_safe(self):
        token = calendar_feed.make_token(self.teacher)
        self.assertRegex(token, r'^[A-Za-z0-9_-]+$')
        self.assertEqual(calendar_feed.user_pk_from_token(token), self.teacher.pk)
        self.assertEqual(token, calendar_feed.make_token(self.teacher))   # permanent

    def test_invalid_tokens_404(self):
        good = calendar_feed.make_token(self.teacher)
        for token in ('nope', good[:-2] + ('AA' if not good.endswith('AA') else 'BB'), 'A' * 40):
            r = self.client.get(reverse('calendar-feed', args=[token]))
            self.assertEqual(r.status_code, 404, token)
        # A token signed for another purpose is rejected too.
        from django.core import signing
        import base64
        forged = base64.urlsafe_b64encode(
            signing.Signer(salt='something.else').sign(str(self.teacher.pk)).encode()).decode().rstrip('=')
        self.assertEqual(self.client.get(reverse('calendar-feed', args=[forged])).status_code, 404)

    def test_inactive_user_404(self):
        self.loner.is_active = False
        self.loner.save()
        self.assertEqual(self.feed(self.loner).status_code, 404)

    # ---------- Feed contents ----------

    def test_teacher_feed_has_assigned_slots_only(self):
        r = self.feed(self.teacher)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'text/calendar; charset=utf-8')
        ics = r.content.decode('utf-8')
        self.assertEqual(self.uids(ics), {str(s.id) for s in (self.lecture, self.lab_a, self.lab_b)})
        flat = unfold(ics)
        self.assertIn('X-WR-CALNAME:SAS · Teacher Test\r\n', flat)
        self.assertIn('SUMMARY:Networks\r\n', flat)
        self.assertIn('SUMMARY:Networks · Lab\\, batch A\r\n', flat)
        self.assertIn('LOCATION:TE-A\r\n', flat)
        self.assertIn('Course: Networks (CS1)', flat)
        self.assertIn('Teacher: Teacher Test', flat)

    def test_student_feed_has_class_slots_for_all_and_own_batch(self):
        ics = self.feed(self.stu_user).content.decode('utf-8')
        self.assertEqual(self.uids(ics), {str(s.id) for s in (self.lecture, self.lab_a, self.compilers_slot)})
        self.assertIn('Teacher: Other Test', unfold(ics))

    def test_student_without_batch_gets_whole_class_slots(self):
        stu = student.objects.get(user=self.stu_user)
        stu.batch = ''
        stu.save()
        ics = self.feed(self.stu_user).content.decode('utf-8')
        self.assertEqual(self.uids(ics), {str(self.lecture.id), str(self.compilers_slot.id)})

    def test_user_without_slots_gets_empty_but_valid_calendar(self):
        ics = self.feed(self.loner).content.decode('utf-8')
        self.assertTrue(ics.startswith('BEGIN:VCALENDAR\r\n'))
        self.assertTrue(ics.endswith('END:VCALENDAR\r\n'))
        self.assertNotIn('BEGIN:VEVENT', ics)

    def test_download_param_sets_attachment(self):
        r = self.feed(self.teacher, download='1')
        self.assertTrue(r['Content-Disposition'].startswith('attachment;'))
        self.assertTrue(self.feed(self.teacher)['Content-Disposition'].startswith('inline;'))

    # ---------- RFC 5545 structure ----------

    def test_ics_structure(self):
        today = datetime.date(2026, 10, 15)          # a Thursday
        now = datetime.datetime(2026, 10, 15, 6, 0, tzinfo=datetime.timezone.utc)
        ics = calendar_feed.build_ics(self.teacher, today=today, now=now)

        # CRLF everywhere, no bare LF, and folded lines no longer than 75 octets.
        self.assertTrue(ics.endswith('\r\n'))
        self.assertNotIn('\n', ics.replace('\r\n', ''))
        for line in ics.split('\r\n'):
            self.assertLessEqual(len(line.encode('utf-8')), 75, line)

        flat = unfold(ics)
        lines = flat.split('\r\n')
        self.assertEqual(lines[0], 'BEGIN:VCALENDAR')
        self.assertEqual(lines[-2], 'END:VCALENDAR')
        for required in ('VERSION:2.0', 'PRODID:-//SAS//Student Attendance System//EN', 'BEGIN:VTIMEZONE',
                         'TZID:Asia/Kolkata', 'BEGIN:STANDARD', 'TZOFFSETFROM:+0530', 'TZOFFSETTO:+0530',
                         'TZNAME:IST', 'END:VTIMEZONE'):
            self.assertIn(required, lines)
        self.assertEqual(flat.count('BEGIN:VEVENT'), 3)
        self.assertEqual(flat.count('BEGIN:VEVENT'), flat.count('END:VEVENT'))

        # Monday 09:30 lecture starts on the Monday of this week; Wednesday's lab two days later.
        self.assertIn('DTSTART;TZID=Asia/Kolkata:20261012T093000', lines)
        self.assertIn('DTEND;TZID=Asia/Kolkata:20261012T103000', lines)
        self.assertIn('DTSTART;TZID=Asia/Kolkata:20261014T140000', lines)
        # 30 Nov 2099 23:59:59 IST is 18:29:59 UTC.
        self.assertIn('RRULE:FREQ=WEEKLY;UNTIL=20991130T182959Z', lines)
        self.assertIn('DTSTAMP:20261015T060000Z', lines)
        self.assertIn('UID:slot-%d@sas' % self.lecture.id, lines)

    def test_escaping_and_folding(self):
        self.assertEqual(calendar_feed.escape_text('a\\b;c,d\ne'), 'a\\\\b\\;c\\,d\\ne')
        long = 'DESCRIPTION:' + 'é' * 100
        folded = calendar_feed.fold(long)
        parts = folded.split('\r\n')
        self.assertGreater(len(parts), 1)
        for i, part in enumerate(parts):
            self.assertLessEqual(len(part.encode('utf-8')), 75)
            if i:
                self.assertTrue(part.startswith(' '))
        self.assertEqual(folded.replace('\r\n ', ''), long)

    def test_long_names_are_folded_in_feed(self):
        self.networks.name = 'Advanced Computer Networks, Security; and Distributed Systems Engineering'
        self.networks.save()
        ics = self.feed(self.teacher).content.decode('utf-8')
        self.assertIn('\r\n ', ics)
        for line in ics.split('\r\n'):
            self.assertLessEqual(len(line.encode('utf-8')), 75)
        self.assertIn('SUMMARY:Advanced Computer Networks\\, Security\\; and Distributed Systems Engineering\r\n',
                      unfold(ics))

    def test_slots_after_semester_end_are_left_out(self):
        with self.settings(SEMESTER_END='2026-10-13'):   # a Tuesday
            ics = calendar_feed.build_ics(self.teacher, today=datetime.date(2026, 10, 13))
        self.assertEqual(self.uids(ics), {str(self.lecture.id)})
        self.assertIn('RRULE:FREQ=WEEKLY;UNTIL=20261013T182959Z', unfold(ics))

    def test_daylight_saving_zone_gets_both_observances(self):
        lines = calendar_feed.vtimezone('Europe/London', datetime.date(2026, 10, 12), datetime.date(2027, 4, 30))
        self.assertIn('BEGIN:DAYLIGHT', lines)
        self.assertIn('BEGIN:STANDARD', lines)
        # BST ends at 02:00 local (01:00 UTC) on 25 Oct 2026; starts 01:00 GMT on 28 Mar 2027.
        self.assertIn('DTSTART:20261025T020000', lines)
        self.assertIn('DTSTART:20270328T010000', lines)

    # ---------- Page ----------

    def test_page_requires_login(self):
        r = self.client.get(reverse('calendar'))
        self.assertEqual(r.status_code, 302)

    def test_page_shows_links(self):
        self.client.force_login(self.teacher)
        r = self.client.get(reverse('calendar'))
        self.assertEqual(r.status_code, 200)
        token = calendar_feed.make_token(self.teacher)
        self.assertContains(r, 'http://testserver/calendar/%s.ics' % token)
        self.assertContains(r, 'webcal://testserver/calendar/%s.ics' % token)
        self.assertContains(r, 'https://calendar.google.com/calendar/r?cid=webcal%3A%2F%2Ftestserver%2Fcalendar%2F')
        self.assertContains(r, 'Download .ics')
        self.assertContains(r, 'Anyone who has it can see your timetable')
        self.assertContains(r, 'Networks · Lab, batch A')
        self.assertNotContains(r, 'Nothing to sync yet')

    def test_page_empty_state(self):
        self.client.force_login(self.loner)
        r = self.client.get(reverse('calendar'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Nothing to sync yet')
        self.assertContains(r, calendar_feed.make_token(self.loner))
