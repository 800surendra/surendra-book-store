from django.urls import path
from . import views

app_name = 'books'
urlpatterns = [
    path('', views.BookListView.as_view(), name='list'),
    path('<slug:slug>/', views.book_detail, name='detail'),
]
from django.urls import path
from . import views

app_name = 'books'
urlpatterns = [
    path('', views.BookListView.as_view(), name='list'),
    path('bestsellers/', views.bestsellers, name='bestsellers'),
    path('<slug:slug>/', views.book_detail, name='detail'),
]