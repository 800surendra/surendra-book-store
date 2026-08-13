from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Sum
from django.db.models import Q
from django.http import FileResponse, Http404
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .models import EBook, EBookAccess, EBookPurchase, WishlistItem, Review, ReturnRequest, Notification, SupportTicket, AuditLog
from books.models import Book
from orders.models import Order, PaymentProof
from orders.views import _get_payment_instructions
from accounts.models import User
from .models import ReturnRequest, SupportTicket


def ebook_list(request):
    query = (request.GET.get("q") or "").strip()
    ebooks = EBook.objects.filter(is_available=True).select_related("category")
    if query:
        ebooks = ebooks.filter(Q(title__icontains=query) | Q(author__icontains=query) | Q(description__icontains=query))
    return render(request, "commerce/ebook_list.html", {"ebooks": ebooks, "query": query})


@login_required
def my_ebooks(request):
    access = EBookAccess.objects.filter(user=request.user).select_related("ebook")
    return render(request, "commerce/my_ebooks.html", {"access_list": access})


@login_required
def download_ebook(request, ebook_id):
    access = get_object_or_404(EBookAccess.objects.select_related("ebook"), user=request.user, ebook_id=ebook_id)
    if not access.ebook.file:
        raise Http404("This e-book file is unavailable.")
    access.download_count += 1
    access.last_downloaded_at = timezone.now()
    access.save(update_fields=["download_count", "last_downloaded_at"])
    return FileResponse(access.ebook.file.open("rb"), as_attachment=True, filename=access.ebook.file.name.rsplit("/", 1)[-1])


@login_required
def buy_ebook(request, ebook_id):
    if request.method != "POST":
        return redirect("commerce:ebook_list")
    ebook = get_object_or_404(EBook, id=ebook_id, is_available=True)
    if EBookAccess.objects.filter(user=request.user, ebook=ebook).exists():
        messages.info(request, "This e-book is already in your library.")
        return redirect("commerce:my_ebooks")
    if ebook.final_price <= 0:
        EBookAccess.objects.get_or_create(user=request.user, ebook=ebook)
        messages.success(request, "This public-domain e-book was added to your library.")
        return redirect("commerce:my_ebooks")
    purchase = EBookPurchase.objects.filter(user=request.user, ebook=ebook).select_related("order").first()
    if purchase and purchase.order.payment_status in {"pending", "under_review"}:
        order = purchase.order
    else:
        name = request.user.get_full_name() or request.user.username or request.user.email
        order = Order.objects.create(user=request.user, full_name=name, email=request.user.email, phone=request.user.phone or "0000000000", address="Digital delivery", city="Digital", state="Rajasthan", pincode="000000", landmark="Digital product", country="India", total_amount=ebook.final_price, delivery_charges=0, discount=0, tax=0, grand_total=ebook.final_price, payment_method="upi", payment_status="pending", order_status="draft")
        EBookPurchase.objects.create(user=request.user, ebook=ebook, order=order)
    return render(request, "orders/payment_screen.html", {"order": order, "instructions": _get_payment_instructions("upi", order.grand_total), "upi_id": "8000411638@Airtel", "bank_account": "8000411638", "bank_ifsc": "AIRP0000001", "bank_name": "Airtel Payments Bank", "subtotal": order.total_amount, "delivery_charges": 0, "discount": 0, "tax": 0, "grand_total": order.grand_total})


@staff_member_required
def operations_dashboard(request):
    """Real-data operations overview; it complements rather than replaces Django admin."""
    today = timezone.localdate()
    orders_today = Order.objects.filter(created_at__date=today)
    metrics = {
        "today_orders": orders_today.count(),
        "today_revenue": orders_today.filter(payment_status="verified").aggregate(value=Sum("grand_total"))["value"] or 0,
        "pending_payments": PaymentProof.objects.filter(order__payment_status="under_review").count(),
        "pending_orders": Order.objects.filter(order_status="pending").count(),
        "delivered_orders": Order.objects.filter(order_status="delivered").count(),
        "low_stock": Book.objects.filter(stock__gt=0, stock__lte=5).count(),
        "out_of_stock": Book.objects.filter(stock=0).count(),
        "new_customers": User.objects.filter(created_at__date=today).count(),
        "return_requests": ReturnRequest.objects.filter(status="requested").count(),
        "open_tickets": SupportTicket.objects.exclude(status__in=["resolved", "closed"]).count(),
    }
    return render(request, "commerce/operations_dashboard.html", {"metrics": metrics, "recent_orders": Order.objects.order_by("-created_at")[:10]})


@login_required
def wishlist(request):
    items = WishlistItem.objects.filter(user=request.user).select_related("book", "book__category")
    return render(request, "commerce/wishlist.html", {"items": items})


@login_required
def toggle_wishlist(request, book_id):
    if request.method != "POST": return redirect("books:detail", slug=get_object_or_404(Book, id=book_id).slug)
    book = get_object_or_404(Book, id=book_id)
    item, created = WishlistItem.objects.get_or_create(user=request.user, book=book)
    if created:
        messages.success(request, "Book added to your wishlist.")
    else:
        item.delete(); messages.info(request, "Book removed from your wishlist.")
    return redirect(request.POST.get("next") or "commerce:wishlist")


@login_required
def create_review(request, book_id):
    book = get_object_or_404(Book, id=book_id)
    if request.method != "POST": return redirect("books:detail", slug=book.slug)
    eligible = Order.objects.filter(user=request.user, order_status__in=["processing", "shipped", "delivered"], items__book=book).exists()
    if not eligible:
        messages.error(request, "Only customers with a verified purchase can review this book.")
    else:
        try: rating = int(request.POST.get("rating", "0"))
        except ValueError: rating = 0
        body = (request.POST.get("body") or "").strip()
        if not body or rating not in range(1, 6): messages.error(request, "Enter a rating from 1 to 5 and a review.")
        else:
            Review.objects.update_or_create(user=request.user, book=book, defaults={"rating": rating, "body": body, "is_verified_purchase": True, "is_approved": False})
            messages.success(request, "Review submitted for moderation.")
    return redirect("books:detail", slug=book.slug)


@login_required
def returns(request):
    return render(request, "commerce/returns.html", {"returns": ReturnRequest.objects.filter(user=request.user).select_related("order")})


@login_required
def request_return(request, order_id):
    order = get_object_or_404(Order, id=order_id, user=request.user, order_status="delivered")
    if request.method == "POST":
        if (timezone.now() - order.created_at).days > 7:
            messages.error(request, "The 7-day return window has closed.")
        else:
            reason = (request.POST.get("reason") or "").strip()
            if reason:
                ReturnRequest.objects.get_or_create(order=order, user=request.user, defaults={"reason": reason})
                Notification.objects.create(user=request.user, title="Return request received", message=f"Your return request for order #{order.id} is under review.")
                messages.success(request, "Return request submitted.")
            else: messages.error(request, "Please provide a return reason.")
    return redirect("commerce:returns")


@login_required
def tickets(request):
    if request.method == "POST":
        subject, message = (request.POST.get("subject") or "").strip(), (request.POST.get("message") or "").strip()
        if subject and message:
            SupportTicket.objects.create(user=request.user, subject=subject, message=message)
            messages.success(request, "Support ticket created.")
        else: messages.error(request, "Subject and message are required.")
    return render(request, "commerce/tickets.html", {"tickets": SupportTicket.objects.filter(user=request.user)})


@login_required
def notifications(request):
    notes = Notification.objects.filter(user=request.user)
    notes.filter(read_at__isnull=True).update(read_at=timezone.now())
    return render(request, "commerce/notifications.html", {"notes": notes})
