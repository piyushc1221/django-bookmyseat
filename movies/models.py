from django.db import models
from django.contrib.auth.models import User
from .validators import get_youtube_video_id, validate_youtube_url

class Movie(models.Model):
    name=models.CharField(max_length=250)
    image=models.ImageField(upload_to="movies/")
    rating=models.DecimalField(max_digits=3,decimal_places=1)
    cast=models.TextField()
    description=models.TextField(blank=True,null=True)
    trailer_url = models.URLField(blank=True, null=True, validators=[validate_youtube_url])

    def get_embed_url(self):
        video_id = get_youtube_video_id(self.trailer_url)
        if not video_id:
            return ""

        return f"https://www.youtube-nocookie.com/embed/{video_id}"


class Theatre(models.Model):
    name=models.CharField(max_length=250)
    movie=models.ForeignKey(Movie,on_delete=models.CASCADE,related_name='theatres')
    time=models.DateTimeField()
    
    def __str__(self):
        return f'{self.name} - {self.movie.name} at {self.time}'

class Seat(models.Model):
    theatre=models.ForeignKey(Theatre,on_delete=models.CASCADE,related_name='seats')
    seat_no=models.CharField(max_length=20)
    is_booked= models.BooleanField( default=False )
    reserved_by=models.ForeignKey(User,on_delete=models.SET_NULL,blank=True,null=True,related_name='reserved_seats')
    reserved_at=models.DateTimeField(blank=True,null=True)
    reserved_until=models.DateTimeField(blank=True,null=True,db_index=True)

    def __str__(self):
        return f'{self.seat_no} in {self.theatre.name}'

class Booking(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE,)
    seat=models.OneToOneField(Seat,on_delete=models.CASCADE,)
    movie=models.ForeignKey(Movie,on_delete=models.CASCADE,)
    theatre=models.ForeignKey(Theatre,on_delete=models.CASCADE,)
    booked_at=models.DateTimeField(auto_now_add=True)
    payment=models.ForeignKey('PaymentTransaction',on_delete=models.SET_NULL,blank=True,null=True,related_name='bookings')

    def __str__(self):
        return f'booking by {self.user.username} for {self.seat.seat_no} at {self.theatre.name}'


class PaymentTransaction(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    ]

    user=models.ForeignKey(User,on_delete=models.CASCADE,related_name='payments')
    theatre=models.ForeignKey(Theatre,on_delete=models.CASCADE,related_name='payments')
    seats=models.ManyToManyField(Seat,related_name='payments')
    amount=models.PositiveIntegerField()
    currency=models.CharField(max_length=10,default='INR')
    status=models.CharField(max_length=20,choices=STATUS_CHOICES,default='pending',db_index=True)
    provider_order_id=models.CharField(max_length=100,unique=True)
    provider_payment_id=models.CharField(max_length=100,blank=True,null=True,unique=True)
    provider_signature=models.CharField(max_length=255,blank=True,null=True)
    idempotency_key=models.CharField(max_length=100,unique=True)
    failure_reason=models.TextField(blank=True,null=True)
    created_at=models.DateTimeField(auto_now_add=True)
    updated_at=models.DateTimeField(auto_now=True)
    expires_at=models.DateTimeField(db_index=True)

    def __str__(self):
        return f'{self.provider_order_id} - {self.status}'


class PaymentWebhookEvent(models.Model):
    event_id=models.CharField(max_length=150,unique=True)
    event_type=models.CharField(max_length=100)
    payment=models.ForeignKey(PaymentTransaction,on_delete=models.SET_NULL,blank=True,null=True,related_name='webhook_events')
    received_at=models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.event_type} - {self.event_id}'
