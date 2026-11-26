import uuid
from django.db import models
from django.conf import settings

class MatchingPolicy(models.Model):
    configuration=models.JSONField()
    created_by=models.ForeignKey(settings.AUTH_USER_MODEL,on_delete=models.SET_NULL,null=True)
    created_at=models.DateTimeField(auto_now_add=True)

class RecommendationRun(models.Model):
    id=models.UUIDField(primary_key=True,default=uuid.uuid4,editable=False)
    draft=models.ForeignKey('nlp.ConsultationDraft',on_delete=models.PROTECT,related_name='recommendations')
    policy=models.ForeignKey(MatchingPolicy,on_delete=models.PROTECT,null=True)
    created_at=models.DateTimeField(auto_now_add=True)
    result=models.JSONField(default=dict)
    class Meta:
        ordering=['-created_at','-id']
