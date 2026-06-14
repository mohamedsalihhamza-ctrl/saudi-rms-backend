import pytest
from datetime import datetime, timezone
from decimal import Decimal
from app.integrations.zatca import ZATCAInvoice, InvoiceLineItem, ZATCACertificateManager, InvoiceSigner


def test_create_invoice_with_line_items():
    invoice = ZATCAInvoice(
        seller_name="Saudi Hotel Co",
        seller_vat_number="310122223400003",
        buyer_name="Guest Name",
        buyer_vat_number="301234567800003",
        line_items=[
            InvoiceLineItem(
                name="Deluxe Room - 2 nights",
                quantity=Decimal("2"),
                unit_price=Decimal("500.00"),
                vat_rate=Decimal("0.15"),
            ),
            InvoiceLineItem(
                name="Breakfast",
                quantity=Decimal("2"),
                unit_price=Decimal("75.00"),
                vat_rate=Decimal("0.15"),
            ),
        ],
    )

    assert len(invoice.line_items) == 2
    assert float(invoice.total_excluding_vat) == 1150.00
    assert float(invoice.total_vat) == 172.50
    assert float(invoice.total_including_vat) == 1322.50


def test_invoice_validation():
    invoice = ZATCAInvoice(
        seller_name="",
        seller_vat_number="",
        buyer_name="Test",
        line_items=[],
    )
    errors = invoice.validate()
    assert "Seller name is required" in errors
    assert "Seller VAT number is required" in errors
    assert "At least one line item is required" in errors


def test_invoice_qr_code_generation():
    invoice = ZATCAInvoice(
        seller_name="Test Hotel",
        seller_vat_number="310122223400003",
        buyer_name="Guest",
        line_items=[
            InvoiceLineItem(name="Room", quantity=Decimal("1"), unit_price=Decimal("500.00")),
        ],
    )
    qr = invoice.generate_qr_base64()
    assert isinstance(qr, str)
    assert len(qr) > 0


def test_invoice_number_auto_generation():
    invoice = ZATCAInvoice(
        seller_name="Test",
        seller_vat_number="310122223400003",
        buyer_name="Guest",
        line_items=[
            InvoiceLineItem(name="Room", quantity=Decimal("1"), unit_price=Decimal("500.00")),
        ],
    )
    assert invoice.invoice_number.startswith("INV-")


def test_csr_generation():
    manager = ZATCACertificateManager()
    csr_pem, key_pem = manager.generate_csr(
        organization_name="Saudi Hotel Co",
        common_name="Saudi Hotel Co-ZATCA",
        vat_number="310122223400003",
    )
    assert csr_pem.startswith("-----BEGIN CERTIFICATE REQUEST-----")
    assert key_pem.startswith("-----BEGIN PRIVATE KEY-----")


def test_invoice_signing():
    signer = InvoiceSigner()
    import hashlib
    invoice_hash = hashlib.sha256(b"test_invoice_data").hexdigest()

    manager = ZATCACertificateManager()
    _, key_pem = manager.generate_csr(
        organization_name="Test", common_name="Test-ZATCA"
    )
    signer.load_key(key_pem)
    signature = signer.sign_invoice_hash(invoice_hash)
    assert isinstance(signature, str)
    assert len(signature) > 0


def test_invoice_to_dict():
    invoice = ZATCAInvoice(
        seller_name="Test Hotel",
        seller_vat_number="310122223400003",
        buyer_name="Guest",
        line_items=[
            InvoiceLineItem(name="Room", quantity=Decimal("1"), unit_price=Decimal("500.00")),
        ],
    )
    d = invoice.to_dict()
    assert d["seller_name"] == "Test Hotel"
    assert d["total_including_vat"] == 575.00
    assert "qr_code_base64" in d
