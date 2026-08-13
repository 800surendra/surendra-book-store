import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from core.models import ServiceablePincode


class Command(BaseCommand):
    help = "Import approved Rajasthan serviceable PIN codes from a CSV file."

    def add_arguments(self, parser):
        parser.add_argument("csv_path")

    def handle(self, *args, **options):
        path = Path(options["csv_path"])
        if not path.is_file():
            raise CommandError("CSV file was not found.")
        required = {"pincode", "city", "state"}
        count = 0
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or not required.issubset(set(reader.fieldnames)):
                raise CommandError("CSV headers required: pincode,city,state. Optional: area_name,estimated_delivery_days,shipping_charge")
            for row in reader:
                if (row.get("state") or "").strip().lower() != "rajasthan":
                    raise CommandError(f"Only Rajasthan PIN codes are allowed: {row.get('pincode')}")
                ServiceablePincode.objects.update_or_create(
                    pincode=(row.get("pincode") or "").strip(),
                    defaults={
                        "city": (row.get("city") or "").strip(), "state": "Rajasthan",
                        "area_name": (row.get("area_name") or "").strip(), "is_serviceable": True,
                        "estimated_delivery_days": int(row.get("estimated_delivery_days") or 5),
                        "shipping_charge": row.get("shipping_charge") or 49,
                        "free_shipping_minimum_order": 2000,
                    },
                )
                count += 1
        self.stdout.write(self.style.SUCCESS(f"Imported {count} approved PIN code(s)."))
