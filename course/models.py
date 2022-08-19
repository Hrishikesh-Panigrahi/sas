from django.db import models
# from student.models import student
# from cls.models import Class

# Create your models here.
class Course(models.Model):
    sem_choices = [
        (1, '1'),
        (2, '2'),
        (3, '3'),
        (4, '4'),
        (5, '5'),
        (6, '6'),
        (7, '7'),
        (8, '8')
    ]

    department_choices = [
        ('Computer Engineering', 'Computer Engineering'),
        ('Electronics and Telecommunication Engineering',
         'Electronics and Telecommunication Engineering'),
        ('Information Technology', 'Information Technology'),
        ('Mechanical Engineering', 'Mechanical Engineering'),
    ]

    id = models.BigAutoField(primary_key=True)
    code = models.CharField(max_length=10)
    scheme = models.CharField(max_length=10)
    name = models.CharField(max_length=50)
    dept = models.CharField(
        max_length=50, choices=department_choices, verbose_name='Department')
    sem = models.IntegerField(choices=sem_choices, verbose_name='Semester')
    is_elective = models.BooleanField(default=False)
    dept_level = models.BooleanField(default=True)
    institue_level = models.BooleanField(default=False)
    # Course code
    # Course scheme
    # taught_by = models.ManyToManyField(TeacherProfile)

    def __str__(self):
        return self.name
