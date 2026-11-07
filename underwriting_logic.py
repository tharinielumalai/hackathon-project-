# underwriting_logic.py
import math
from typing import Dict, Any

class MortgageEngine:
    MIN_AGE = 21
    MAX_AGE_AT_MATURITY = 65
    BENCHMARK_INTEREST_RATE = 8.85  # Annual %

    @staticmethod
    def calculate_emi(principal: float, annual_rate_pct: float, tenor_months: int) -> float:
        if principal <= 0 or tenor_months <= 0:
            return 0.0
        r = (annual_rate_pct / 100.0) / 12.0
        return (principal * r * ((1 + r) ** tenor_months)) / (((1 + r) ** tenor_months) - 1)

    @staticmethod
    def calculate_max_loan_from_emi(max_emi: float, annual_rate_pct: float, tenor_months: int) -> float:
        if max_emi <= 0 or tenor_months <= 0:
            return 0.0
        r = (annual_rate_pct / 100.0) / 12.0
        factor = (((1 + r) ** tenor_months) - 1) / (r * ((1 + r) ** tenor_months))
        return max_emi * factor

    def evaluate(self, data: Dict[str, Any]) -> Dict[str, Any]:
        failures = []
        pos_drivers = []
        neg_drivers = []

        applicant = data["applicant"]
        bureau = data["bureau"]
        banking = data["banking"]
        prop = data["property"]
        req_amount = float(data["requested_amount"])
        req_tenor = int(data["requested_tenor_months"])
        loan_type = data["loan_type"]

        # 1. KNOCKOUT CHECKS
        maturity_age = applicant["age"] + (req_tenor / 12.0)
        if applicant["age"] < self.MIN_AGE:
            failures.append(f"Applicant age ({applicant['age']}) is below minimum limit of {self.MIN_AGE}")
        if maturity_age > self.MAX_AGE_AT_MATURITY:
            failures.append(f"Maturity age ({maturity_age:.1f} yrs) exceeds maximum limit of {self.MAX_AGE_AT_MATURITY}")

        if bureau["write_offs_or_settled"]:
            failures.append("Past loan write-offs or settlements recorded in bureau history")
        if bureau["dpd_30_last_12m"] > 0:
            failures.append(f"Active delinquency: {bureau['dpd_30_last_12m']} instance(s) of 30+ DPD in last 12m")
        if prop["cersai_active_charge"]:
            failures.append("Collateral encumbered: Active mortgage charge found on CERSAI")
        if data["fraud"]["vkyc_face_match_score"] < 0.85:
            failures.append(f"V-KYC verification failed (Score: {data['fraud']['vkyc_face_match_score']:.2f} < 0.85)")
        if data["fraud"]["pdf_tamper_detected"]:
            failures.append("Document fraud detected: Internal PDF tampering or font alteration flagged")

        # Stop immediately if knockout rules fail
        if failures:
            return {
                "outcome": "REJECT",
                "sanctioned_amount": 0.0,
                "monthly_emi": 0.0,
                "interest_rate_pct": 0.0,
                "sanctioned_tenor_months": 0,
                "applied_ltv_pct": 0.0,
                "applied_foir_pct": 0.0,
                "failures": failures,
                "positive_drivers": [],
                "negative_drivers": ["Statutory policy criteria violated"]
            }

        # 2. NHB LTV CAPS
        prop_val = float(prop["market_valuation"])
        if loan_type == "HOME_LOAN":
            if req_amount <= 3_000_000:
                max_ltv = 0.90
            elif req_amount <= 7_500_000:
                max_ltv = 0.80
            else:
                max_ltv = 0.75
        else:  # LAP
            max_ltv = 0.60

        max_loan_by_ltv = prop_val * max_ltv

        # 3. AFFORDABILITY & FOIR
        income = float(applicant["net_monthly_income"])
        existing_emis = float(bureau["active_monthly_obligations"])

        if income < 35_000:
            max_foir = 0.50
        elif income <= 75_000:
            max_foir = 0.60
        else:
            max_foir = 0.65

        max_total_emi = income * max_foir
        available_emi = max_total_emi - existing_emis

        if available_emi <= 0:
            failures.append(f"Debt burden: Existing EMIs (₹{existing_emis:,.0f}) exceed maximum permissible FOIR")
            return {
                "outcome": "REJECT",
                "sanctioned_amount": 0.0,
                "monthly_emi": 0.0,
                "interest_rate_pct": 0.0,
                "sanctioned_tenor_months": 0,
                "applied_ltv_pct": 0.0,
                "applied_foir_pct": 0.0,
                "failures": failures,
                "positive_drivers": [],
                "negative_drivers": ["Applicant existing debt obligations exceed affordability limits"]
            }

        max_loan_by_foir = self.calculate_max_loan_from_emi(available_emi, self.BENCHMARK_INTEREST_RATE, req_tenor)
        eligible_amount = min(req_amount, max_loan_by_ltv, max_loan_by_foir)
        eligible_amount = math.floor(eligible_amount / 10_000) * 10_000

        # 4. SCORING & EXPLAINABILITY (SHAP-STYLE)
        cibil = bureau["bureau_score"]
        if cibil >= 750:
            pos_drivers.append(f"Strong bureau score of {cibil} (+35 pts)")
        else:
            neg_drivers.append(f"Sub-optimal bureau score of {cibil} (-30 pts)")

        amb = banking["avg_monthly_balance"]
        if amb >= 50_000:
            pos_drivers.append(f"Healthy average monthly balance of ₹{amb:,.0f} (+25 pts)")
        elif amb < 15_000:
            neg_drivers.append(f"Low liquidity buffer in bank statement (-20 pts)")

        bounces = banking["inward_cheque_bounces_12m"]
        if bounces == 0:
            pos_drivers.append("Flawless banking conduct: 0 cheque/ECS bounces (+20 pts)")
        else:
            neg_drivers.append(f"Cashflow strain: {bounces} cheque bounce(s) detected (-40 pts)")

        if applicant["employment_vintage_years"] >= 3:
            pos_drivers.append(f"High occupational stability: {applicant['employment_vintage_years']} yrs vintage (+15 pts)")

        # Decision routing
        applied_foir = (existing_emis + self.calculate_emi(eligible_amount, self.BENCHMARK_INTEREST_RATE, req_tenor)) / income
        applied_ltv = eligible_amount / prop_val

        if eligible_amount < req_amount * 0.70:
            outcome = "REFER"
        else:
            outcome = "APPROVE"

        emi = self.calculate_emi(eligible_amount, self.BENCHMARK_INTEREST_RATE, req_tenor)

        return {
            "outcome": outcome,
            "sanctioned_amount": eligible_amount,
            "monthly_emi": emi,
            "interest_rate_pct": self.BENCHMARK_INTEREST_RATE,
            "sanctioned_tenor_months": req_tenor,
            "applied_ltv_pct": round(applied_ltv, 4),
            "applied_foir_pct": round(applied_foir, 4),
            "failures": [],
            "positive_drivers": pos_drivers,
            "negative_drivers": neg_drivers
        }
