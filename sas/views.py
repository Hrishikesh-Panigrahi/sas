from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from attendance.models import Assign_cls, AttendanceClass
from attendance.stats import student_summary, students_below_threshold
from insights.forecast import forecasts, warnings
from cls.models import Class
from course.models import Course
from sas.permissions import in_department
from student.models import student
from timetable.models import TimeTable
from timetable.substitutes import todays_cover
from users.models import TeacherProfile


@login_required
def index(request):
    user = request.user
    today = timezone.localdate()
    context = {'title': 'Dashboard', 'today': today}

    if user.is_student:
        profile = student.objects.filter(user=user).select_related('cls').first()
        context['profile'] = profile
        context['summary'] = student_summary(profile) if profile else None
        if profile:
            context['forecast'] = forecasts(student.objects.filter(pk=profile.pk)).get(profile.pk)
            context['short_courses'] = sum(1 for c in context['summary']['courses'] if c['short'])
            context['leaves'] = profile.leave_requests.order_by('-created_at')[:4]
        return render(request, 'dashboard_student.html', context)

    # Teaching: today's timetable, lectures still to be marked, my classes.
    assignments = list(Assign_cls.objects.filter(teacher__user=user)
                       .select_related('cls', 'course'))
    by_pair = {(a.cls_id, a.course_id): a for a in assignments}
    slots = (TimeTable.objects.filter(day=today.strftime('%A'),
                                      cls__in={a.cls_id for a in assignments})
             .select_related('cls', 'course').order_by('start_time'))
    marked = {
        (lec.assign_id, lec.period, lec.batch): lec
        for lec in AttendanceClass.objects.filter(assign__in=assignments, date=today)
    }
    today_slots = []
    for slot in slots:
        assign = by_pair.get((slot.cls_id, slot.course_id))
        if assign:
            today_slots.append({'slot': slot, 'assign': assign,
                                'lecture': marked.get((assign.id, slot.period, slot.batch))})
    for cover in todays_cover(user, today):
        lecture = AttendanceClass.objects.filter(assign=cover['assign'], date=today, period=cover['slot'].period,
                                                 batch=cover['slot'].batch).first()
        today_slots.append({'slot': cover['slot'], 'assign': cover['assign'], 'lecture': lecture,
                            'cover_for': cover['sub'].absent_teacher.user.full_name})
    today_slots.sort(key=lambda item: item['slot'].start_time)

    pending = (AttendanceClass.objects.filter(assign__in=assignments, status=0, date__lte=today)
               .select_related('assign__cls', 'assign__course').order_by('-date'))
    context.update({
        'assignments': assignments,
        'today_slots': today_slots,
        'pending': pending[:6],
        'pending_count': pending.count(),
    })

    if user.can_manage_students:
        dept_students = in_department(student.objects.filter(user__is_staff=False),
                                      user, 'user__department')
        below = students_below_threshold(dept_students)
        upcoming = warnings(dept_students.filter(cls__isnull=False))
        context.update({
            'counts': {
                'courses': in_department(Course.objects.all(), user, 'dept').count(),
                'teachers': in_department(TeacherProfile.objects.filter(user__is_staff=True),
                                          user, 'user__department').count(),
                'students': dept_students.count(),
                'classes': in_department(Class.objects.all(), user).count(),
                'below': len(below),
                'warnings': len(upcoming),
            },
            'low_attendance': below[:8],
            'warnings': upcoming[:8],
        })
    elif assignments:
        upcoming = warnings(student.objects.filter(cls__in={a.cls_id for a in assignments}),
                            courses={a.course_id for a in assignments})
        context.update({'warnings': upcoming[:8], 'warning_count': len(upcoming)})

    return render(request, 'dashboard.html', context)
