from django.shortcuts import render
from books.models import Book

def home(request):
    bestsellers = Book.objects.filter(is_bestseller=True)[:6]
    new_arrivals = Book.objects.filter(is_new_arrival=True)[:6]
    all_books = Book.objects.all().order_by('?')[:8]
    context = {
        'bestsellers': bestsellers,
        'new_arrivals': new_arrivals,
        'all_books': all_books,
    }
    return render(request, 'core/index.html', context)
    from django.shortcuts import render
from books.models import Book

def home(request):
    bestsellers = Book.objects.filter(is_bestseller=True)[:6]
    new_arrivals = Book.objects.filter(is_new_arrival=True)[:6]
    return render(request, 'core/index.html', {
        'bestsellers': bestsellers,
        'new_arrivals': new_arrivals,
    })

def support(request):
    return render(request, 'core/support.html')
    from django.contrib import messages

def subscribe(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        if email:
            messages.success(request, f'Thank you for subscribing with {email}!')
        else:
            messages.error(request, 'Please enter a valid email.')
    return redirect('core:home')