from django.shortcuts import redirect, render
from django.http import HttpResponse
from .forms import UserForm, TeacherForm
from django.contrib.auth.models import User
from .models import TeacherProfile
from django.contrib.auth.forms import UserCreationForm


#ek bhi print sTATEMETN NOT WORKIGN
def register(request):
    page = 'User'
    form= UserCreationForm()  #USer Model - form
    form1=TeacherForm()     #teacher model - form1
    print('h341')
    if request.method == 'POST':
        form=UserCreationForm(request.POST)
        print('h1')
        if form.is_valid():
            # username = form.fields['username']
            user = form.save(commit=False)    #freezing user model and saving the values in user
            # form.save()
            print('h2')
            profile = user.username    #taking user.username value
            # profile = username
            print('h3')
            user.save()
            form1=TeacherForm(instance=profile)
            print('h4')
            if request.method == 'POST':
                form1=TeacherForm(request.POST, instance=profile)
                print('h5')
                if form1.is_valid():
                    form1.save() 
                    print('h6')
                    return redirect('/FacultyRegister')

                
    context={'form':form, 'form1': form1, 'page':page}
    return render(request, 'users/register.html', context)
    




# def Teacherdetails(request,pk):
#     page= 'Details'
#     profile = User.objects.get(id=pk)
    
#     context={'form1':form1, 'page':page}
#     return render(request, 'users/register.html', context)