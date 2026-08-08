from django.urls import path
from . import views

app_name = 'cart'
urlpatterns = [
    path('', views.view_cart, name='view'),
    path('add/<int:book_id>/', views.add_to_cart, name='add'),
    path('update/<int:item_id>/', views.update_cart, name='update'),
    path('remove/<int:item_id>/', views.remove_from_cart, name='remove'),
]