from django.contrib import messages
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from attendance.models import Attendance, AttendanceClass
from course.models import Course
from sas.permissions import in_department, linked_records, manager_required, staff_required
from student.models import ROLL_ORDER, student
from users.models import TeacherProfile
from .forms import ClassForm
from .models import Class


def _classes_for(user):
    return in_department(Class.objects.all(), user)


def _form_for(request, instance=None):
    user = request.user
    return ClassForm(
        request.POST or None,
        instance=instance,
        courses=in_department(Course.objects.all(), user, 'dept').order_by('sem', 'code'),
        teachers=in_department(TeacherProfile.objects.filter(user__is_staff=True),
                               user, 'user__department')
        .select_related('user').order_by('user__first_name', 'user__last_name'),
        students=in_department(student.objects.filter(user__is_staff=False),
                               user, 'user__department')
        .select_related('user', 'cls').order_by(*ROLL_ORDER),
    )


@staff_required
def AllClass(request):
    classes = (_classes_for(request.user)
               .select_related('class_teacher__user')
               .annotate(num_students=Count('student', distinct=True),
                         num_courses=Count('assign_cls', distinct=True))
               .order_by('class_name'))
    context = {'title': 'Classes', 'classes': classes}
    return render(request, 'cls/Allclass.html', context)


@staff_required
def detail(request, id):
    cls = get_object_or_404(_classes_for(request.user).select_related('class_teacher__user'), pk=id)
    context = {
        'title': cls.class_name,
        'cls': cls,
        'students': cls.student_set.select_related('user').order_by(*ROLL_ORDER),
        'assignments': (cls.assign_cls_set.select_related('course', 'teacher__user')
                        .annotate(num_lectures=Count('attendanceclass'))
                        .order_by('course__name')),
    }
    return render(request, 'cls/detail.html', context)


@manager_required
def clsCreation(request):
    form = _form_for(request)
    if request.method == 'POST' and form.is_valid():
        cls = form.save(department=request.user.department)
        messages.success(request, 'Class "%s" was created.' % cls.class_name)
        return redirect('class-detail', id=cls.id)
    context = {'title': 'Create class', 'form': form, 'type': 'Create'}
    return render(request, 'cls/form.html', context)


@manager_required
def update(request, id):
    cls = get_object_or_404(_classes_for(request.user), pk=id)
    form = _form_for(request, instance=cls)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Class "%s" was updated.' % cls.class_name)
        if form.kept_courses:
            messages.warning(request, 'Kept %s because attendance has already been recorded for it.'
                             % ', '.join(c.name for c in form.kept_courses))
        return redirect('class-detail', id=cls.id)
    context = {'title': 'Edit class', 'form': form, 'type': 'Update', 'cls': cls}
    return render(request, 'cls/form.html', context)


@manager_required
def delete(request, id):
    cls = get_object_or_404(_classes_for(request.user), pk=id)
    if request.method == 'POST':
        name = cls.class_name
        cls.delete()
        messages.success(request, 'Class "%s" was deleted.' % name)
        return redirect('viewcls')
    lectures = AttendanceClass.objects.filter(assign__cls=cls)
    context = {
        'title': 'Delete class',
        'object_name': cls.class_name,
        'cancel_url': reverse('class-detail', args=[cls.id]),
        'consequences': linked_records(
            (cls.assign_cls_set.count(), 'course assignment'),
            (cls.timetable_set.count(), 'timetable slot'),
            (lectures.count(), 'lecture'),
            (Attendance.objects.filter(attendanceclass__in=lectures).count(), 'attendance record'),
        ),
        'note': 'Students in this class are not deleted; they just become unassigned.',
    }
    return render(request, 'confirm_delete.html', context)
