from django.db import models
class Questioninfo(models.Model):
    QuestionId = models.CharField(max_length=100, null=True)
    CreatedBy = models.CharField(max_length=70, null=True)
    CreatedTime = models.DateTimeField(null=True)
    ReviewedBy = models.CharField(max_length=70, null=True)
    ReviewedTime = models.DateTimeField(null=True)
    Approved = models.CharField(max_length=1, null=True)
    Last_Updated = models.DateTimeField(null=True)
    Comments = models.CharField(max_length=200, null=True)

    class Meta:
        db_table = 'questioninfo' 
