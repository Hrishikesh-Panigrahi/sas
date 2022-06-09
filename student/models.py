from pyexpat import model
from django.db import models
from course.models import  Course

# Create your models here.

class student(models.Model):
    
        
    name=models.CharField(max_length=30)
    div=models.CharField(max_length=2)
    rollno=models.IntegerField()
    DOB=models.DateField()
    address=models.TextField()
    email=models.EmailField()
    id=(str(rollno)+str(DOB))
    #attendance=something
    course=models.ManyToManyField("course.Course", verbose_name=("Enrolled Course"))
   
    
   
    
    
    
    
    
    
    
    
    
    
    
    
    
        
        
        
        
        
        
        
    
    

    
    
    
    

