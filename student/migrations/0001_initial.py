# Generated by Django 4.0.5 on 2022-06-09 12:35

from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('course', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='student',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=30)),
                ('div', models.CharField(max_length=2)),
                ('rollno', models.IntegerField()),
                ('DOB', models.DateField()),
                ('address', models.TextField()),
                ('email', models.EmailField(max_length=254)),
                ('course', models.ManyToManyField(to='course.course', verbose_name='Enrolled Course')),
            ],
        ),
    ]
