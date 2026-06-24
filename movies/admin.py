from django.contrib import admin
from .models import Movie,Theatre,Seat,Booking,PaymentTransaction,PaymentWebhookEvent

@admin.register(Movie)
class MovieAdmin(admin.ModelAdmin):
    list_display=['name','rating','cast','description' ]
    
@admin.register(Theatre)
class theatreAdmin(admin.ModelAdmin):
    list_display=['name','movie','time' ]
    
@admin.register(Seat)
class seatAdmin(admin.ModelAdmin):
    list_display=['theatre','seat_no','is_booked','reserved_by','reserved_until', ]
    
@admin.register(Booking)
class bookingAdmin(admin.ModelAdmin):
    list_display=['user','seat','movie','theatre','payment','booked_at' ]

@admin.register(PaymentTransaction)
class paymentTransactionAdmin(admin.ModelAdmin):
    list_display=['provider_order_id','provider_payment_id','user','theatre','amount','status','expires_at' ]
    readonly_fields=['created_at','updated_at' ]

@admin.register(PaymentWebhookEvent)
class paymentWebhookEventAdmin(admin.ModelAdmin):
    list_display=['event_id','event_type','payment','received_at' ]
    
