"""Management command to seed the database with demo data."""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from tables.models import RestaurantTable
from menu.models import MenuCategory, MenuItem
from tables.qr import generate_all_qr_codes


class Command(BaseCommand):
    help = 'Seed database with demo tables, categories, and menu items'

    def handle(self, *args, **options):
        self.stdout.write('🌱 Seeding database...\n')

        # Create superuser
        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@orderless.com', 'admin123')
            self.stdout.write(self.style.SUCCESS('  ✅ Superuser created: admin / admin123'))
        else:
            self.stdout.write('  ℹ️  Superuser already exists')

        # Create staff user for kitchen/payment
        if not User.objects.filter(username='staff').exists():
            staff = User.objects.create_user('staff', 'staff@orderless.com', 'staff123', is_staff=True)
            self.stdout.write(self.style.SUCCESS('  ✅ Staff user created: staff / staff123'))
        else:
            self.stdout.write('  ℹ️  Staff user already exists')

        # Create tables T01-T10
        tables_created = 0
        for i in range(1, 11):
            table_number = f'T{i:02d}'
            obj, created = RestaurantTable.objects.get_or_create(
                table_number=table_number,
                defaults={'active': True}
            )
            if created:
                tables_created += 1
        self.stdout.write(self.style.SUCCESS(f'  ✅ Tables: {tables_created} created (T01-T10)'))

        # Create categories
        categories_data = [
            {'name': 'Starters', 'icon': '🥗', 'display_order': 1},
            {'name': 'Main Course', 'icon': '🍛', 'display_order': 2},
            {'name': 'Beverages', 'icon': '🥤', 'display_order': 3},
            {'name': 'Desserts', 'icon': '🍰', 'display_order': 4},
        ]
        categories = {}
        for cat_data in categories_data:
            obj, created = MenuCategory.objects.get_or_create(
                name=cat_data['name'],
                defaults={'icon': cat_data['icon'], 'display_order': cat_data['display_order']}
            )
            categories[cat_data['name']] = obj
        self.stdout.write(self.style.SUCCESS(f'  ✅ Categories: {len(categories_data)} created'))

        # Create menu items
        menu_items_data = [
            # Starters
            {'category': 'Starters', 'name': 'French Fries', 'description': 'Crispy golden fries served with ketchup and mayo', 'price': 120, 'emoji': '🍟', 'is_vegetarian': True, 'is_bestseller': True},
            {'category': 'Starters', 'name': 'Chicken Wings', 'description': 'Spicy buffalo wings tossed in tangy sauce', 'price': 220, 'emoji': '🍗', 'is_bestseller': True},
            {'category': 'Starters', 'name': 'Paneer Tikka', 'description': 'Marinated cottage cheese grilled to perfection', 'price': 200, 'emoji': '🧀', 'is_vegetarian': True},
            {'category': 'Starters', 'name': 'Spring Rolls', 'description': 'Crispy rolls stuffed with vegetables', 'price': 150, 'emoji': '🌯', 'is_vegetarian': True},

            # Main Course
            {'category': 'Main Course', 'name': 'Chicken Burger', 'description': 'Juicy grilled chicken patty with lettuce, tomato & special sauce', 'price': 180, 'emoji': '🍔', 'is_bestseller': True},
            {'category': 'Main Course', 'name': 'Veg Burger', 'description': 'Crispy vegetable patty with fresh greens & tangy mayo', 'price': 150, 'emoji': '🍔', 'is_vegetarian': True},
            {'category': 'Main Course', 'name': 'Chicken Pizza', 'description': 'Wood-fired pizza with tender chicken, peppers & mozzarella', 'price': 250, 'emoji': '🍕', 'is_bestseller': True},
            {'category': 'Main Course', 'name': 'Margherita Pizza', 'description': 'Classic pizza with fresh tomato, basil & mozzarella', 'price': 200, 'emoji': '🍕', 'is_vegetarian': True},
            {'category': 'Main Course', 'name': 'Pasta Alfredo', 'description': 'Creamy white sauce pasta with mushrooms and herbs', 'price': 220, 'emoji': '🍝', 'is_vegetarian': True},
            {'category': 'Main Course', 'name': 'Chicken Biryani', 'description': 'Aromatic basmati rice cooked with tender chicken and spices', 'price': 280, 'emoji': '🍚', 'is_bestseller': True},

            # Beverages
            {'category': 'Beverages', 'name': 'Coke', 'description': 'Chilled Coca-Cola 300ml', 'price': 50, 'emoji': '🥤', 'is_vegetarian': True},
            {'category': 'Beverages', 'name': 'Fresh Lime Soda', 'description': 'Refreshing lime soda — sweet or salty', 'price': 80, 'emoji': '🍋', 'is_vegetarian': True},
            {'category': 'Beverages', 'name': 'Coffee', 'description': 'Freshly brewed hot coffee', 'price': 80, 'emoji': '☕', 'is_vegetarian': True},
            {'category': 'Beverages', 'name': 'Mango Lassi', 'description': 'Thick and creamy mango yogurt drink', 'price': 100, 'emoji': '🥭', 'is_vegetarian': True},
            {'category': 'Beverages', 'name': 'Masala Chai', 'description': 'Authentic Indian spiced tea', 'price': 40, 'emoji': '🍵', 'is_vegetarian': True},

            # Desserts
            {'category': 'Desserts', 'name': 'Ice Cream', 'description': 'Two scoops of premium ice cream — vanilla, chocolate or strawberry', 'price': 100, 'emoji': '🍨', 'is_vegetarian': True},
            {'category': 'Desserts', 'name': 'Chocolate Brownie', 'description': 'Warm fudgy brownie topped with vanilla ice cream', 'price': 160, 'emoji': '🍫', 'is_vegetarian': True, 'is_bestseller': True},
            {'category': 'Desserts', 'name': 'Gulab Jamun', 'description': 'Soft milk dumplings soaked in rose-flavored sugar syrup', 'price': 80, 'emoji': '🟤', 'is_vegetarian': True},
        ]

        items_created = 0
        for item_data in menu_items_data:
            category = categories[item_data.pop('category')]
            obj, created = MenuItem.objects.get_or_create(
                name=item_data['name'],
                defaults={**item_data, 'category': category}
            )
            if created:
                items_created += 1
        self.stdout.write(self.style.SUCCESS(f'  ✅ Menu items: {items_created} created'))

        # Generate QR codes
        try:
            qr_codes = generate_all_qr_codes()
            self.stdout.write(self.style.SUCCESS(f'  ✅ QR codes: {len(qr_codes)} generated'))
        except Exception as e:
            self.stdout.write(self.style.WARNING(f'  ⚠️  QR generation failed: {e}'))

        self.stdout.write(self.style.SUCCESS('\n🎉 Database seeded successfully!'))
        self.stdout.write('\n📋 Credentials:')
        self.stdout.write('   Admin:  admin / admin123')
        self.stdout.write('   Staff:  staff / staff123')
        self.stdout.write('\n🔗 URLs:')
        self.stdout.write('   Customer: http://localhost:8000/order/T05/')
        self.stdout.write('   Kitchen:  http://localhost:8000/kitchen/')
        self.stdout.write('   Payment:  http://localhost:8000/payment/')
        self.stdout.write('   Admin:    http://localhost:8000/admin/')
