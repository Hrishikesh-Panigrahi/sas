from django.http import HttpResponseRedirect
from django.urls import reverse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required

from student.models import student
from users.models import TeacherProfile
from .models import Assign_cls, Attendance, AttendanceClass
from course.models import Course
from cls.models import Class

from django.utils import timezone
import datetime


def attendanceclass(request, pk):
   teachercls= get_object_or_404(TeacherProfile, user__id=pk)
   context = { 'title': 'ClassSelection',
               'teachercls': teachercls,
               }
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
   co = ass.course

   context = {'att': att_list,
               'ass':ass,
               'cls':cls
            }

   if request.method == 'POST':

      for i, stu in enumerate(cls.student_set.all()):

         stats = request.POST[stu.user.email]
         if stats == 'present':
            s = 'True'
         elif stats == 'absent':
            s = 'False'
         
         if att_list.status == 1:
            att = Attendance.objects.get_or_create(course = co ,student = stu, date = att_list.date, attendanceclass = att_list, status = s)
            
         else:
            att = Attendance(course = co ,student = stu, date = att_list.date, attendanceclass = att_list, status = s)
            att.save()
            att_list.status=1
            att_list.save()
            
      return redirect('/')

   return render(request, 'attendance/attendance.html', context)

def edit_attendance(request, attendancecls_id ):
   att_list = get_object_or_404(AttendanceClass, id=attendancecls_id)
   ass = att_list.assign
   cls = ass.cls
   
   context = {'att': att_list,
               'ass':ass,
               'cls':cls
            }

   return render(request, 'attendance/edit-attendance.html', context)