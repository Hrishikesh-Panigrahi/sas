from django import forms
from cls.models import Class
from student.models import student
from course.models import Course

department_choices = [
        ('Computer Engineering', 'Computer Engineering'),
        ('Electronics and Telecommunication Engineering',
         'Electronics and Telecommunication Engineering'),
        ('Information Technology', 'Information Technology'),
        ('Mechanical Engineering', 'Mechanical Engineering'),
    ]

#Course_choices = [ (c.id ,c.name) for c in Course.objects.all()]


class ClassCreateForm(forms.Form):
    name = forms.CharField(label='Class Name')
    #course= forms.ChoiceField(label='Course', choices=Course_choices)
    
    
    
    def __init__(self, *args, **kwargs):
        t = kwargs.pop('teachers', None)
        s = kwargs.pop('students', None)
        co = kwargs.pop('course', None)
        super(ClassCreateForm, self).__init__(*args, **kwargs)
        self.fields['teacher'] = forms.ModelChoiceField(queryset=t, required=False)
        self.fields['students'] = forms.ModelMultipleChoiceField(queryset=s, required=False, widget=forms.CheckboxSelectMultiple)
        self.fields['course'] = forms.ModelMultipleChoiceField(queryset=co, required=False, widget=forms.CheckboxSelectMultiple)

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