"""QR code generation for restaurant tables."""
import qrcode
from pathlib import Path
from django.conf import settings


def generate_table_qr(table, base_url='http://localhost:8000'):
    """Generate QR code for a specific table."""
    url = f"{base_url}/order/{table.table_number}/"
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    qr_dir = Path(settings.MEDIA_ROOT) / 'qr_codes'
    qr_dir.mkdir(parents=True, exist_ok=True)

    filepath = qr_dir / f"{table.table_number}.png"
    img.save(str(filepath))
    return str(filepath)


def generate_all_qr_codes(base_url='http://localhost:8000'):
    """Generate QR codes for all active tables."""
    from .models import RestaurantTable
    tables = RestaurantTable.objects.filter(active=True)
    generated = []
    for table in tables:
        path = generate_table_qr(table, base_url)
        generated.append((table.table_number, path))
    return generated
