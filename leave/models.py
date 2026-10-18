from django.conf import settings
from django.db import models

from student.models import student


class LeaveRequest(models.Model):
    """A student's request to be excused from lectures between two dates.

    Approved leave turns absences in that range into excused absences, which
    don't count against the student's attendance percentage.
    """
    KINDS = [
        ('medical', 'Medical'),
        ('family', 'Family emergency'),
        ('event', 'College event or competition'),
        ('other', 'Other'),
    ]
    STATUSES = [
        ('pending', 'Waiting for approval'),
        ('approved', 'Approved'),
        ('rejected', 'Not approved'),
        ('cancelled', 'Cancelled'),
    ]

    student = models.ForeignKey(student, on_delete=models.CASCADE, related_name='leave_requests')
    kind = models.CharField(max_length=10, choices=KINDS)
    start_date = models.DateField()
    end_date = models.DateField()
    reason = models.TextField(max_length=1000)
    # Small supporting documents (a medical certificate) are kept in the
    # database so they work on hosts without persistent file storage.
    document = models.BinaryField(null=True, blank=True, editable=False)
    document_name = models.CharField(max_length=255, blank=True)
    document_type = models.CharField(max_length=100, blank=True)
    status = models.CharField(max_length=10, choices=STATUSES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, blank=True,
                                    on_delete=models.SET_NULL, related_name='+')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.CharField(max_length=300, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return '%s: %s %s–%s (%s)' % (self.student, self.kind, self.start_date, self.end_date, self.status)

    @property
    def days(self):
        return (self.end_date - self.start_date).days + 1

    @property
    def has_document(self):
        return bool(self.document_name)
