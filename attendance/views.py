from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.shortcuts import render, redirect
from student.models import student
from users.models import TeacherProfile
from .models import Assign_cls, AttendanceClass
from course.models import Course
from cls.models import Class


def attendanceclass(request, pk):
   context={}
   teacher = TeacherProfile.objects.get(user__id=pk)
   teachercls = Assign_cls.objects.filter(teacher__user__id = pk).distinct()
   print(teachercls)

   cls = Class.objects.all()  #for testing

   context = { 'title': 'ClassSelection',
               'course': teacher.course.all(),
               'teacherprofile': teacher.user.id,
               'teachercls': teachercls,
               'cls':cls
               }
   
   # dic={}
   for i in teachercls:
      context.update({i.cls.class_name : i.cls})
      # print(i.cls.class_name)
      # context[i.cls.class_name].append(i.cls)
      print(context)
      # dic[i]=i.cls
      # print(dic)
   # context.update({'dic': dic})
   # print(context)


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


def attendancecourse(request, pk, co):
   teachercourse = Assign_cls.objects.filter(teacher__user__id = pk)
   t = teachercourse.filter(course__id = co)
   print(t)
   
   context={'title': 'CourseSelection',
            'course':t
            }
   
   return render(request, 'attendance/class_course_selection.html', context)

