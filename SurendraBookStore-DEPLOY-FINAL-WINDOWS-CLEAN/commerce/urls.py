from django.urls import path
from . import views

app_name = "commerce"
urlpatterns = [
    path("ebooks/", views.ebook_list, name="ebook_list"),
    path("my-ebooks/", views.my_ebooks, name="my_ebooks"),
    path("ebooks/<int:ebook_id>/download/", views.download_ebook, name="download_ebook"),
    path("ebooks/<int:ebook_id>/buy/", views.buy_ebook, name="buy_ebook"),
    path("wishlist/", views.wishlist, name="wishlist"),
    path("wishlist/toggle/<int:book_id>/", views.toggle_wishlist, name="toggle_wishlist"),
    path("reviews/<int:book_id>/", views.create_review, name="create_review"),
    path("returns/", views.returns, name="returns"),
    path("returns/new/<int:order_id>/", views.request_return, name="request_return"),
    path("support/tickets/", views.tickets, name="tickets"),
    path("notifications/", views.notifications, name="notifications"),
]
