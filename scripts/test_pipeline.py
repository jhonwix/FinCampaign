#!/usr/bin/env python3
"""
End-to-end pipeline test with 3 representative customers.

Carlos  → NEAR-PRIME  (score 680, DTI ~26%)
Andrea  → PRIME/SUPER-PRIME (score 760, DTI ~12%)
Miguel  → SUBPRIME/DEEP-SUBPRIME (score 580, DTI ~67%)

Usage:
    python scripts/test_pipeline.py
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from agents.orchestrator import orchestrator

TEST_CUSTOMERS = [
    {
        "name": "Carlos Mendoza",
        "age": 34,
        "monthly_income": 4500.0,
        "monthly_debt": 1200.0,
        "credit_score": 680,
        "late_payments": 2,
        "credit_utilization": 45.0,
        "products_of_interest": "personal loan or credit card",
    },
    {
        "name": "Andrea Torres",
        "age": 28,
        "monthly_income": 7200.0,
        "monthly_debt": 900.0,
        "credit_score": 760,
        "late_payments": 0,
        "credit_utilization": 15.0,
        "products_of_interest": "auto loan",
    },
    {
        "name": "Miguel Ángel Reyes",
        "age": 45,
        "monthly_income": 2800.0,
        "monthly_debt": 1900.0,
        "credit_score": 580,
        "late_payments": 6,
        "credit_utilization": 82.0,
        "products_of_interest": "personal loan",
    },
]


async def run_tests():
    print("=" * 60)
    print("FinCampaign RAG Agent — End-to-End Test")
    print("=" * 60)

    passed = 0
    failed = 0

    for customer in TEST_CUSTOMERS:
        name = customer["name"]
        score = customer["credit_score"]
        dti = round((customer["monthly_debt"] / customer["monthly_income"]) * 100, 1)
        print(f"\n--- {name} (score: {score}, DTI: {dti}%) ---")

        try:
            result = await orchestrator.analyze_customer(customer)

            print(f"  Request ID:  {result.request_id}")
            print(f"  Segment:     {result.risk_assessment.segment}")
            print(f"  Risk Level:  {result.risk_assessment.risk_level}")
            print(f"  DTI:         {result.risk_assessment.dti}%")
            print(f"  Eligible:    {result.risk_assessment.eligible_for_credit}")
            print(f"  Product:     {result.campaign.product_name}")
            print(f"  Channel:     {result.campaign.channel}")
            print(f"  Rates:       {result.campaign.rates}")
            print(f"  Compliance:  {result.compliance.overall_verdict}")
            print(f"  Human Rev.:  {result.compliance.human_review_required}")
            print(f"  Stored at:   {result.stored_at}")
            print(f"  Time:        {result.processing_time_ms}ms")

            if result.compliance.warnings:
                print(f"  Warnings:    {result.compliance.warnings}")

            passed += 1

        except Exception as exc:
            print(f"  ERROR: {exc}")
            failed += 1

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed out of {len(TEST_CUSTOMERS)} tests")
    print("=" * 60)

    if failed:
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(run_tests())
