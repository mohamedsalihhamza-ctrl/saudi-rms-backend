import pytest
from app.services.billing import (
    SubscriptionTier,
    PLAN_CONFIGS,
    get_plan,
)


def test_plan_configs_have_all_tiers():
    assert len(PLAN_CONFIGS) == 3
    assert SubscriptionTier.BASIC in PLAN_CONFIGS
    assert SubscriptionTier.PROFESSIONAL in PLAN_CONFIGS
    assert SubscriptionTier.ENTERPRISE in PLAN_CONFIGS


def test_basic_plan_limits():
    plan = get_plan(SubscriptionTier.BASIC)
    assert plan.max_hotels == 2
    assert plan.max_rooms_per_hotel == 50
    assert float(plan.monthly_price_usd) == 99.00


def test_professional_plan_limits():
    plan = get_plan(SubscriptionTier.PROFESSIONAL)
    assert plan.max_hotels == 10
    assert plan.max_rooms_per_hotel == 200
    assert float(plan.monthly_price_usd) == 249.00
    assert "ZATCA e-invoicing compliance" in plan.features


def test_enterprise_plan_limits():
    plan = get_plan(SubscriptionTier.ENTERPRISE)
    assert plan.max_hotels == 50
    assert plan.max_rooms_per_hotel == 1000
    assert float(plan.monthly_price_usd) == 749.00
    assert "SLA guarantee (99.9% uptime)" in plan.features


def test_plan_includes_stripe_price_id():
    for tier, plan in PLAN_CONFIGS.items():
        assert plan.stripe_price_id, f"{tier} missing stripe_price_id"


def test_basic_plan_forecast_days():
    assert get_plan(SubscriptionTier.BASIC).forecast_days == 30
    assert get_plan(SubscriptionTier.PROFESSIONAL).forecast_days == 90
    assert get_plan(SubscriptionTier.ENTERPRISE).forecast_days == 180
