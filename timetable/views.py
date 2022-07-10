# from django.http import HttpResponse, HttpResponseRedirect
# from django.views import View
import json
import os
from unicodedata import name
from django.http import JsonResponse
from django.shortcuts import render
# from .models import TimeTable
from cls.models import Class

path = os.path.join(os.getcwd(), 'timetable', 'tables')

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
    # print(request.method)
    # cls = Class.objects.filter(is_timetable=False)
    # print(cls)
    # tt = TimeTable.objects.get(faculty__user__id = request.user.id)
    # print(tt)
    # print(request.body)
    
    if request.method == 'POST':
        body = json.loads(request.body)
        with open (os.path.join(path, '{}_static.json'.format(body['class'])), 'w') as fp:
            json.dump(body, fp, indent=4)
        with open (os.path.join(path, '{}_weekly.json'.format(body['class'])), 'w') as fp:
            json.dump(body, fp, indent=4)
        return JsonResponse({"msg":"saved"})
    
    # commented to test post
    # if request.user.is_classteacher:
        
    #     print(request.method=='GET')
    #     tt = TimeTable.objects.get_or_create(user = request.user)
                
    #     if request.method == 'POST':
        
    #         # tt = TimeTable()
    #         name = request.POST('course1')

    #         tt.name=name
    #         tt.save()
    #         print(tt)
            
    #         return JsonResponse("saved", safe=False)


        # read_file('')
        # with open('path to json', 'r') as f:
        #     my_json_obj = json.load(f)

    return render(request, 'timetable/tt.html', context)

def editTT(request):
    context = {
        'title': 'Timetable',
        'page': 'editTT',
    }
    return render(request, 'timetable/tt.html', context)

def updateTT(request):
    context = {
        'title': 'Timetable',
        'page': 'updateTT',
    }
    return render(request, 'timetable/tt.html', context)

def requests(request):
    context = {
        'title': 'Timetable',
        'page': 'request',
    }
    return render(request, 'timetable/requests.html', context)