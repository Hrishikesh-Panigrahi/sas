import datetime
import re

from django.test import TestCase, override_settings
from django.urls import include, path, reverse

import sas.urls
from cls.models import Class
from course.models import Course
from student.models import student
from users.models import TeacherProfile, User
from .defaulters import (defaulter_list_pdf, defaulters, needed_for, warning_letters_pdf)
from .models import Assign_cls, Attendance, AttendanceClass

# The project URLconf plus the defaulter URLs, so these tests run whether or not
# sas/urls.py includes them yet.
urlpatterns = [path('reports/', include('attendance.defaulter_urls'))] + sas.urls.urlpatterns

DEPT = 'Computer Engineering'
OTHER = 'Mechanical Engineering'


def make_user(email, department=DEPT, **flags):
    return User.objects.create_user(email, 'pass-12345-x', first_name=email.split('@')[0].title(),
                                    last_name='Test', department=department, **flags)


def make_student(email, klass, roll, department=DEPT):
    stu = student.objects.get(user=make_user(email, department=department))
    stu.cls, stu.roll_no = klass, roll
    stu.save()
    return stu


def hold_lectures(assign, attended, count=10):
    """`count` marked lectures; `attended` maps each student to how many they attended."""
    start = datetime.date(2026, 8, 3)
    for i in range(count):
        day = start + datetime.timedelta(days=i)
        lec = AttendanceClass.objects.create(assign=assign, date=day, period='09:00 - 10:00', status=1)
        for stu, n in attended.items():
            Attendance.objects.create(course=assign.course, student=stu, date=day,
                                      attendanceclass=lec, status=i < n)


def pages(pdf):
    return len(re.findall(rb'/Type /Page\b(?!s)', pdf))


@override_settings(ROOT_URLCONF=__name__, ATTENDANCE_THRESHOLD=75)
class DefaulterTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hod = make_user('hod@x.test', is_staff=True, is_hod=True)
        cls.class_teacher = make_user('ct@x.test', is_staff=True, is_classteacher=True)
        cls.teacher = make_user('teacher@x.test', is_staff=True)
        teacher = TeacherProfile.objects.get(user=cls.teacher)

        cls.klass = Class.objects.create(class_name='TE-A', department=DEPT,
                                         class_teacher=TeacherProfile.objects.get(user=cls.class_teacher))
        cls.other_klass = Class.objects.create(class_name='ME-A', department=OTHER)
        cls.networks = Course.objects.create(code='CSC503', scheme='R19', name='Computer Networks',
                                             dept=DEPT, sem=5)
        cls.dbms = Course.objects.create(code='CSC504', scheme='R19', name='Databases', dept=DEPT, sem=5)
        cls.thermo = Course.objects.create(code='MEC501', scheme='R19', name='Thermodynamics',
                                           dept=OTHER, sem=5)

        cls.good = make_student('good@x.test', cls.klass, 1)
        cls.poor = make_student('poor@x.test', cls.klass, 2)
        cls.border = make_student('border@x.test', cls.klass, 3)
        cls.outsider = make_student('outsider@x.test', cls.other_klass, 1, department=OTHER)

        cls.assign_cn = Assign_cls.objects.create(cls=cls.klass, course=cls.networks, teacher=teacher)
        cls.assign_db = Assign_cls.objects.create(cls=cls.klass, course=cls.dbms, teacher=teacher)
        assign_me = Assign_cls.objects.create(cls=cls.other_klass, course=cls.thermo, teacher=teacher)
        # Networks: good 100%, poor 60%, border 70%. Databases: poor 50%, the rest 100%.
        hold_lectures(cls.assign_cn, {cls.good: 10, cls.poor: 6, cls.border: 7})
        hold_lectures(cls.assign_db, {cls.good: 10, cls.poor: 5, cls.border: 10})
        hold_lectures(assign_me, {cls.outsider: 2})

    def get(self, name, user=None, args=(), **params):
        self.client.force_login(user or self.hod)
        return self.client.get(reverse(name, args=args), params)

    # --- data ---------------------------------------------------------------

    def test_sections_and_rollup(self):
        report = defaulters(self.hod)
        self.assertEqual([s['course'].code for s in report['sections']], ['CSC503', 'CSC504'])
        cn = report['sections'][0]
        self.assertEqual([r['student'] for r in cn['students']], [self.poor, self.border])  # worst first
        self.assertEqual(cn['lectures'], 10)
        self.assertEqual([e['student'] for e in report['students']], [self.poor, self.border])
        poor = report['students'][0]
        self.assertEqual([(c['code'], c['percent'], c['needed']) for c in poor['courses']],
                         [('CSC503', 60, 6), ('CSC504', 50, 10)])
        self.assertEqual(poor['summary']['percent'], 55)
        self.assertEqual(report['counts'], {'students': 2, 'courses': 2, 'classes': 1,
                                            'classes_in_scope': 1})

    def test_needed_for_other_thresholds(self):
        self.assertEqual(needed_for(6, 10, 75), 6)
        self.assertEqual(needed_for(6, 10, 80), 10)
        self.assertEqual(needed_for(8, 10, 80), 0)
        self.assertIsNone(needed_for(9, 10, 100))

    # --- page ---------------------------------------------------------------

    def test_page_lists_students_below_threshold_only(self):
        response = self.get('defaulters')
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Poor Test')
        self.assertContains(response, 'Border Test')
        self.assertContains(response, 'CSC503 60% (6/10)')
        self.assertContains(response, reverse('defaulter-letter', args=[self.poor.id]))
        self.assertNotContains(response, 'Good Test')
        self.assertNotContains(response, 'Outsider Test')

    def test_threshold_changes_who_is_listed(self):
        response = self.get('defaulters', threshold=65)
        self.assertContains(response, 'Poor Test')
        self.assertNotContains(response, 'Border Test')
        self.assertEqual(response.context['report']['counts']['students'], 1)
        response = self.get('defaulters', threshold=50)
        self.assertNotContains(response, 'Poor Test')
        self.assertContains(response, 'Nobody is below 50%')
        # Out-of-range and junk values fall back to the 50-100 range / the setting.
        self.assertEqual(self.get('defaulters', threshold=10).context['report']['threshold'], 50)
        self.assertEqual(self.get('defaulters', threshold='x').context['report']['threshold'], 75)

    def test_class_filter(self):
        response = self.get('defaulters', cls=self.klass.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['report']['cls'], self.klass)
        self.assertContains(response, 'Poor Test')

    def test_class_from_another_department_is_404(self):
        self.assertEqual(self.get('defaulters', cls=self.other_klass.id).status_code, 404)
        self.assertEqual(self.get('defaulters-pdf', cls=self.other_klass.id).status_code, 404)
        self.assertEqual(self.get('defaulters-letters', cls='abc').status_code, 404)
        self.assertEqual(self.get('defaulter-letter', args=[self.outsider.id]).status_code, 404)

    def test_permissions(self):
        for user in (self.teacher, self.good.user):
            for name, args in (('defaulters', ()), ('defaulters-pdf', ()),
                               ('defaulters-letters', ()), ('defaulter-letter', (self.poor.id,))):
                with self.subTest(user=user.email, url=name):
                    self.assertEqual(self.get(name, user, args).status_code, 403)
        self.assertEqual(self.get('defaulters', self.class_teacher).status_code, 200)
        self.client.logout()
        self.assertEqual(self.client.get(reverse('defaulters')).status_code, 302)

    # --- PDFs ---------------------------------------------------------------

    def assertPdf(self, response, filename_start):
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertIn('attachment; filename="%s' % filename_start, response['Content-Disposition'])

    def test_defaulter_list_pdf(self):
        self.assertPdf(self.get('defaulters-pdf'), 'defaulters-computer-engineering-')
        self.assertPdf(self.get('defaulters-pdf', cls=self.klass.id, threshold=90), 'defaulters-te-a-')
        # Nobody below: still a valid document.
        self.assertPdf(self.get('defaulters-pdf', threshold=50), 'defaulters-')

    def test_warning_letters_pdf(self):
        response = self.get('defaulters-letters')
        self.assertPdf(response, 'warning-letters-computer-engineering-')
        self.assertEqual(pages(response.content), 2)   # one page per student
        response = self.get('defaulters-letters', threshold=65)
        self.assertEqual(pages(response.content), 1)

    def test_single_letter(self):
        response = self.get('defaulter-letter', args=[self.poor.id], threshold=80)
        self.assertPdf(response, 'warning-letter-te-a-2-')
        self.assertEqual(pages(response.content), 1)

    def test_no_letter_for_student_above_threshold(self):
        response = self.get('defaulter-letter', args=[self.good.id])
        self.assertRedirects(response, reverse('defaulters') + '?cls=%d&threshold=75' % self.klass.id)

    def test_pdfs_are_deterministic(self):
        report = defaulters(self.hod)
        self.assertEqual(defaulter_list_pdf(report), defaulter_list_pdf(defaulters(self.hod)))
        self.assertEqual(warning_letters_pdf(report), warning_letters_pdf(defaulters(self.hod)))
