from django.http import HttpResponse, HttpResponseRedirect
from django.views import View
from django.shortcuts import redirect, render
# Create your views here.



def createTT(request):
    form = CourseForm()
    context = {
        'title': 'Timetable',
        'type': 'createTT',
    }
    return render(request, 'timetable/tt.html', context)

def updateTT(request):
    context = {
        'title': 'Timetable',
        'type': 'UpdateTT',
    }
    return render(request, 'timetable/tt-editable.html', context)