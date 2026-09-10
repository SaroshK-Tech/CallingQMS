import string
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class Service(models.Model):
    name = models.CharField(max_length=100)
    prefix = models.CharField(max_length=2, unique=True, help_text="1-2 letter prefix like A, B, VIP")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['prefix']

    def __str__(self):
        return f"{self.name} ({self.prefix})"

    def next_ticket_number(self):
        today = timezone.localdate()
        last = (
            Ticket.objects
            .filter(service=self, created_at__date=today)
            .order_by('-number')
            .first()
        )
        return (last.number + 1) if last else 1

    def generate_ticket_number(self):
        num = self.next_ticket_number()
        return f"{self.prefix}{num:03d}"


class Counter(models.Model):
    name = models.CharField(max_length=50, unique=True)
    display_name = models.CharField(max_length=50, blank=True)
    is_active = models.BooleanField(default=True)
    services = models.ManyToManyField(Service, through='CounterService')

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.display_name or self.name


class CounterService(models.Model):
    counter = models.ForeignKey(Counter, on_delete=models.CASCADE)
    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    sequence = models.PositiveIntegerField(default=1, help_text="Order in the service path")

    class Meta:
        ordering = ['sequence']
        unique_together = ['counter', 'service']

    def __str__(self):
        return f"{self.counter} - {self.service} (seq {self.sequence})"


class CounterUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='counter_profile')
    counter = models.ForeignKey(Counter, on_delete=models.CASCADE, related_name='users')

    def __str__(self):
        return f"{self.user.username} @ {self.counter}"


class Ticket(models.Model):
    class Status(models.TextChoices):
        WAITING = 'WAITING', 'Waiting'
        CALLED = 'CALLED', 'Called'
        IN_PROGRESS = 'IN_PROGRESS', 'In Progress'
        COMPLETED = 'COMPLETED', 'Completed'
        CANCELLED = 'CANCELLED', 'Cancelled'

    service = models.ForeignKey(Service, on_delete=models.CASCADE)
    ticket_number = models.CharField(max_length=10)
    number = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.WAITING)
    current_counter = models.ForeignKey(Counter, null=True, blank=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)
    called_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.ticket_number

    def save(self, *args, **kwargs):
        if not self.ticket_number and self.service:
            self.ticket_number = self.service.generate_ticket_number()
            self.number = self.service.next_ticket_number()
        super().save(*args, **kwargs)


class TicketCall(models.Model):
    ticket = models.ForeignKey(Ticket, on_delete=models.CASCADE, related_name='calls')
    counter = models.ForeignKey(Counter, on_delete=models.CASCADE)
    called_at = models.DateTimeField(auto_now_add=True)
    recalled = models.BooleanField(default=False)
    served = models.BooleanField(default=False, help_text="True when this counter finished (Done) the ticket")

    class Meta:
        ordering = ['-called_at']

    def __str__(self):
        return f"{self.ticket} at {self.counter}"


class Advertisement(models.Model):
    title = models.CharField(max_length=200)
    image = models.ImageField(upload_to='ads/', null=True, blank=True)
    video = models.FileField(upload_to='ads/', null=True, blank=True)
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['order', '-created_at']

    def __str__(self):
        return self.title
