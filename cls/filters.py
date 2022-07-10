from dataclasses import fields
from django import forms
import django_filters
from course.models import Course
from student.models import student

class StudentFilter(django_filters.FilterSet):
    f_name = django_filters.CharFilter(field_name='user__first_name', label='First Name', widget=forms.TextInput(attrs={'class': 'test', 'form':'filter-form'}))
    l_name = django_filters.CharFilter(field_name='user__last_name', label='Last Name', widget=forms.TextInput(attrs={'class': 'test', 'form':'filter-form'}))

    class Meta:
        model = student
        fields = ['f_name', 'l_name', 'id']
        
class CourseFilter(django_filters.FilterSet):
    c_code = django_filters.CharFilter(field_name='code', label='Code', widget=forms.TextInput(attrs={'class': 'test', 'form':'filter-form'}))
    c_scheme = django_filters.CharFilter(field_name='scheme', label='Scheme', widget=forms.TextInput(attrs={'class': 'test', 'form':'filter-form'}))
    c_name= django_filters.CharFilter(field_name='name', label='Name', widget=forms.TextInput(attrs={'class': 'test', 'form':'filter-form'}))
    c_sem= django_filters.CharFilter(field_name='sem', label='Sem', widget=forms.TextInput(attrs={'class': 'test', 'form':'filter-form'}))
    class Meta:
        model =Course
        fields = ['c_code', 'c_scheme','c_name','c_sem']        