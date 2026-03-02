from django.db import models

# Create your models here.
from django.db import models

class Crop(models.Model):
    name = models.CharField(max_length=100)

class Disease(models.Model):
    crop = models.ForeignKey(Crop, on_delete=models.CASCADE)
    affected_part = models.CharField(max_length=100)
    name = models.CharField(max_length=100)
    solution = models.TextField()