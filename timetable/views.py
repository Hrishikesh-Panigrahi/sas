# from django.http import HttpResponse, HttpResponseRedirect
# from django.views import View
from unicodedata import name
from django.http import JsonResponse
from django.shortcuts import render
from .models import TimeTable

def read_file(path):
    file = open(path, "r")
    data = file.read()
    file.close()
    return data

def createTT(request):
    context = {
        'title': 'Timetable',
        'page': 'createTT',
    }
    
    if request.user.is_classteacher:
        
        print(request.method=='GET')
        tt = TimeTable.objects.get_or_create(user = request.user)
                
        if request.method == 'POST':
        
            # tt = TimeTable()
            name = request.POST('course1')

            tt.name=name
            tt.save()
            print(tt)
            
            return JsonResponse("saved", safe=False)

        # read_file('')
        # with open('path to json', 'r') as f:
        #     my_json_obj = json.load(f)

    return render(request, 'timetable/tt.html', context)

def updateTT(request):
    context = {
        'title': 'Timetable',
        'page': 'updateTT',
    }
    read_file('static/js/timetable.js')
    return render(request, 'timetable/tt.html', context)