from django.shortcuts import redirect, render
from django.http import HttpResponse

from cls.filters import StudentFilter
from .forms import ClassCreateForm, ClassUpdateForm
from .models import Class
from student.models import student

# Create your views here.

def create(request):
    form = ClassCreateForm(request.POST or None)
    context = {
        'form': form
    }
    if request.method == 'POST':
        form = ClassCreateForm(request.POST)
        if form.is_valid():
            body = request.POST.dict()
            students = dict(request.POST)['students']
            c = Class(class_name=body['name'], department=body['department'])
            c.save()
            for obj in students:
                s = student.objects.get(pk=obj)
                s.cls = c
                s.save()
    return render(request, 'cls/form.html', context)


def update(request, id):
    print(request.GET)
    c = Class.objects.get(pk=id)
    in_class = student.objects.filter(cls=c)
    out_class = student.objects.exclude(cls=c)
    inStudentFilter = StudentFilter(request.GET, queryset=in_class)
    in_class = inStudentFilter.qs

    outStudentFilter = StudentFilter(request.GET, queryset=out_class)
    out_class = outStudentFilter.qs
    
    form = ClassUpdateForm(request.POST or None, in_class=in_class, out_class=out_class)
    context = {
        "form":form,
        "filter1": inStudentFilter
    }
    return render(request, 'cls/form.html', context)