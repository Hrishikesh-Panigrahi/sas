from django.db import models
from course.models import Course
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.models import User
from django.contrib.auth.base_user import BaseUserManager


class CustomUserManager(BaseUserManager):
    
    # use this function to save users
    def create_user(self, email, password, is_active=True, is_staff=False, is_superuser=False, is_classteacher= False, is_hod = False,first_name=None,last_name=None,middle_name=None):

        # create and save user with email and password

        if not email:
            raise ValueError('The Email must be set ')

        if not password:
            raise ValueError('Password is mandatory')


        User = self.model(
            email=self.normalize_email(email)
        )
        User.is_active = is_active
        User.is_staff = is_staff
        User.is_superuser = is_superuser
        User.is_classteacher=is_classteacher
        User.is_hod =is_hod
        User.set_password(password)
        User.first_name=first_name
        User.last_name=last_name
        User.middle_name=middle_name
        
        
        User.save(using=self.db)
        return User

    # use this function to save teachers
    # for subject teachers
    def create_staffuser(self, email, password):
        User = self.create_user(
            email, 
            password=password, 
            is_staff=True,
            is_superuser=False,
            is_classteacher= False,
            is_hod = False
            )
        return User

    # use this function to save admins
    # for admin
    def create_superuser(self, email, password):
        User = self.create_user(
            email,
            password=password,
            is_staff=True, 
            is_superuser=True,
            is_classteacher= True,
            is_hod = True
            )
        return User


# User model start 
class User(AbstractUser):
    # id = models.CharField(max_length=50, unique=True)
    username = None
    first_name = models.CharField(max_length=50, null=True)
    last_name = models.CharField(max_length=50, null=True)
    middle_name = models.CharField(max_length=50, null=True)
    email = models.EmailField(max_length=255, unique=True)
    created_on = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    is_classteacher = models.BooleanField(default=False)
    is_hod = models.BooleanField(default=False)
    
    # profile_img = models.ImageField()

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []
    objects = CustomUserManager()

    def __str__(self):
        return str(self.email)

# User model end

class TeacherProfile(models.Model):

    department_choices = [
        ('Computer Engineering', 'Computer Engineering'),
        ('Electronics and Telecommunication Engineering',
         'Electronics and Telecommunication Engineering'),
        ('Information Technology', 'Information Technology'),
        ('Mechanical Engineering', 'Mechanical Engineering'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    # name = models.CharField(max_length=50)
    id = models.BigAutoField(primary_key=True)
    department = models.CharField(
        max_length=50, blank=True, null=True, choices=department_choices)
    course = models.ManyToManyField(Course, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    def __str__(self):
        return str(self.id) + ' ' + self.user.first_name + ' ' + self.user.last_name
