from django.shortcuts import render

# Create your views here.
def register(request):
    context = {}
    return render(request, 'student/studentRegister.html ' , context)
