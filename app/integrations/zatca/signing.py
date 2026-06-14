"""
ZATCA Phase 2 cryptographic signing and certificate management.
Handles CSR generation, invoice hashing, and ECDSA signing.
"""

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.serialization import Encoding, PrivateFormat, NoEncryption
from cryptography import x509
from cryptography.x509.oid import NameOID
from datetime import datetime, timedelta, timezone
import hashlib
import base64
import uuid


class ZATCACertificateManager:
    def __init__(self):
        self._private_key: ec.EllipticCurvePrivateKey | None = None
        self._certificate: x509.Certificate | None = None

    def generate_csr(
        self,
        organization_name: str,
        common_name: str,
        country: str = "SA",
        vat_number: str = "",
    ) -> tuple[str, str]:
        private_key = ec.generate_private_key(ec.SECP256K1())
        self._private_key = private_key

        csr_builder = x509.CertificateSigningRequestBuilder()
        csr_builder = csr_builder.subject_name(
            x509.Name([
                x509.NameAttribute(NameOID.COUNTRY_NAME, country),
                x509.NameAttribute(NameOID.ORGANIZATION_NAME, organization_name),
                x509.NameAttribute(NameOID.COMMON_NAME, common_name),
            ])
        )

        vat_oid = x509.ObjectIdentifier("2.5.4.15")
        csr_builder = csr_builder.add_attribute(vat_oid, vat_number.encode())

        csr = csr_builder.sign(private_key, hashes.SHA256())

        csr_pem = csr.public_bytes(Encoding.PEM).decode()
        key_pem = private_key.private_bytes(
            Encoding.PEM,
            PrivateFormat.PKCS8,
            NoEncryption(),
        ).decode()

        return csr_pem, key_pem

    def load_signed_certificate(self, cert_pem: str):
        self._certificate = x509.load_pem_x509_certificate(cert_pem.encode())

    @property
    def has_certificate(self) -> bool:
        return self._certificate is not None


class InvoiceSigner:
    def __init__(self, private_key_pem: str | None = None):
        self._private_key: ec.EllipticCurvePrivateKey | None = None
        if private_key_pem:
            self._private_key = serialization.load_pem_private_key(
                private_key_pem.encode(), password=None
            )

    def load_key(self, private_key_pem: str):
        self._private_key = serialization.load_pem_private_key(
            private_key_pem.encode(), password=None
        )

    def compute_invoice_hash(self, invoice_data: dict) -> str:
        sorted_fields = self._canonical_sort(invoice_data)
        canonical = "".join(str(v) for v in sorted_fields.values())
        return hashlib.sha256(canonical.encode()).hexdigest()

    def sign_invoice_hash(self, invoice_hash: str) -> str:
        if not self._private_key:
            raise RuntimeError("Private key not loaded")
        signature = self._private_key.sign(
            invoice_hash.encode(),
            ec.ECDSA(hashes.SHA256()),
        )
        return base64.b64encode(signature).decode()

    def generate_uuid(self) -> str:
        return str(uuid.uuid4())

    def _canonical_sort(self, data: dict) -> dict:
        return dict(sorted(data.items()))

    def create_phase2_stamp(self, invoice_data: dict) -> dict:
        invoice_hash = self.compute_invoice_hash(invoice_data)
        signature = self.sign_invoice_hash(invoice_hash)
        return {
            "invoice_hash": invoice_hash,
            "digital_signature": signature,
            "signed_timestamp": datetime.now(timezone.utc).isoformat(),
            "uuid": self.generate_uuid(),
        }
