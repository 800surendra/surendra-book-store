from django.shortcuts import render, get_object_or_404
from django.views.generic import ListView
from django.db.models import Q
from .models import Book, Category

class BookListView(ListView):
    model = Book
    template_name = 'books/book_list.html'
    context_object_name = 'books'
    paginate_by = 12

    def get_queryset(self):
        queryset = Book.objects.all().order_by('-created_at')
        q = self.request.GET.get('q')
        cat = self.request.GET.get('category')
        if q:
            queryset = queryset.filter(Q(title__icontains=q) | Q(author__icontains=q) | Q(category__name__icontains=q) | Q(description__icontains=q))
        if cat:
            queryset = queryset.filter(category__slug=cat)
        sort = self.request.GET.get('sort')
        if sort == 'price_low': queryset = queryset.order_by('price')
        elif sort == 'price_high': queryset = queryset.order_by('-price')
        elif sort == 'rating': queryset = queryset.order_by('-rating')
        return queryset.distinct()

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['categories'] = Category.objects.all()
        return context

def book_detail(request, slug):
    book = get_object_or_404(Book, slug=slug)
    return render(request, 'books/book_detail.html', {'book': book})

def bestsellers(request):
    books = Book.objects.filter(is_bestseller=True)
    return render(request, 'books/bestsellers.html', {'books': books})
    
