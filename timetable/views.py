# from django.http import HttpResponse, HttpResponseRedirect
# from django.views import View
import json
import os
from unicodedata import name
from django.http import JsonResponse
from django.shortcuts import render
# from .models import TimeTable
from cls.models import Class

_path = os.path.join(os.getcwd(), 'static', 'tables')

def read_file(_path):
    file = open(_path, "r")
    data = file.read()
    file.close()
    return data

def test_C(request):
    time_slot = ["08:00-09:00", "09:00-10:00", "10:00-11:00", "11:15-12:15", \
    "12:15-13:15", "14:00-15:00", "15:00-16:00", "16:00-17:00"];
    if request.method == 'POST':
        body = json.loads(request.body)
        with open (os.path.join(_path, '{}_weekly.json'.format(body['class'])), 'w') as fp:
            json.dump(body, fp, indent=4)
        return JsonResponse({"msg":"updated"})
    context = {
        'title': 'tt_test',
        'page': 'test',
    }
    try:
        f = open(os.path.join(_path, '{}_weekly.json'.format('class_id')))
        table = json.loads(f.read())
        schedule = table['schedule']
        schedule_keys = list(schedule.keys())
        Formatted_Schedule=[]
        for key, value in schedule.items():
            for i in range(len(value['slots'])):
                value['slots'][i]['start_time'] = time_slot[value['slots'][i]['time'] % 8].split('-')[0] 
                value['slots'][i]['end_time'] = time_slot[value['slots'][i]['time'] % 8].split('-')[1]              
                value['slots'][i]['time'] = value['slots'][i]['time'] % 8
                value['slots'][i]['weekday'] = key
                value['slots'][i]['weekday_id'] = schedule_keys.index(key)
                # vertical check
                if i-8 >= 0 and value['slots'][i-8]['course'] == value['slots'][i]['course']:
                    continue
                # horizontal check
                if i-1 >= 0 and value['slots'][i-1]['course'] == value['slots'][i]['course'] and (i-1)%8 != 2 and (i-1)%8 != 4 and (i-1)%8 != 7:
                    # rowspan check not implemented
                    Formatted_Schedule[-1]['end_time'] = time_slot[value['slots'][i]['time'] % 8].split('-')[1]
                    continue                    
                # fix batch number 
                if i+8 < 24 and value['slots'][i]['course'] != value['slots'][i+8]['course']:
                    if i < 8:
                        value['slots'][i]['batch'] = "A"
                    elif i< 16:
                        value['slots'][i]['batch'] = "B"
                if i >= 16 and value['slots'][i]['course'] != value['slots'][i-8]['course']:
                        value['slots'][i]['batch'] = "C"
                Formatted_Schedule.append(value['slots'][i])
        context['json'] = table
        context['table'] = Formatted_Schedule
    except:
        table = None
    return render(request, 'timetable/create.html', context)

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
        with open (os.path.join(_path, '{}_static.json'.format(body['class'])), 'w') as fp:
            json.dump(body, fp, indent=4)
        with open (os.path.join(_path, '{}_weekly.json'.format(body['class'])), 'w') as fp:
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