# api/models.py

from django.db import models

class Meeting(models.Model):
    date = models.DateField()
    topic = models.CharField(max_length=200)
    summary = models.TextField()

    def __str__(self):
        return self.topic
