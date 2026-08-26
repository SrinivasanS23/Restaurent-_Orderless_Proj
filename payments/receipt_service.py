"""PDF receipt generation using ReportLab."""
import os
from datetime import datetime
from pathlib import Path
from django.conf import settings
from django.utils import timezone
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.enums import TA_CENTER, TA_RIGHT, TA_LEFT
from .models import Receipt


class ReceiptService:

    @staticmethod
    def generate_pdf_receipt(order):
        """Generate a professional PDF receipt for an order."""
        # Check if receipt already exists
        existing = Receipt.objects.filter(order=order).first()
        if existing:
            pdf_path = Path(settings.MEDIA_ROOT) / existing.pdf_path
            if pdf_path.exists():
                return existing

        # Generate receipt number
        receipt_number = f"RCP-{order.order_number.replace('ORD-', '')}-{timezone.now().strftime('%y%m%d')}"

        # Ensure directory exists
        receipts_dir = Path(settings.MEDIA_ROOT) / 'receipts'
        receipts_dir.mkdir(parents=True, exist_ok=True)

        filename = f"Receipt_{order.order_number}_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        relative_path = f"receipts/{filename}"
        full_path = receipts_dir / filename

        # Colors
        brown_dark = HexColor('#3D2923')
        brown_accent = HexColor('#654032')
        brown_mid = HexColor('#B2835A')
        brown_light = HexColor('#D6B89A')
        bg_cream = HexColor('#F6EEE3')

        # Build PDF
        doc = SimpleDocTemplate(
            str(full_path),
            pagesize=A4,
            rightMargin=20*mm,
            leftMargin=20*mm,
            topMargin=15*mm,
            bottomMargin=15*mm
        )

        styles = getSampleStyleSheet()

        title_style = ParagraphStyle('ReceiptTitle', parent=styles['Heading1'],
            fontName='Helvetica-Bold', fontSize=18, textColor=brown_dark,
            alignment=TA_CENTER, spaceAfter=4)
        
        subtitle_style = ParagraphStyle('ReceiptSubtitle', parent=styles['Normal'],
            fontName='Helvetica', fontSize=9, textColor=brown_accent,
            alignment=TA_CENTER, spaceAfter=2)

        meta_style = ParagraphStyle('ReceiptMeta', parent=styles['Normal'],
            fontName='Helvetica', fontSize=9, textColor=brown_dark,
            spaceAfter=2)
        
        meta_bold_style = ParagraphStyle('ReceiptMetaBold', parent=styles['Normal'],
            fontName='Helvetica-Bold', fontSize=10, textColor=brown_dark,
            spaceAfter=2)

        section_style = ParagraphStyle('SectionHeader', parent=styles['Normal'],
            fontName='Helvetica-Bold', fontSize=11, textColor=brown_accent,
            spaceBefore=10, spaceAfter=6)

        footer_style = ParagraphStyle('Footer', parent=styles['Normal'],
            fontName='Helvetica-Oblique', fontSize=9, textColor=brown_mid,
            alignment=TA_CENTER, spaceBefore=15)

        elements = []

        # Restaurant Header
        restaurant_name = getattr(settings, 'RESTAURANT_NAME', 'OrderLess')
        elements.append(Paragraph(f"<b>{restaurant_name}</b>", title_style))
        
        restaurant_address = getattr(settings, 'RESTAURANT_ADDRESS', '')
        if restaurant_address:
            elements.append(Paragraph(restaurant_address, subtitle_style))

        restaurant_gstin = getattr(settings, 'RESTAURANT_GSTIN', '')
        if restaurant_gstin:
            elements.append(Paragraph(f"GSTIN: {restaurant_gstin}", subtitle_style))
        
        elements.append(Paragraph("TAX INVOICE", ParagraphStyle('InvoiceLabel', parent=styles['Normal'],
            fontName='Helvetica-Bold', fontSize=10, textColor=brown_mid,
            alignment=TA_CENTER, spaceBefore=6, spaceAfter=4)))

        elements.append(HRFlowable(width="100%", thickness=1, color=brown_light))
        elements.append(Spacer(1, 6))

        # Receipt & Order Info
        elements.append(Paragraph(f"Receipt No: <b>{receipt_number}</b>", meta_style))
        elements.append(Paragraph(f"Order No: <b>{order.order_number}</b>", meta_style))
        elements.append(Paragraph(f"Date: <b>{order.created_at.strftime('%d %b %Y')}</b> &nbsp; Time: <b>{order.created_at.strftime('%H:%M')}</b>", meta_style))
        elements.append(Spacer(1, 4))
        
        # Customer Info
        customer_name = order.customer_name_display
        customer_phone = order.customer_phone_masked
        table_num = order.table.display_number
        elements.append(Paragraph(f"Customer: <b>{customer_name}</b>", meta_style))
        if customer_phone:
            elements.append(Paragraph(f"Phone: {customer_phone}", meta_style))
        elements.append(Paragraph(f"Table: <b>{table_num}</b>", meta_style))

        elements.append(Spacer(1, 6))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=brown_light))
        elements.append(Spacer(1, 6))

        # Items Table
        elements.append(Paragraph("ORDER ITEMS", section_style))

        table_data = [['Item', 'Qty', 'Price', 'Total']]
        for item in order.items.select_related('menu_item').all():
            item_name = item.item_name_snapshot or item.menu_item.name
            table_data.append([
                item_name,
                str(item.quantity),
                f"₹{item.unit_price:.2f}",
                f"₹{item.subtotal:.2f}"
            ])

        col_widths = [240, 40, 75, 75]
        t = Table(table_data, colWidths=col_widths)
        t.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('TEXTCOLOR', (0, 0), (-1, 0), brown_accent),
            ('TEXTCOLOR', (0, 1), (-1, -1), brown_dark),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
            ('TOPPADDING', (0, 1), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
            ('LINEBELOW', (0, 0), (-1, 0), 1, brown_light),
            ('ALIGN', (1, 0), (-1, -1), 'RIGHT'),
            ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ]))
        elements.append(t)

        elements.append(Spacer(1, 6))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=brown_light))
        elements.append(Spacer(1, 6))

        # Billing Summary
        billing_data = [
            ['Subtotal:', f"₹{order.subtotal:.2f}"],
        ]
        if order.discount > 0:
            billing_data.append(['Discount:', f"-₹{order.discount:.2f}"])
        billing_data.extend([
            ['CGST (2.5%):', f"₹{order.cgst_amount:.2f}"],
            ['SGST (2.5%):', f"₹{order.sgst_amount:.2f}"],
            ['', ''],
            ['GRAND TOTAL:', f"₹{order.total_amount:.2f}"],
        ])

        bt = Table(billing_data, colWidths=[340, 90])
        bt.setStyle(TableStyle([
            ('FONTNAME', (0, 0), (-1, -2), 'Helvetica'),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -2), 9),
            ('FONTSIZE', (0, -1), (-1, -1), 12),
            ('TEXTCOLOR', (0, 0), (-1, -2), brown_accent),
            ('TEXTCOLOR', (0, -1), (-1, -1), brown_dark),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('TOPPADDING', (0, 0), (-1, -1), 2),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 2),
            ('LINEABOVE', (0, -1), (-1, -1), 1.5, brown_dark),
        ]))
        elements.append(bt)

        elements.append(Spacer(1, 8))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=brown_light))
        elements.append(Spacer(1, 6))

        # Payment Info
        elements.append(Paragraph("PAYMENT DETAILS", section_style))
        
        payment = order.payments.first()
        if payment:
            elements.append(Paragraph(f"Payment Method: <b>{payment.get_payment_method_display()}</b>", meta_style))
            elements.append(Paragraph(f"Amount Paid: <b>₹{payment.amount:.2f}</b>", meta_style))
            elements.append(Paragraph(f"Status: <b>PAID</b>", meta_style))
            if payment.paid_at:
                elements.append(Paragraph(f"Paid At: {payment.paid_at.strftime('%d %b %Y %H:%M')}", meta_style))
            if payment.transaction_reference:
                elements.append(Paragraph(f"Ref: {payment.transaction_reference}", meta_style))
            if payment.cashier:
                cashier_name = payment.cashier.get_full_name() or payment.cashier.username
                elements.append(Paragraph(f"Cashier: {cashier_name}", meta_style))
        else:
            status_text = "PAID" if order.payment_status == 'PAID' else order.payment_status
            elements.append(Paragraph(f"Status: <b>{status_text}</b>", meta_style))

        elements.append(Spacer(1, 15))
        elements.append(HRFlowable(width="100%", thickness=0.5, color=brown_light))
        elements.append(Paragraph("Thank you for dining with us!", footer_style))
        elements.append(Paragraph(f"— {restaurant_name}", footer_style))

        doc.build(elements)

        # Save receipt record
        receipt, created = Receipt.objects.update_or_create(
            order=order,
            defaults={
                'receipt_number': receipt_number,
                'pdf_path': relative_path,
            }
        )

        return receipt
