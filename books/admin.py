from django.contrib import admin
from .models import Book, Category

class BookAdmin(admin.ModelAdmin):
    list_display = ('title', 'author', 'price', 'final_price', 'stock', 'is_bestseller', 'is_new_arrival')
    list_filter = ('category', 'is_bestseller', 'is_new_arrival')  # 'status' hata diya
    search_fields = ('title', 'author', 'description')
    prepopulated_fields = {'slug': ('title',)}
    list_editable = ('price', 'stock', 'is_bestseller', 'is_new_arrival')

admin.site.register(Book, BookAdmin)
admin.site.register(Category)