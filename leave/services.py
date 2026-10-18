"""Keeps Attendance.excused in step with approved leave."""
from attendance.models import Attendance
from .models import LeaveRequest


def approved_on(students, date):
    """IDs of students (from `students`) with approved leave covering `date`."""
    return set(LeaveRequest.objects.filter(student__in=students, status='approved',
                                           start_date__lte=date, end_date__gte=date)
               .values_list('student_id', flat=True))


def sync_excuses(stu, start, end):
    """Re-derive `excused` for one student's records between two dates.

    An absence is excused when any approved leave covers its lecture's date;
    everything else in the range is not excused.
    """
    leaves = list(LeaveRequest.objects.filter(student=stu, status='approved',
                                              start_date__lte=end, end_date__gte=start))
    records = Attendance.objects.filter(student=stu, attendanceclass__date__range=(start, end))
    excuse, clear = [], []
    for pk, status, date, excused in records.values_list('pk', 'status', 'attendanceclass__date', 'excused'):
        covered = not status and any(l.start_date <= date <= l.end_date for l in leaves)
        if covered and not excused:
            excuse.append(pk)
        elif not covered and excused:
            clear.append(pk)
    Attendance.objects.filter(pk__in=excuse).update(excused=True)
    Attendance.objects.filter(pk__in=clear).update(excused=False)
    return len(excuse)


def excuse_lecture(lecture):
    """After attendance is saved, excuse absences of students on approved leave."""
    on_leave = approved_on(lecture.attendance_set.values('student'), lecture.date)
    lecture.attendance_set.update(excused=False)
    if on_leave:
        lecture.attendance_set.filter(student__in=on_leave, status=False).update(excused=True)
    return on_leave


def lectures_in_range(leave):
    """Lectures the student is expected at during the leave (marked or not)."""
    from attendance.models import AttendanceClass
    stu = leave.student
    if not stu.cls_id:
        return AttendanceClass.objects.none()
    qs = AttendanceClass.objects.filter(assign__cls=stu.cls_id, date__range=(leave.start_date, leave.end_date))
    return qs.filter(batch__in=['All', stu.batch]) if stu.batch else qs.filter(batch='All')
