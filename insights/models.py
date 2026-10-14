from django.conf import settings
from django.db import models


class AIInsight(models.Model):
    """A cached Claude analysis, reused while the underlying facts are unchanged."""
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    kind = models.CharField(max_length=30)
    subject_id = models.BigIntegerField(null=True, blank=True)
    fingerprint = models.CharField(max_length=64)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [models.Index(fields=['user', 'kind', 'subject_id'])]

    def __str__(self):
        return '%s %s for %s' % (self.kind, self.subject_id or '', self.user)
