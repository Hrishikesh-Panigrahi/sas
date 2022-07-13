from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from student.models import student
from .models import Assign_cls, AttendanceClass
from course.models import Course


def index(request):
   Udept = request.user.department
   course = Course.objects.filter(dept=Udept)
   stu = student.objects.filter(user__department=Udept)
   context = {'student': stu,
               'title': 'CourseSelection',
               'course': course,
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

   return render(request, 'attendance/index.html', context)
