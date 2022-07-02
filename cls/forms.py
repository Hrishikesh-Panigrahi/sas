from dataclasses import fields
from django import forms
from pkg_resources import require
from cls.models import Class
from student.models import student

department_choices = [
        ('Computer Engineering', 'Computer Engineering'),
        ('Electronics and Telecommunication Engineering',
         'Electronics and Telecommunication Engineering'),
        ('Information Technology', 'Information Technology'),
        ('Mechanical Engineering', 'Mechanical Engineering'),
    ]

class ClassCreateForm(forms.Form):
    name = forms.CharField(label='Class Name')
    def __init__(self, *args, **kwargs):
        s = kwargs.pop('students', None)
        super(ClassCreateForm, self).__init__(*args, **kwargs)
        self.fields['students'] = forms.ModelMultipleChoiceField(queryset=s,widget=forms.CheckboxSelectMultiple)

class ClassUpdateForm(forms.ModelForm):
    
    class Meta:
        model = Class
        fields = ['class_name']
    
    def __init__(self,*args, **kwargs):
        in_class = kwargs.pop('in_class', None)
        out_class = kwargs.pop('out_class', None)
        super(ClassUpdateForm, self).__init__(*args, **kwargs)
        self.fields['students in class'] = forms.ModelMultipleChoiceField(queryset=in_class,widget=forms.CheckboxSelectMultiple, required=False)
        self.fields['students not in class'] = forms.ModelMultipleChoiceField(queryset=out_class,widget=forms.CheckboxSelectMultiple, required=False)