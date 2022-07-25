from multiprocessing import context
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
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

   # for i, s in enumerate(cls.student_set.all()):

   # if request.method == 'POST':
   #    try:
   #       if request.POST['courseSelected'] :
   #          c = request.POST['courseSelected']
   #          print(c)
   #          ass = Assign_cls.objects.get(course__name=c)
   #          print(ass) 
   #    except:
   #          pass
      # return HttpResponse('success')

   return render(request, 'attendance/class_course_selection.html', context)


def attendance(request, pk, assign_id):
   now = timezone.now()
   now1 = datetime.date.today()  
   print(now)
   print(now1)

   ass = get_object_or_404(Assign_cls, id=assign_id)
   print(ass)
   # order_by('-date')
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
   return render(request, 'attendance/attendance.html', context)