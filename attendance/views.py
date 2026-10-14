import csv

from django.contrib import messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Count, Max, Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from sas.permissions import in_department, staff_required
from student.models import ROLL_ORDER
from timetable.models import TimeTable
from .forms import LectureForm
from .models import Assign_cls, Attendance, AttendanceClass
from .stats import assignment_report


def _can_view(user, assign):
    if assign.teacher.user_id == user.id or user.is_superuser:
        return True
    return user.can_manage_students and assign.cls.department == user.department


def _can_mark(user, assign):
    if assign.teacher.user_id == user.id or user.is_superuser:
        return True
    return user.can_manage_department and assign.cls.department == user.department


def _get_assignment(request, assign_id, mark=False):
    assign = get_object_or_404(
        Assign_cls.objects.select_related('cls', 'course', 'teacher__user'), pk=assign_id)
    allowed = _can_mark if mark else _can_view
    if not allowed(request.user, assign):
        raise PermissionDenied
    return assign


def _with_stats(assignments):
    return assignments.select_related('cls', 'course', 'teacher__user').annotate(
        num_lectures=Count('attendanceclass', distinct=True),
        num_pending=Count('attendanceclass', distinct=True,
                          filter=Q(attendanceclass__status=0)),
        last_lecture=Max('attendanceclass__date'),
    ).order_by('cls__class_name', 'course__name')


@staff_required
def home(request):
    user = request.user
    context = {
        'title': 'Attendance',
        'assignments': _with_stats(Assign_cls.objects.filter(teacher__user=user)),
    }
    if user.can_manage_students:
        context['department_assignments'] = _with_stats(
            in_department(Assign_cls.objects.exclude(teacher__user=user), user, 'cls__department'))
    return render(request, 'attendance/home.html', context)


@staff_required
def lectures(request, assign_id):
    assign = _get_assignment(request, assign_id)
    lecture_list = (assign.attendanceclass_set
                    .annotate(num_present=Count('attendance', filter=Q(attendance__status=True)),
                              num_marked=Count('attendance'))
                    .order_by('-date', '-id'))
    context = {
        'title': '%s · %s' % (assign.course.name, assign.cls.class_name),
        'assign': assign,
        'lectures': lecture_list,
        'num_students': assign.cls.student_set.count(),
        'can_mark': _can_mark(request.user, assign),
        'form': LectureForm(assign=assign),
    }
    return render(request, 'attendance/lectures.html', context)


@staff_required
def create_lecture(request, assign_id):
    assign = _get_assignment(request, assign_id, mark=True)
    if request.method != 'POST':
        return redirect('attendance-attendance_date', assign_id=assign.id)
    form = LectureForm(request.POST, assign=assign)
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect('attendance-attendance_date', assign_id=assign.id)
    date = form.cleaned_data['date']
    lecture, created = AttendanceClass.objects.get_or_create(
        assign=assign, date=date, period=form.cleaned_data['period'],
        batch=form.cleaned_data['batch'], defaults={'day': date.strftime('%A')})
    if not created:
        messages.info(request, 'That lecture already exists, so it has been opened for you.')
    return redirect('attendance', attendancecls_id=lecture.id)


@staff_required
@require_POST
def start_from_slot(request, slot_id):
    """Open (or create) today's lecture for a timetable slot."""
    slot = get_object_or_404(TimeTable, pk=slot_id)
    assign = Assign_cls.objects.filter(cls=slot.cls, course=slot.course,
                                       teacher__user=request.user).first()
    if assign is None:
        raise PermissionDenied
    today = timezone.localdate()
    lecture, _ = AttendanceClass.objects.get_or_create(
        assign=assign, date=today, period=slot.period, batch=slot.batch,
        defaults={'day': today.strftime('%A')})
    return redirect('attendance', attendancecls_id=lecture.id)


@staff_required
def mark(request, attendancecls_id):
    lecture = get_object_or_404(AttendanceClass, pk=attendancecls_id)
    assign = _get_assignment(request, lecture.assign_id, mark=True)
    students = list(lecture.students().select_related('user').order_by(*ROLL_ORDER))

    if request.method == 'POST':
        records = []
        for stu in students:
            value = request.POST.get('status_%d' % stu.id)
            if value in ('present', 'absent'):
                records.append(Attendance(course=assign.course, student=stu, date=lecture.date,
                                          attendanceclass=lecture, status=value == 'present'))
        with transaction.atomic():
            # Replace this lecture's records for the submitted students; this also
            # clears duplicates left behind by older versions of the app.
            lecture.attendance_set.filter(student__in=[r.student for r in records]).delete()
            Attendance.objects.bulk_create(records)
            lecture.status = 1
            lecture.save(update_fields=['status'])
        present = sum(1 for r in records if r.status)
        messages.success(request, 'Attendance saved for %s: %d present, %d absent.'
                         % (lecture.date.strftime('%d %b'), present, len(records) - present))
        return redirect('attendance-attendance_date', assign_id=assign.id)

    existing = {a.student_id: a.status for a in lecture.attendance_set.all()}
    rows = [{'student': stu, 'present': existing.get(stu.id, True)} for stu in students]
    context = {
        'title': 'Take attendance',
        'assign': assign,
        'lecture': lecture,
        'rows': rows,
        'num_present': sum(1 for r in rows if r['present']),
    }
    return render(request, 'attendance/attendance.html', context)


@staff_required
@require_POST
def delete_lecture(request, attendancecls_id):
    lecture = get_object_or_404(AttendanceClass, pk=attendancecls_id)
    assign = _get_assignment(request, lecture.assign_id, mark=True)
    lecture.delete()
    messages.success(request, 'Lecture on %s was deleted.' % lecture.date.strftime('%d %b %Y'))
    return redirect('attendance-attendance_date', assign_id=assign.id)


@staff_required
def report(request, assign_id):
    assign = _get_assignment(request, assign_id)
    rows, total_lectures = assignment_report(assign)

    if request.GET.get('format') == 'csv':
        response = HttpResponse(content_type='text/csv')
        filename = slugify('%s %s attendance' % (assign.cls.class_name, assign.course.code))
        response['Content-Disposition'] = 'attachment; filename="%s.csv"' % filename
        writer = csv.writer(response)
        writer.writerow(['Roll no', 'Name', 'Email', 'Present', 'Lectures', 'Percent'])
        for row in rows:
            stu = row['student']
            writer.writerow([stu.roll_no or '', stu.user.full_name, stu.user.email,
                             row['present'], row['total'],
                             '' if row['percent'] is None else row['percent']])
        return response

    with_data = [r['percent'] for r in rows if r['percent'] is not None]
    context = {
        'title': 'Attendance report',
        'assign': assign,
        'rows': rows,
        'total_lectures': total_lectures,
        'average': round(sum(with_data) / len(with_data)) if with_data else None,
        'num_short': sum(1 for r in rows if r['short']),
    }
    return render(request, 'attendance/report.html', context)
