from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

# Create your models here.

class SymptomEntry(models.Model):
    """
    Model to store user symptom entries with severity levels and suggestions.
    """
    # Severity choices
    SEVERITY_CHOICES = [
        ('Low', 'Low'),
        ('Medium', 'Medium'),
        ('High', 'High'),
    ]
    
    # Foreign key to User model
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='symptom_entries')
    
    # Symptom description
    symptom_text = models.TextField(help_text="Describe your symptoms")
    
    # Severity level
    severity = models.CharField(max_length=10, choices=SEVERITY_CHOICES, default='Low')
    
    # Predefined suggestion based on severity
    suggestion = models.TextField(help_text="Suggestion based on severity")
    
    # Timestamp
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-created_at']  # Most recent first
        verbose_name_plural = "Symptom Entries"
    
    def __str__(self):
        return f"{self.user.username} - {self.symptom_text[:50]} ({self.severity})"
