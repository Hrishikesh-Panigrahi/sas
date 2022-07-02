from dataclasses import fields
from django import forms
import django_filters
from student.models import student

class StudentFilter(django_filters.FilterSet):
    f_name = django_filters.CharFilter(field_name='user__first_name', label='First Name', widget=forms.TextInput(attrs={'class': 'test', 'form':'filter-form'}))
    l_name = django_filters.CharFilter(field_name='user__last_name', label='Last Name', widget=forms.TextInput(attrs={'class': 'test', 'form':'filter-form'}))

    class Meta:
        model = student
        fields = ['f_name', 'l_name', 'id']