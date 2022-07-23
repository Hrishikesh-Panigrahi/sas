from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render, redirect, get_object_or_404
from student.models import student
from users.models import TeacherProfile
from .models import Assign_cls, AttendanceClass
from course.models import Course
from cls.models import Class


def attendanceclass(request, pk):
   # teachercls = AttendanceClass.objects.filter(assign__teacher__user__id = pk)
   # teachercls.distinct()   
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


def attendance(request, pk, cls_id):
   return HttpResponse('nice')