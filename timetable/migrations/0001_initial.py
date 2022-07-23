# Generated by Django 4.0.5 on 2022-07-23 07:15

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('cls', '__first__'),
        ('course', '__first__'),
    ]

    operations = [
        migrations.CreateModel(
            name='TimeTable',
            fields=[
                ('id', models.BigAutoField(primary_key=True, serialize=False)),
                ('lec_type', models.CharField(choices=[('Lecture', 'Lecture'), ('Lab', 'Lab')], max_length=7)),
                ('batch', models.CharField(choices=[('All', 'All'), ('A', 'A'), ('B', 'B'), ('C', 'C')], max_length=3)),
                ('day', models.CharField(choices=[('Monday', 'Monday'), ('Tuesday', 'Tuesday'), ('Wednesday', 'Wednesday'), ('Thursday', 'Thursday'), ('Friday', 'Friday')], max_length=9)),
                ('start_time', models.TimeField()),
                ('end_time', models.TimeField()),
                ('cls', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='cls.class')),
                ('course', models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to='course.course')),
            ],
        ),
    ]
