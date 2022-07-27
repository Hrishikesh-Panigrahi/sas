from django.http import HttpResponseRedirect
from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required

from student.models import student
from users.models import TeacherProfile
from .models import Assign_cls, AttendanceClass
from course.models import Course
from cls.models import Class
from django.utils import timezone

import datetime


def attendanceclass(request, pk):
   teachercls= get_object_or_404(TeacherProfile, user__id=pk)
   context = { 'title': 'ClassSelection',
               'teachercls': teachercls,
               }

   #    try:
   #       if request.POST['courseSelected'] :
   #          c = request.POST['courseSelected']
   #          ass = Assign_cls.objects.get(course__name=c)

   return render(request, 'attendance/class_course_selection.html', context)


def attendance_date(request, assign_id):
   now1 = datetime.date.today()  
   ass = get_object_or_404(Assign_cls, id=assign_id)

   att_list = ass.attendanceclass_set.filter(date__lte = now1).order_by('-date')
   print(att_list)

   context = {'title': 'dates',
               'ass': ass,
               'att_list': att_list}
   return render(request, 'attendance/class_course_selection.html', context)


def stu_list(request, attendancecls_id):
   att_list = get_object_or_404(AttendanceClass, id=attendancecls_id)
   ass = att_list.assign
   cls = ass.cls

   context = {'att': att_list,
               'ass':ass,
               'cls':cls
            }
   if request.method == 'POST':
      print('hello')
      for i, stu in enumerate(cls.student_set.all()):
         print(request.POST[stu.user.email])

   return render(request, 'attendance/attendance.html', context)

# def confirm_attendance(request, attendancecls_id ):
#    att_list = get_object_or_404(AttendanceClass, id=attendancecls_id)
#    ass = att_list.assign
#    cls = ass.cls
   # for i, s in enumerate(cl.student_set.all()):
   #    print(request.POST[s.USN])

   # return HttpResponseRedirect(reverse('attendance-attendance_date', args=(ass.id,)))