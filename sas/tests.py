"""End-to-end tests for the main flows of each role."""
import datetime

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from attendance.models import Assign_cls, Attendance, AttendanceClass
from cls.models import Class
from course.models import Course
from student.models import student
from timetable.models import TimeTable
from users.models import TeacherProfile, User

DEPT = 'Computer Engineering'
OTHER = 'Mechanical Engineering'
PASSWORD = 'correct-horse-battery'


def make_user(email, dept=DEPT, **flags):
    return User.objects.create_user(email, PASSWORD, first_name=email.split('@')[0].title(),
                                    last_name='Test', department=dept, **flags)


class Base(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.hod = make_user('hod@x.test', is_staff=True, is_hod=True, is_classteacher=True)
        cls.teacher = make_user('teacher@x.test', is_staff=True)
        cls.other_teacher = make_user('other@x.test', is_staff=True)
        cls.stu_user = make_user('stu@x.test')
        cls.stu2_user = make_user('stu2@x.test')
        cls.course = Course.objects.create(code='CS1', scheme='R19', name='Networks', dept=DEPT, sem=5)
        cls.course2 = Course.objects.create(code='CS2', scheme='R19', name='Compilers', dept=DEPT, sem=5)
        cls.foreign_course = Course.objects.create(code='ME1', scheme='R19', name='Thermo', dept=OTHER, sem=5)
        cls.klass = Class.objects.create(class_name='TE-A', department=DEPT)
        cls.stu = student.objects.get(user=cls.stu_user)
        cls.stu2 = student.objects.get(user=cls.stu2_user)
        for i, s in enumerate((cls.stu, cls.stu2), start=1):
            s.cls, s.roll_no = cls.klass, i
            s.save()
        cls.assign = Assign_cls.objects.create(
            cls=cls.klass, course=cls.course, teacher=TeacherProfile.objects.get(user=cls.teacher))

    def login(self, user):
        self.client.force_login(user)


class AuthTests(Base):
    def test_login_and_safe_redirects(self):
        url = reverse('Login')
        r = self.client.post(url, {'email': 'hod@x.test', 'password': 'wrong'})
        self.assertContains(r, 'not correct')
        r = self.client.post(url, {'email': 'hod@x.test', 'password': PASSWORD,
                                   'next': 'https://evil.example/'})
        self.assertRedirects(r, reverse('index'))
        self.client.logout()
        r = self.client.post(url, {'email': 'hod@x.test', 'password': PASSWORD, 'next': '/course/'})
        self.assertRedirects(r, '/course/')

    def test_logout_get_does_not_crash_and_post_logs_out(self):
        self.login(self.hod)
        self.assertRedirects(self.client.get(reverse('logout')), reverse('Login'), target_status_code=302)
        self.client.post(reverse('logout'))
        r = self.client.get(reverse('index'))
        self.assertEqual(r.status_code, 302)
        self.assertIn(reverse('Login'), r.url)

    def test_anonymous_users_are_sent_to_login(self):
        for name in ('index', 'chome', 'teachers', 'StudentList', 'viewcls', 'attendance-home', 'timetable'):
            r = self.client.get(reverse(name))
            self.assertEqual(r.status_code, 302, name)

    def test_attendance_urls_are_not_protocol_relative(self):
        # Used to reverse to "//<id>/attendance/class", which browsers treat as a host name.
        self.assertEqual(reverse('attendance-home'), '/attendance/')
        self.assertFalse(reverse('attendance', args=[1]).startswith('//'))


class RoleTests(Base):
    def test_student_cannot_open_staff_pages(self):
        self.login(self.stu_user)
        for name in ('chome', 'teachers', 'StudentList', 'attendance-home', 'clsCreation'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403, name)

    def test_plain_teacher_cannot_manage(self):
        self.login(self.teacher)
        self.assertEqual(self.client.get(reverse('course-create')).status_code, 403)
        self.assertEqual(self.client.get(reverse('FacultyRegister')).status_code, 403)
        self.assertEqual(self.client.get(reverse('clsCreation')).status_code, 403)
        self.assertEqual(self.client.get(reverse('chome')).status_code, 200)

    def test_pages_render_for_every_role(self):
        lecture = AttendanceClass.objects.create(assign=self.assign, date=timezone.localdate(), period='9-10')
        pages = [reverse(n) for n in ('index', 'chome', 'teachers', 'StudentList', 'viewcls',
                                      'attendance-home', 'timetable', 'profile', 'password-change',
                                      'course-create', 'FacultyRegister', 'StudentRegister', 'clsCreation')]
        pages += [reverse('course-update', args=[self.course.id]), reverse('course-delete', args=[self.course.id]),
                  reverse('class-detail', args=[self.klass.id]), reverse('class-edit', args=[self.klass.id]),
                  reverse('class-delete', args=[self.klass.id]), reverse('timetable-class', args=[self.klass.id]),
                  reverse('student-detail', args=[self.stu.id]), reverse('UpdateStudent', args=[self.stu.id]),
                  reverse('deleteStudent', args=[self.stu.id]),
                  reverse('updateTeacher', args=[self.assign.teacher.id]),
                  reverse('deleteTeacher', args=[self.assign.teacher.id]),
                  reverse('attendance-attendance_date', args=[self.assign.id]),
                  reverse('attendance-report', args=[self.assign.id]),
                  reverse('attendance', args=[lecture.id])]
        self.login(self.hod)
        for url in pages:
            self.assertEqual(self.client.get(url).status_code, 200, url)
        self.login(self.teacher)
        self.assertEqual(self.client.get(reverse('index')).status_code, 200)
        self.login(self.stu_user)
        self.assertEqual(self.client.get(reverse('index')).status_code, 200)

    def test_other_department_is_hidden(self):
        self.login(self.hod)
        self.assertEqual(self.client.get(reverse('course-update', args=[self.foreign_course.id])).status_code, 404)
        self.assertNotContains(self.client.get(reverse('chome')), 'Thermo')


class CourseTests(Base):
    def test_hod_creates_course_in_own_department(self):
        self.login(self.hod)
        r = self.client.post(reverse('course-create'), {
            'code': 'CS9', 'name': 'AI', 'scheme': 'R19', 'sem': 6, 'dept': OTHER, 'dept_level': 'on'})
        self.assertRedirects(r, reverse('chome'))
        self.assertEqual(Course.objects.get(code='CS9').dept, DEPT)

    def test_invalid_course_shows_errors(self):
        self.login(self.hod)
        r = self.client.post(reverse('course-create'), {'code': '', 'name': '', 'sem': ''})
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'This field is required')


class PeopleTests(Base):
    def test_register_teacher(self):
        self.login(self.hod)
        data = {'first_name': 'New', 'last_name': 'Teacher', 'email': 'new@x.test',
                'is_classteacher': 'on', 'password1': 'Zebra-Lamp-42', 'password2': 'Zebra-Lamp-42'}
        r = self.client.post(reverse('FacultyRegister'), data)
        self.assertRedirects(r, reverse('teachers'))
        user = User.objects.get(email='new@x.test')
        self.assertTrue(user.is_staff and user.is_classteacher)
        self.assertEqual(user.department, DEPT)
        self.assertTrue(TeacherProfile.objects.filter(user=user).exists())
        self.assertTrue(user.check_password('Zebra-Lamp-42'))

    def test_password_mismatch(self):
        self.login(self.hod)
        r = self.client.post(reverse('FacultyRegister'), {
            'first_name': 'A', 'last_name': 'B', 'email': 'ab@x.test',
            'password1': 'Zebra-Lamp-42', 'password2': 'nope'})
        self.assertContains(r, "don&#x27;t match")
        self.assertFalse(User.objects.filter(email='ab@x.test').exists())

    def test_register_student_into_class(self):
        self.login(self.hod)
        r = self.client.post(reverse('StudentRegister'), {
            'first_name': 'Riya', 'last_name': 'Sen', 'email': 'riya@x.test', 'roll_no': 3,
            'cls': self.klass.id, 'password1': 'Zebra-Lamp-42', 'password2': 'Zebra-Lamp-42'})
        self.assertRedirects(r, reverse('StudentList'))
        stu = student.objects.get(user__email='riya@x.test')
        self.assertEqual((stu.cls, stu.roll_no, stu.user.first_name), (self.klass, 3, 'Riya'))
        self.assertIn(self.course, stu.course.all())

    def test_edit_student_keeps_password_when_blank(self):
        self.login(self.hod)
        r = self.client.post(reverse('UpdateStudent', args=[self.stu.id]), {
            'first_name': 'Changed', 'last_name': 'Name', 'email': 'stu@x.test', 'roll_no': 9,
            'cls': self.klass.id, 'password1': '', 'password2': ''})
        self.assertRedirects(r, reverse('student-detail', args=[self.stu.id]))
        self.stu_user.refresh_from_db()
        self.assertEqual(self.stu_user.first_name, 'Changed')
        self.assertTrue(self.stu_user.check_password(PASSWORD))

    def test_toggling_staff_keeps_profiles(self):
        self.teacher.is_staff = False
        self.teacher.save()
        self.assertTrue(Assign_cls.objects.filter(pk=self.assign.pk).exists())


class ClassTests(Base):
    def test_create_class_with_courses_and_students(self):
        self.login(self.hod)
        newbie = student.objects.get(user=make_user('new-stu@x.test'))
        r = self.client.post(reverse('clsCreation'), {
            'class_name': 'TE-B', 'class_teacher': TeacherProfile.objects.get(user=self.hod).pk,
            'course_%d' % self.course2.id: 'on',
            'teacher_%d' % self.course2.id: TeacherProfile.objects.get(user=self.other_teacher).pk,
            'students': [newbie.pk]})
        cls = Class.objects.get(class_name='TE-B')
        self.assertRedirects(r, reverse('class-detail', args=[cls.id]))
        self.assertEqual(cls.department, DEPT)
        self.assertEqual(cls.assign_cls_set.get().teacher.user, self.other_teacher)
        newbie.refresh_from_db()
        self.assertEqual(newbie.cls, cls)

    def test_course_without_teacher_is_rejected(self):
        self.login(self.hod)
        r = self.client.post(reverse('clsCreation'), {
            'class_name': 'TE-C', 'course_%d' % self.course2.id: 'on'})
        self.assertContains(r, 'Choose who teaches this course')
        self.assertFalse(Class.objects.filter(class_name='TE-C').exists())

    def test_edit_keeps_courses_with_attendance(self):
        AttendanceClass.objects.create(assign=self.assign, date=timezone.localdate(), period='9-10')
        self.login(self.hod)
        r = self.client.post(reverse('class-edit', args=[self.klass.id]), {
            'class_name': 'TE-A', 'students': [self.stu.pk, self.stu2.pk]}, follow=True)
        self.assertContains(r, 'Kept Networks')
        self.assertTrue(Assign_cls.objects.filter(pk=self.assign.pk).exists())

    def test_edit_reassigns_teacher_and_removes_students(self):
        self.login(self.hod)
        other = TeacherProfile.objects.get(user=self.other_teacher)
        self.client.post(reverse('class-edit', args=[self.klass.id]), {
            'class_name': 'TE-A', 'course_%d' % self.course.id: 'on',
            'teacher_%d' % self.course.id: other.pk, 'students': [self.stu.pk]})
        self.assign.refresh_from_db()
        self.assertEqual(self.assign.teacher, other)
        self.stu2.refresh_from_db()
        self.assertIsNone(self.stu2.cls)


class AttendanceTests(Base):
    def test_take_and_edit_attendance(self):
        self.login(self.teacher)
        today = timezone.localdate()
        r = self.client.post(reverse('create_lecture', args=[self.assign.id]),
                             {'date': today.isoformat(), 'period': '9:30 - 10:30'})
        lecture = AttendanceClass.objects.get(assign=self.assign)
        self.assertRedirects(r, reverse('attendance', args=[lecture.id]))
        self.assertEqual(lecture.day, today.strftime('%A'))

        mark = reverse('attendance', args=[lecture.id])
        self.client.post(mark, {'status_%d' % self.stu.id: 'present', 'status_%d' % self.stu2.id: 'absent'})
        lecture.refresh_from_db()
        self.assertTrue(lecture.is_marked)
        self.assertFalse(Attendance.objects.get(student=self.stu2).status)

        # The edit page shows the saved values and saving again doesn't duplicate rows.
        r = self.client.get(reverse('edit-attendance', args=[lecture.id]))
        self.assertContains(r, 'id="a%d" name="status_%d" value="absent" checked' % (self.stu2.id, self.stu2.id))
        self.client.post(mark, {'status_%d' % self.stu.id: 'absent', 'status_%d' % self.stu2.id: 'present'})
        self.assertEqual(Attendance.objects.filter(attendanceclass=lecture).count(), 2)
        self.assertTrue(Attendance.objects.get(student=self.stu2).status)

    def test_future_lecture_rejected(self):
        self.login(self.teacher)
        tomorrow = timezone.localdate() + datetime.timedelta(days=1)
        self.client.post(reverse('create_lecture', args=[self.assign.id]),
                         {'date': tomorrow.isoformat(), 'period': '9:30 - 10:30'})
        self.assertFalse(AttendanceClass.objects.exists())

    def test_other_teacher_cannot_mark(self):
        lecture = AttendanceClass.objects.create(assign=self.assign, date=timezone.localdate(), period='9-10')
        self.login(self.other_teacher)
        self.assertEqual(self.client.get(reverse('attendance', args=[lecture.id])).status_code, 403)
        self.assertEqual(self.client.get(reverse('attendance-report', args=[self.assign.id])).status_code, 403)

    def test_report_and_csv(self):
        lecture = AttendanceClass.objects.create(assign=self.assign, date=timezone.localdate(), period='9-10', status=1)
        Attendance.objects.create(course=self.course, student=self.stu, date=lecture.date, attendanceclass=lecture, status=True)
        Attendance.objects.create(course=self.course, student=self.stu2, date=lecture.date, attendanceclass=lecture, status=False)
        self.login(self.teacher)
        r = self.client.get(reverse('attendance-report', args=[self.assign.id]))
        self.assertEqual(r.context['average'], 50)
        self.assertEqual(r.context['num_short'], 1)
        r = self.client.get(reverse('attendance-report', args=[self.assign.id]) + '?format=csv')
        self.assertEqual(r['Content-Type'], 'text/csv')
        self.assertIn('Stu Test,stu@x.test,1,1,100', r.content.decode())

    def test_student_dashboard_shows_shortfall(self):
        for i in range(4):
            lecture = AttendanceClass.objects.create(assign=self.assign, date=timezone.localdate(), period=str(i), status=1)
            Attendance.objects.create(course=self.course, student=self.stu, date=lecture.date,
                                      attendanceclass=lecture, status=i == 0)
        self.login(self.stu_user)
        r = self.client.get(reverse('index'))
        self.assertEqual(r.context['summary']['percent'], 25)
        self.assertEqual(r.context['summary']['needed'], 8)  # (1+8)/(4+8) = 75%


class TimetableTests(Base):
    def add(self, **data):
        base = {'day': 'Monday', 'start_time': '09:00', 'end_time': '10:00', 'course': self.course.id,
                'lec_type': 'Lecture', 'batch': 'All'}
        base.update(data)
        return self.client.post(reverse('timetable-class', args=[self.klass.id]), base)

    def test_add_slot_and_reject_clashes(self):
        self.login(self.hod)
        self.assertEqual(self.add().status_code, 302)
        r = self.add(start_time='09:30', end_time='10:30')
        self.assertContains(r, 'already has Networks')
        r = self.add(start_time='10:00', end_time='09:00')
        self.assertContains(r, 'must end after it starts')
        self.assertEqual(TimeTable.objects.count(), 1)

    def test_teacher_double_booking_rejected(self):
        other_cls = Class.objects.create(class_name='TE-B', department=DEPT)
        Assign_cls.objects.create(cls=other_cls, course=self.course2, teacher=self.assign.teacher)
        TimeTable.objects.create(cls=other_cls, course=self.course2, lec_type='Lecture', batch='All',
                                 day='Monday', start_time='09:00', end_time='10:00')
        self.login(self.hod)
        self.assertContains(self.add(), 'is already teaching TE-B')

    def test_start_attendance_from_todays_slot(self):
        today = timezone.localdate().strftime('%A')
        slot = TimeTable.objects.create(cls=self.klass, course=self.course, lec_type='Lecture', batch='All',
                                        day=today, start_time='09:00', end_time='10:00')
        self.login(self.teacher)
        r = self.client.get(reverse('index'))
        self.assertContains(r, 'Take attendance')
        self.assertEqual(len(r.context['today_slots']), 1)
        r = self.client.post(reverse('attendance-start', args=[slot.id]))
        lecture = AttendanceClass.objects.get()
        self.assertRedirects(r, reverse('attendance', args=[lecture.id]))
        self.assertEqual(lecture.period, '09:00 - 10:00')
        # Starting again reopens the same lecture.
        self.client.post(reverse('attendance-start', args=[slot.id]))
        self.assertEqual(AttendanceClass.objects.count(), 1)
