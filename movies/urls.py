from django.urls import path
from . import views

urlpatterns = [
     path('',views.movie_list,name='movie_list'),
     path('<int:movie_id>/theatres',views.theatre_list,name='theatre_list'),
     path('theatre/<int:theatre_id>/seats/book/',views.book_seats,name='book_seats'),
]
