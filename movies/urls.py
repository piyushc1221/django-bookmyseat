from django.urls import path
from . import views

urlpatterns = [
     path('',views.movie_list,name='movie_list'),
     path('<int:movie_id>/theatres',views.theatre_list,name='theatre_list'),
     path('theatre/<int:theatre_id>/seats/book/',views.book_seats,name='book_seats'),
     path('theatre/<int:theatre_id>/seats/confirm/',views.confirm_booking,name='confirm_booking'),
     path('theatre/<int:theatre_id>/seats/status/',views.seat_status,name='seat_status'),
     path('payments/<int:payment_id>/checkout/',views.payment_checkout,name='payment_checkout'),
     path('payments/callback/',views.payment_callback,name='payment_callback'),
     path('payments/<int:payment_id>/cancel/',views.payment_cancel,name='payment_cancel'),
     path('payments/razorpay/webhook/',views.razorpay_webhook,name='razorpay_webhook'),
]
