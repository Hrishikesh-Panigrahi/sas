from django.contrib.auth.models import User
from django.db import models
from course.models import  Course


# Create your models here.

class student(models.Model):
    
    user = models.OneToOneField(User, on_delete=models.CASCADE)    
    # name =models.CharField(max_length=30)
    # div = models.CharField(max_length=2)
    department = models.CharField(max_length=100, null=True)
    roll_no=models.IntegerField()
    DOB=models.DateField()
    address=models.TextField()
    # email= models.EmailField()
    # id = (str(roll_no)+str(DOB))
    #attendance=something
    id = models.BigAutoField(primary_key=True)
    course=models.ManyToManyField("course.Course", verbose_name=("Enrolled Course"))

    def __str__(self):
        return str(self.id) + " " +self.user.username 


    
   
    
    
    
    
    
    
    
    
    
    
    
    
    
        
        
        
        
        
        
        
    
    

    
    
    
    

