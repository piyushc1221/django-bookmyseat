from django.db import models
from django.contrib.auth.models import User

class Movie(models.Model):
    name=models.CharField(max_length=250)
    image=models.ImageField(upload_to="movies/")
    rating=models.DecimalField(max_digits=3,decimal_places=1)
    cast=models.TextField()
    description=models.TextField(blank=True,null=True)

    def __str__(self):
        return self.name
    
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
    
    
    def __str__(self):
        return f'{self.seat_no} in {self.theatre.name}'

class Booking(models.Model):
    user=models.ForeignKey(User,on_delete=models.CASCADE,)
    seat=models.OneToOneField(Seat,on_delete=models.CASCADE,)
    movie=models.ForeignKey(Movie,on_delete=models.CASCADE,)
    theatre=models.ForeignKey(Theatre,on_delete=models.CASCADE,)
    booked_at=models.DateTimeField(auto_now_add=True)

    
    
    def __str__(self):
        return f'booking by {self.user.username} for {self.seat.seat_no} at {self.theatre.name}'