import datetime

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from attendance.models import Assign_cls, Attendance, AttendanceClass
from attendance.stats import student_summary
from cls.models import Class
from course.models import Course
from student.models import student
from users.models import TeacherProfile, User
from .models import LeaveRequest

DEPT = 'Computer Engineering'


def make_user(email, **flags):
    return User.objects.create_user(email, 'pass-12345-x', first_name=email.split('@')[0].title(),
                                    last_name='Test', department=DEPT, **flags)


class LeaveTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hod = make_user('hod@x.test', is_staff=True, is_hod=True)
        cls.teacher = make_user('teacher@x.test', is_staff=True)
        cls.klass = Class.objects.create(class_name='TE-A', department=DEPT)
        course = Course.objects.create(code='CS1', scheme='R19', name='Networks', dept=DEPT, sem=5)
        cls.assign = Assign_cls.objects.create(cls=cls.klass, course=course,
                                               teacher=TeacherProfile.objects.get(user=cls.teacher))
        cls.stu = student.objects.get(user=make_user('stu@x.test'))
        cls.stu.cls = cls.klass
        cls.stu.save()
        cls.today = timezone.localdate()
        for i in range(4):
            day = cls.today - datetime.timedelta(days=4 - i)
            lec = AttendanceClass.objects.create(assign=cls.assign, date=day, period='9-10', status=1)
            # Present on the first two days, absent (ill) on the last two.
            Attendance.objects.create(course=course, student=cls.stu, date=day, attendanceclass=lec, status=i < 2)

    def test_student_applies_with_document(self):
        self.client.force_login(self.stu.user)
        pdf = SimpleUploadedFile('certificate.pdf', b'%PDF-1.4 test', content_type='application/pdf')
        r = self.client.post(reverse('leave'), {
            'kind': 'medical', 'start_date': (self.today - datetime.timedelta(days=2)).isoformat(),
            'end_date': (self.today - datetime.timedelta(days=1)).isoformat(),
            'reason': 'Fever', 'document_file': pdf})
        self.assertRedirects(r, reverse('leave'))
        leave = LeaveRequest.objects.get()
        self.assertEqual((leave.status, leave.document_type), ('pending', 'application/pdf'))
        self.assertEqual(self.client.get(reverse('leave-document', args=[leave.id])).status_code, 200)

    def test_fake_document_rejected(self):
        self.client.force_login(self.stu.user)
        r = self.client.post(reverse('leave'), {
            'kind': 'medical', 'start_date': self.today.isoformat(), 'end_date': self.today.isoformat(),
            'reason': 'x', 'document_file': SimpleUploadedFile('a.pdf', b'MZ not a pdf')})
        self.assertContains(r, "doesn&#x27;t look like a real PDF")

    def test_approval_excuses_absences_and_revoking_restores(self):
        leave = LeaveRequest.objects.create(student=self.stu, kind='medical', reason='Fever',
                                            start_date=self.today - datetime.timedelta(days=2),
                                            end_date=self.today - datetime.timedelta(days=1))
        self.assertEqual(student_summary(self.stu)['percent'], 50)
        self.client.force_login(self.hod)
        self.assertContains(self.client.get(reverse('leave')), 'Fever')
        self.client.post(reverse('leave-review', args=[leave.id]), {'action': 'approve'})
        self.assertEqual(Attendance.objects.filter(excused=True).count(), 2)
        self.assertEqual(student_summary(self.stu)['percent'], 100)   # excused absences don't count
        self.client.post(reverse('leave-review', args=[leave.id]), {'action': 'reject'})
        self.assertEqual(Attendance.objects.filter(excused=True).count(), 0)

    def test_marking_on_approved_leave_is_excused(self):
        LeaveRequest.objects.create(student=self.stu, kind='medical', reason='x', status='approved',
                                    start_date=self.today, end_date=self.today)
        lec = AttendanceClass.objects.create(assign=self.assign, date=self.today, period='10-11')
        self.client.force_login(self.teacher)
        page = self.client.get(reverse('attendance', args=[lec.id]))
        self.assertContains(page, 'On leave')
        self.client.post(reverse('attendance', args=[lec.id]), {'status_%d' % self.stu.id: 'absent'})
        self.assertTrue(Attendance.objects.get(attendanceclass=lec).excused)

    def test_permissions(self):
        leave = LeaveRequest.objects.create(student=self.stu, kind='other', reason='x',
                                            start_date=self.today, end_date=self.today)
        self.client.force_login(self.teacher)   # plain teacher: no inbox, can't decide
        self.assertEqual(self.client.get(reverse('leave')).status_code, 403)
        self.assertEqual(self.client.post(reverse('leave-review', args=[leave.id]), {'action': 'approve'}).status_code, 404)
        other = student.objects.get(user=make_user('other@x.test'))
        self.client.force_login(other.user)
        self.assertEqual(self.client.post(reverse('leave-cancel', args=[leave.id])).status_code, 404)
