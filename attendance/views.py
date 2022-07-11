# from django.shortcuts import render

# # Create your views here.


# def index(request):
    
#     return render(request, 'attendance/index.html')



# from django.shortcuts import render

# # Create your views here.


# def index(request):
    
#     return render(request, 'attendance/index.html')

from django.shortcuts import render
from django.http import HttpResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.forms import UserCreationForm
from django.shortcuts import render, redirect
from student.models import student
# from timetable.models import timetable
# Attendance views.py
# Create your views here.




def index(request):
     stu = student.objects.all()
    #  tt=timetable.objects.all()

     

    
     
  
     context = {'student': stu,
                'title' : 'Students'          
                
     }      
     if request.method == 'post':
        student_id = request.POST['student_id']
        status = request.POST['status']
        student_obj = student.objects.get(id=student_id)
        student_obj.status = status
        student_obj.save()
        return HttpResponse('success')

     else:
        return render(request, 'attendance/index.html')