from urllib.error import URLError
from urllib.request import Request, urlopen

from django.core.files.base import ContentFile
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from books.models import Category
from commerce.models import EBook


BOOKS = [
    {
        "title": "Alice's Adventures in Wonderland", "author": "Lewis Carroll", "slug": "alice-adventures-public-domain",
        "description": "A public-domain classic from Project Gutenberg.", "price": "0.00",
        "source_url": "https://www.gutenberg.org/ebooks/11", "download": "https://www.gutenberg.org/cache/epub/11/pg11-images.epub",
    },
    {
        "title": "The Art of War", "author": "Sunzi", "slug": "the-art-of-war-public-domain",
        "description": "A public-domain strategy classic from Project Gutenberg.", "price": "0.00",
        "source_url": "https://www.gutenberg.org/ebooks/132", "download": "https://www.gutenberg.org/cache/epub/132/pg132-images.epub",
    },
]


class Command(BaseCommand):
    help = "Downloads two legal public-domain Project Gutenberg EPUB samples into the secure e-book library."

    def handle(self, *args, **options):
        category, _ = Category.objects.get_or_create(name="Public Domain Classics", slug="public-domain-classics")
        for item in BOOKS:
            ebook, _ = EBook.objects.update_or_create(
                slug=item["slug"],
                defaults={"title": item["title"], "author": item["author"], "category": category, "description": item["description"], "price": item["price"], "language": "English", "is_available": False, "source_url": item["source_url"]},
            )
            if not ebook.file:
                self.stdout.write(f"Downloading public-domain EPUB: {ebook.title}")
                request = Request(item["download"], headers={"User-Agent": "SurendraBookStore/1.0"})
                try:
                    with urlopen(request, timeout=30) as response:
                        data = response.read()
                    ebook.file.save(f"{slugify(ebook.title)}.epub", ContentFile(data), save=True)
                except (URLError, TimeoutError, OSError) as exc:
                    ebook.is_available = False
                    ebook.save(update_fields=["is_available"])
                    self.stdout.write(self.style.WARNING(f"Not published yet: {ebook.title}. Download failed ({exc}). Run this command again where internet access is allowed."))
                    continue
            ebook.is_available = True
            ebook.save(update_fields=["is_available"])
            self.stdout.write(self.style.SUCCESS(f"Ready: {ebook.title}"))
