import pytest
from datetime import date, timedelta
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_full_e2e_flow(client: AsyncClient):
    email = "e2e@saudirms.sa"
    password = "testpass123"

    # 1. Register
    resp = await client.post(
        "/api/v1/users/register",
        json={
            "email": email,
            "password": password,
            "full_name": "E2E User",
            "organization_name": "E2E Integration Co",
        },
    )
    assert resp.status_code == 201
    register_data = resp.json()
    token = register_data["access_token"]
    org_id = register_data["organization_id"]
    assert register_data["subscription_tier"] == "basic"

    auth_header = {"Authorization": f"Bearer {token}"}

    # 2. Update organization with VAT number (needed for ZATCA invoices)
    resp = await client.patch(
        "/api/v1/users/organization",
        json={
            "name": "E2E Integration Co",
            "vat_number": "310123456789012",
            "commercial_registration": "CR-99999",
            "city_ar": "الرياض",
        },
        headers=auth_header,
    )
    assert resp.status_code == 200
    org = resp.json()
    assert org["vat_number"] == "310123456789012"
    assert org["commercial_registration"] == "CR-99999"

    # 3. Get organization
    resp = await client.get("/api/v1/users/organization", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json()["vat_number"] == "310123456789012"

    # 4. Create a hotel
    resp = await client.post(
        "/api/v1/hotels/",
        json={
            "name": "E2E Grand Hotel",
            "name_ar": "فندق إي تو إي جراند",
            "city": "Riyadh",
            "city_ar": "الرياض",
            "star_rating": 5,
            "total_rooms": 100,
            "currency": "SAR",
        },
        headers=auth_header,
    )
    assert resp.status_code == 201
    hotel = resp.json()
    hotel_id = hotel["id"]
    assert hotel["name"] == "E2E Grand Hotel"
    assert hotel["total_rooms"] == 100

    # 5. Create a room type
    resp = await client.post(
        f"/api/v1/hotels/{hotel_id}/room-types",
        json={
            "name": "Deluxe Suite",
            "name_ar": "جناح ديلوكس",
            "code": "DLX",
            "total_rooms": 20,
            "base_rate": 800.0,
            "min_rate": 400.0,
            "max_rate": 1600.0,
        },
        headers=auth_header,
    )
    assert resp.status_code == 201
    room_type = resp.json()
    room_type_id = room_type["id"]
    assert room_type["code"] == "DLX"
    assert room_type["base_rate"] == 800.0

    # 6. List hotels
    resp = await client.get("/api/v1/hotels/", headers=auth_header)
    assert resp.status_code == 200
    hotels = resp.json()
    assert len(hotels) >= 1

    # 7. Generate rate recommendations
    resp = await client.post(
        f"/api/v1/rates/generate/{hotel_id}",
        headers=auth_header,
    )
    assert resp.status_code == 200
    gen_data = resp.json()
    assert "Generated" in gen_data["message"]
    assert gen_data["hotel_id"] == hotel_id

    # 8. Get rate recommendations
    resp = await client.get(
        f"/api/v1/rates/recommendations?hotel_id={hotel_id}",
        headers=auth_header,
    )
    assert resp.status_code == 200
    recs = resp.json()
    assert len(recs) > 0

    rec = recs[0]
    assert rec["hotel_id"] == hotel_id
    assert rec["room_type_id"] == room_type_id
    assert rec["status"] == "pending"
    assert rec["recommended_rate"] > 0

    # 9. Filter recommendations by date range
    today = date.today()
    future = today + timedelta(days=30)
    resp = await client.get(
        f"/api/v1/rates/recommendations?hotel_id={hotel_id}&start_date={today.isoformat()}&end_date={future.isoformat()}",
        headers=auth_header,
    )
    assert resp.status_code == 200
    filtered = resp.json()
    assert len(filtered) > 0

    # 10. Apply a rate recommendation
    rec_id = recs[0]["id"]
    resp = await client.post(
        f"/api/v1/rates/apply/{rec_id}",
        headers=auth_header,
    )
    assert resp.status_code == 200
    apply_data = resp.json()
    assert apply_data["rate"] == rec["recommended_rate"]

    # 11. Create a ZATCA invoice
    resp = await client.post(
        "/api/v1/zatca/invoices",
        json={
            "hotel_id": hotel_id,
            "buyer_name": "Acme Corp",
            "buyer_vat_number": "399999999999993",
            "line_items": [
                {"name": "Deluxe Suite - 2 Nights", "quantity": 1, "unit_price": 1600.0, "vat_rate": 0.15},
                {"name": "Breakfast Buffet", "quantity": 2, "unit_price": 75.0, "vat_rate": 0.15},
            ],
            "notes": "E2E test invoice",
        },
        headers=auth_header,
    )
    assert resp.status_code == 201
    invoice = resp.json()
    assert invoice["seller_vat_number"] == "310123456789012"
    assert invoice["buyer_name"] == "Acme Corp"
    assert invoice["zatca_status"] == "draft"
    assert len(invoice["invoice_number"]) > 0
    total = 1600.0 + 2 * 75.0  # 1750.0
    vat = round(total * 0.15, 2)  # 262.5
    assert invoice["total_excluding_vat"] == total
    assert invoice["total_vat"] == vat
    assert invoice["total_including_vat"] == total + vat

    # 12. List invoices
    resp = await client.get("/api/v1/zatca/invoices", headers=auth_header)
    assert resp.status_code == 200
    invoices = resp.json()
    assert len(invoices) >= 1

    # 13. Get specific invoice
    invoice_id = invoice["id"]
    resp = await client.get(f"/api/v1/zatca/invoices/{invoice_id}", headers=auth_header)
    assert resp.status_code == 200
    assert resp.json()["id"] == invoice_id

    # 14. Generate CSR
    resp = await client.get("/api/v1/zatca/certificate/csr", headers=auth_header)
    assert resp.status_code == 200
    csr_data = resp.json()
    assert "BEGIN CERTIFICATE REQUEST" in csr_data["csr_pem"]
    assert "BEGIN PRIVATE KEY" in csr_data["private_key"]

    # 15. Get dashboard metrics
    resp = await client.get(f"/api/v1/reports/dashboard/{hotel_id}", headers=auth_header)
    assert resp.status_code == 200
    dashboard = resp.json()
    assert dashboard["hotel_id"] == hotel_id
    assert dashboard["hotel_name"] == "E2E Grand Hotel"
    assert dashboard["active_recommendations"] > 0

    # 16. Check subscription status
    resp = await client.get("/api/v1/billing/subscription", headers=auth_header)
    assert resp.status_code == 200
    sub = resp.json()
    assert sub["tier"] == "basic"
    assert sub["status"] == "active"
    assert sub["hotels_used"] >= 1

    # 17. Check subscription with no auth (should return 401)
    resp = await client.get("/api/v1/billing/subscription")
    assert resp.status_code == 401

    # 18. List plans (public endpoint)
    resp = await client.get("/api/v1/billing/plans")
    assert resp.status_code == 200
    plans = resp.json()
    assert len(plans) == 3
    tiers = [p["tier"] for p in plans]
    assert "basic" in tiers
    assert "professional" in tiers
    assert "enterprise" in tiers

    # 19. Create checkout session (mock - no Stripe keys)
    resp = await client.post(
        "/api/v1/billing/create-checkout-session",
        json={
            "price_id": "price_basic",
            "success_url": "http://localhost:3000/settings",
            "cancel_url": "http://localhost:3000/settings",
        },
        headers=auth_header,
    )
    assert resp.status_code == 200
    checkout = resp.json()
    assert "mock_session" in checkout["session_id"]
    assert "mock_checkout=true" in checkout["url"]

    # 20. Customer portal (mock - no Stripe customer)
    resp = await client.post(
        "/api/v1/billing/customer-portal",
        json={"return_url": "http://localhost:3000/settings"},
        headers=auth_header,
    )
    assert resp.status_code == 200
    portal = resp.json()
    assert "mock_portal=true" in portal["url"]

    # 21. Login with the same credentials
    resp = await client.post(
        "/api/v1/users/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200
    login_data = resp.json()
    assert login_data["user"]["email"] == email
    assert login_data["organization_id"] == org_id

    # 22. Verify duplicate registration fails
    resp = await client.post(
        "/api/v1/users/register",
        json={
            "email": email,
            "password": password,
            "full_name": "E2E User",
            "organization_name": "E2E Integration Co",
        },
    )
    assert resp.status_code == 400
    assert resp.json()["detail"] == "Email already registered"

    # 23. Health check
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "healthy"
