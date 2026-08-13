from django.contrib import messages
from django.shortcuts import redirect, render

from books.models import Book


def home(request):
    """Preserves the existing home template and only provides clean data."""
    return render(request, "core/index.html", {
        "bestsellers": Book.objects.filter(is_bestseller=True)[:6],
        "new_arrivals": Book.objects.filter(is_new_arrival=True)[:6],
        "all_books": Book.objects.order_by("?")[:8],
    })


def support(request):
    return render(request, "core/support.html")


def subscribe(request):
    if request.method != "POST":
        return redirect("core:home")
    email = (request.POST.get("email") or "").strip()
    if email:
        messages.success(request, "Thank you for subscribing.")
    else:
        messages.error(request, "Please enter a valid email address.")
    return redirect("core:home")
