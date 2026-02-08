from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.db.models import JSONField

import secrets
import string

def generate_firebase_id():
    chars = string.ascii_letters + string.digits
    return ''.join(secrets.choice(chars) for _ in range(20))

# GigCreation model
default_blank_null = {'blank': True, 'null': True}

class GigCreation(models.Model):
    id = models.CharField(primary_key=True, max_length=20, default=generate_firebase_id, editable=False, unique=True)
    title = models.CharField(max_length=255, blank=True, null=True)
    full_name = models.CharField(max_length=255)
    gig_city = models.CharField(max_length=100, blank=True, null=True)
    gig_state = models.CharField(max_length=100, blank=True, null=True)
    gig_country = models.CharField(max_length=100, blank=True, null=True)
    kreyate_city = models.CharField(max_length=100, blank=True, null=True)
    kreyate_state = models.CharField(max_length=100, blank=True, null=True)
    kreyate_country = models.CharField(max_length=100, blank=True, null=True)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField()
    deadline = models.DateField()
    time = models.TimeField(blank=True, null=True)
    min_price = models.DecimalField(max_digits=10, decimal_places=2)
    max_price = models.DecimalField(max_digits=10, decimal_places=2)
    posted_at = models.DateTimeField(auto_now_add=True)
    description = models.TextField()
    gig_category = models.CharField(max_length=100)
    gig_review = models.TextField(**default_blank_null)
    gig_comment = models.TextField(**default_blank_null)
    gig_kreyate_id = models.IntegerField(**default_blank_null)
    gig_kreyate_name = models.CharField(max_length=255)
    gig_kreyate_review = models.TextField(**default_blank_null)

    kreyate_fee = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    gig_kreyate_fee = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, blank=True, null=True)
    currency = models.CharField(max_length=10, blank=True, null=True)
    method_payment = models.CharField(max_length=50, blank=True, null=True)
    kreyate_phone = models.CharField(max_length=20, blank=True, null=True)
    offers = JSONField(default=list, blank=True, null=True)

    def __str__(self):
        return f"{self.full_name} - {self.gig_category}"
