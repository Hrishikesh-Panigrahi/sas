from django import forms
from student.models import student

department_choices = [
        ('Computer Engineering', 'Computer Engineering'),
        ('Electronics and Telecommunication Engineering',
         'Electronics and Telecommunication Engineering'),
        ('Information Technology', 'Information Technology'),
        ('Mechanical Engineering', 'Mechanical Engineering'),
    ]

class ClassCreateForm(forms.Form):
    name = forms.CharField()
    department = forms.ChoiceField(choices=department_choices)
    students = forms.ModelMultipleChoiceField(queryset=student.objects.all(),widget=forms.CheckboxSelectMultiple)

class ClassUpdateForm(forms.Form):
    name = forms.CharField()
    department = forms.ChoiceField(choices=department_choices)
    
    def __init__(self,*args, **kwargs):
        in_class = kwargs.pop('in_class', None)
        out_class = kwargs.pop('out_class', None)
        super(ClassUpdateForm, self).__init__(*args, **kwargs)
        self.fields['students in class'] = forms.ModelMultipleChoiceField(queryset=in_class,widget=forms.CheckboxSelectMultiple)
        self.fields['students not in class'] = forms.ModelMultipleChoiceField(queryset=out_class,widget=forms.CheckboxSelectMultiple)