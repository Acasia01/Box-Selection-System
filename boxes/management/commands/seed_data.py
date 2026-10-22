from decimal import Decimal
from django.core.management.base import BaseCommand
from products.models import Product
from boxes.models import BoxType, BoxInventory


class Command(BaseCommand):
    help = "Seeds representative sample products, box specifications, and live inventory."

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE("Seeding catalog products..."))

        products_data = [
            {
                "sku": "SPK-101",
                "name": "Wireless Speaker",
                "length": Decimal("20.00"),
                "width": Decimal("15.00"),
                "height": Decimal("10.00"),
                "weight": Decimal("1.200"),
                "clearance": Decimal("1.00"),
                "is_fragile": True,
                "is_active": True,
            },
            {
                "sku": "BOOK-01",
                "name": "Hardcover Reference Book",
                "length": Decimal("24.00"),
                "width": Decimal("16.00"),
                "height": Decimal("4.00"),
                "weight": Decimal("0.850"),
                "clearance": Decimal("0.00"),
                "is_fragile": False,
                "is_active": True,
            },
            {
                "sku": "HEAD-202",
                "name": "Noise Canceling Headphones",
                "length": Decimal("18.00"),
                "width": Decimal("14.00"),
                "height": Decimal("8.00"),
                "weight": Decimal("0.350"),
                "clearance": Decimal("0.50"),
                "is_fragile": False,
                "is_active": True,
            },
            {
                "sku": "MUG-003",
                "name": "Ceramic Artisan Coffee Mug",
                "length": Decimal("12.00"),
                "width": Decimal("10.00"),
                "height": Decimal("10.00"),
                "weight": Decimal("0.400"),
                "clearance": Decimal("1.50"),
                "is_fragile": True,
                "is_active": True,
            },
            {
                "sku": "LAP-900",
                "name": "Ultra Thin Laptop 14-inch",
                "length": Decimal("35.00"),
                "width": Decimal("24.00"),
                "height": Decimal("2.00"),
                "weight": Decimal("1.800"),
                "clearance": Decimal("1.00"),
                "is_fragile": True,
                "is_active": True,
            },
            {
                "sku": "TSH-110",
                "name": "Premium Cotton T-Shirt",
                "length": Decimal("25.00"),
                "width": Decimal("20.00"),
                "height": Decimal("2.00"),
                "weight": Decimal("0.200"),
                "clearance": Decimal("0.00"),
                "is_fragile": False,
                "is_active": True,
            },
        ]

        for p_info in products_data:
            obj, created = Product.objects.update_or_create(
                sku=p_info["sku"],
                defaults=p_info,
            )
            state = "Created" if created else "Updated"
            self.stdout.write(f"  {state} product: {obj.sku} - {obj.name}")

        self.stdout.write(self.style.NOTICE("\nSeeding box types and inventories..."))

        boxes_data = [
            {
                "code": "BX-101",
                "name": "Small Standard Box",
                "length": Decimal("22.00"),
                "width": Decimal("16.00"),
                "height": Decimal("12.00"),
                "max_weight": Decimal("3.000"),
                "empty_weight": Decimal("0.150"),
                "cost": Decimal("12.00"),
                "currency": "INR",
                "is_active": True,
                "on_hand": 50,
                "reserved": 5,
            },
            {
                "code": "BX-102",
                "name": "Medium Shipping Box",
                "length": Decimal("30.00"),
                "width": Decimal("25.00"),
                "height": Decimal("20.00"),
                "max_weight": Decimal("5.000"),
                "empty_weight": Decimal("0.300"),
                "cost": Decimal("18.00"),
                "currency": "INR",
                "is_active": True,
                "on_hand": 100,
                "reserved": 12,
            },
            {
                "code": "BX-103",
                "name": "Large Shipping Box",
                "length": Decimal("45.00"),
                "width": Decimal("35.00"),
                "height": Decimal("25.00"),
                "max_weight": Decimal("10.000"),
                "empty_weight": Decimal("0.550"),
                "cost": Decimal("28.00"),
                "currency": "INR",
                "is_active": True,
                "on_hand": 60,
                "reserved": 2,
            },
            {
                "code": "BX-104",
                "name": "Flat Book / Media Box",
                "length": Decimal("32.00"),
                "width": Decimal("24.00"),
                "height": Decimal("8.00"),
                "max_weight": Decimal("3.500"),
                "empty_weight": Decimal("0.180"),
                "cost": Decimal("14.00"),
                "currency": "INR",
                "is_active": True,
                "on_hand": 80,
                "reserved": 0,
            },
            {
                "code": "BX-105",
                "name": "Heavy Duty Cube Box",
                "length": Decimal("35.00"),
                "width": Decimal("35.00"),
                "height": Decimal("35.00"),
                "max_weight": Decimal("20.000"),
                "empty_weight": Decimal("0.850"),
                "cost": Decimal("45.00"),
                "currency": "INR",
                "is_active": True,
                "on_hand": 30,
                "reserved": 1,
            },
            {
                "code": "BX-OUT",
                "name": "Out-of-Stock Test Box",
                "length": Decimal("25.00"),
                "width": Decimal("20.00"),
                "height": Decimal("15.00"),
                "max_weight": Decimal("4.000"),
                "empty_weight": Decimal("0.200"),
                "cost": Decimal("11.00"),
                "currency": "INR",
                "is_active": True,
                "on_hand": 10,
                "reserved": 10,  # 0 available
            },
            {
                "code": "BX-INACT",
                "name": "Discontinued Box Spec",
                "length": Decimal("28.00"),
                "width": Decimal("22.00"),
                "height": Decimal("14.00"),
                "max_weight": Decimal("4.000"),
                "empty_weight": Decimal("0.220"),
                "cost": Decimal("9.00"),
                "currency": "INR",
                "is_active": False,  # Inactive
                "on_hand": 50,
                "reserved": 0,
            },
        ]

        for b_info in boxes_data:
            on_hand = b_info.pop("on_hand")
            reserved = b_info.pop("reserved")
            box, created = BoxType.objects.update_or_create(
                code=b_info["code"],
                defaults=b_info,
            )
            inv, inv_created = BoxInventory.objects.update_or_create(
                box_type=box,
                defaults={
                    "quantity_on_hand": on_hand,
                    "quantity_reserved": reserved,
                },
            )
            state = "Created" if created else "Updated"
            self.stdout.write(
                f"  {state} box: {box.code} ({box.name}) | Available: {inv.quantity_available}/{inv.quantity_on_hand}"
            )

        self.stdout.write(self.style.NOTICE("\nSeeding sample warehouse orders..."))
        from orders.models import Order, OrderItem

        orders_data = [
            {
                "order_number": "ORD-1001",
                "customer_name": "Rajesh Kumar",
                "status": Order.STATUS_PENDING,
                "items": [
                    ("SPK-101", 2),  # 2 Wireless Speakers (from design.md example)
                ]
            },
            {
                "order_number": "ORD-1002",
                "customer_name": "Priya Sharma",
                "status": Order.STATUS_PENDING,
                "items": [
                    ("BOOK-01", 1),
                    ("HEAD-202", 1),
                ]
            },
            {
                "order_number": "ORD-1003",
                "customer_name": "Vikram Mehta",
                "status": Order.STATUS_PENDING,
                "items": [
                    ("LAP-900", 1),
                ]
            },
            {
                "order_number": "ORD-1004",
                "customer_name": "Ananya Patel",
                "status": Order.STATUS_PENDING,
                "items": [
                    ("MUG-003", 2),
                    ("TSH-110", 2),
                ]
            },
            {
                "order_number": "ORD-EMPTY",
                "customer_name": "Test Customer (Empty)",
                "status": Order.STATUS_PENDING,
                "items": []
            },
            {
                "order_number": "ORD-CANCELLED",
                "customer_name": "Test Customer (Cancelled)",
                "status": Order.STATUS_CANCELLED,
                "items": [
                    ("BOOK-01", 1),
                ]
            },
        ]

        for o_info in orders_data:
            items_info = o_info.pop("items")
            order, created = Order.objects.update_or_create(
                order_number=o_info["order_number"],
                defaults=o_info,
            )
            # Clear old items if updating to match seed
            order.items.all().delete()
            for sku, qty in items_info:
                product = Product.objects.get(sku=sku)
                OrderItem.objects.create(order=order, product=product, quantity=qty)
            state = "Created" if created else "Updated"
            self.stdout.write(f"  {state} order: {order.order_number} ({len(items_info)} item lines)")

        self.stdout.write(self.style.SUCCESS("\nSample catalog, box inventory, and orders seeded successfully!"))
