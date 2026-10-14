from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse

from course.forms import CourseForm
from course.models import Course
from attendance.models import AttendanceClass
from sas.permissions import hod_required, in_department, linked_records, staff_required


def _courses_for(user):
    return in_department(Course.objects.all(), user, 'dept')


@staff_required
def index(request):
    context = {
        'title': 'Courses',
        'department': request.user.department,
        'courses': _courses_for(request.user).order_by('sem', 'code'),
    }
    return render(request, 'course/courses.html', context)


@hod_required
def create(request):
    form = CourseForm(request.POST or None, dept=request.user.department)
    if request.method == 'POST' and form.is_valid():
        course = form.save()
        messages.success(request, 'Course "%s" was added.' % course.name)
        if 'add_another' in request.POST:
            return redirect('course-create')
        return redirect('chome')
    context = {'title': 'Add course', 'form': form, 'type': 'Create'}
    return render(request, 'course/CourseForm.html', context)


@hod_required
def update(request, id):
    course = get_object_or_404(_courses_for(request.user), pk=id)
    form = CourseForm(request.POST or None, instance=course, dept=request.user.department)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Course "%s" was updated.' % course.name)
        return redirect('chome')
    context = {'title': 'Edit course', 'form': form, 'type': 'Update', 'course': course}
    return render(request, 'course/CourseForm.html', context)


@hod_required
def delete(request, id):
    course = get_object_or_404(_courses_for(request.user), pk=id)
    if request.method == 'POST':
        name = course.name
        course.delete()
        messages.success(request, 'Course "%s" was deleted.' % name)
        return redirect('chome')
    context = {
        'title': 'Delete course',
        'object_name': '%s (%s)' % (course.name, course.code),
        'cancel_url': reverse('course-update', args=[course.id]),
        'consequences': linked_records(
            (course.assign_cls_set.count(), 'class assignment'),
            (AttendanceClass.objects.filter(assign__course=course).count(), 'lecture'),
            (course.attendance_set.count(), 'attendance record'),
        ),
    }
    return render(request, 'confirm_delete.html', context)
