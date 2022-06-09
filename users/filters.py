import django_filters
from course.models import Course


class CourseFilter(django_filters.FilterSet):
    class Meta:
        model = Course
        fields = ['code', 'scheme', 'name', 'sem']
