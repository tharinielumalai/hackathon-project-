import streamlit as st
import requests
import time

st.set_page_config(page_title="Hero Housing Underwriting Portal", page_icon="🏠", layout="wide")

st.title("🏠 Hero Housing Autonomous Underwriting Portal")
st.caption("Client Application Form (Sends user inputs directly to FastAPI Backend)")
st.write("---")

# Backend API URL
BACKEND_URL = "http://127.0.0.1:8000/api/underwrite"

# Form for user inputs
with st.form("mortgage_form"):
    col1, col2, col3 = st.columns(3)

    with col1:
        st.subheader("1. Applicant Details")
        full_name = st.text_input("Full Name", value="Arjun Sharma")
        age = st.number_input("Age (Years)", min_value=18, max_value=75, value=29)
        income = st.number_input("Net Monthly Income (₹)", min_value=10000, max_value=2000000, value=85000, step=5000)
        vintage = st.number_input("Job/Business Vintage (Years)", min_value=0, max_value=40, value=4)
        loan_type = st.selectbox("Loan Type", ["HOME_LOAN", "LAP"])

    with col2:
        st.subheader("2. Bureau & Banking Inputs")
        cibil = st.slider("CIBIL Score", min_value=300, max_value=900, value=780)
        existing_emis = st.number_input("Existing Monthly EMIs (₹)", min_value=0, max_value=500000, value=10000, step=1000)
        dpd_30 = st.number_input("30+ DPD (Past 12 Months)", min_value=0, max_value=12, value=0)
        write_offs = st.checkbox("Historical Loan Write-offs or Settlements", value=False)
        amb = st.number_input("Average Monthly Balance (₹)", min_value=0, max_value=1000000, value=55000, step=5000)
        bounces = st.number_input("Inward Cheque/ECS Bounces (12m)", min_value=0, max_value=10, value=0)

    with col3:
        st.subheader("3. Loan, Collateral & Fraud Flags")
        req_loan = st.number_input("Requested Loan Amount (₹)", min_value=100000, max_value=50000000, value=3500000, step=100000)
        req_tenor = st.number_input("Tenor (Months)", min_value=12, max_value=360, value=240, step=12)
        prop_val = st.number_input("Property Valuation (₹)", min_value=500000, max_value=100000000, value=4500000, step=100000)
        cersai_charge = st.checkbox("CERSAI Active Charge Found", value=False)
        vkyc_score = st.slider("V-KYC Face Match Score", min_value=0.0, max_value=1.0, value=0.92, step=0.01)
        pdf_tamper = st.checkbox("PDF Tampering Flagged", value=False)

    submit_button = st.form_submit_button("Submit Application to Backend Engine", type="primary", use_container_width=True)

# Processing when user clicks Submit
if submit_button:
    payload = {
        "application_id": f"APP-{int(time.time())}",
        "loan_type": loan_type,
        "requested_amount": float(req_loan),
        "requested_tenor_months": int(req_tenor),
        "applicant": {
            "full_name": full_name,
            "age": int(age),
            "net_monthly_income": float(income),
            "employment_vintage_years": int(vintage)
        },
        "bureau": {
            "bureau_score": int(cibil),
            "active_monthly_obligations": float(existing_emis),
            "dpd_30_last_12m": int(dpd_30),
            "write_offs_or_settled": write_offs
        },
        "banking": {
            "avg_monthly_balance": float(amb),
            "inward_cheque_bounces_12m": int(bounces)
        },
        "property": {
            "market_valuation": float(prop_val),
            "cersai_active_charge": cersai_charge
        },
        "fraud": {
            "vkyc_face_match_score": float(vkyc_score),
            "pdf_tamper_detected": pdf_tamper
        }
    }

    try:
        with st.spinner("Connecting to FastAPI backend at port 8000..."):
            response = requests.post(BACKEND_URL, json=payload, timeout=5)
            response.raise_for_status()
            data = response.json()
            res = data["result"]

        st.write("---")
        st.header(f"Decision for {data['applicant_name']} (ID: {data['application_id']})")

        if res["outcome"] == "APPROVE":
            st.success("### Status: APPROVED (Straight-Through Processing)")
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Sanctioned Amount", f"₹{res['sanctioned_amount']:,.0f}")
            c2.metric("Interest Rate", f"{res['interest_rate_pct']:.2f}% p.a.")
            c3.metric("Monthly EMI", f"₹{res['monthly_emi']:,.0f}")
            c4.metric("Applied LTV / FOIR", f"{res['applied_ltv_pct']*100:.1f}% / {res['applied_foir_pct']*100:.1f}%")

            if res["sanctioned_amount"] < req_loan:
                st.warning(f"⚠️ Requested ₹{req_loan:,.0f} was auto-downsized to ₹{res['sanctioned_amount']:,.0f} to satisfy statutory NHB LTV caps.")

        elif res["outcome"] == "REJECT":
            st.error("### Status: REJECTED (Adverse Action Notice)")
            st.write("**Identified Knockout Violations:**")
            for fail in res["failures"]:
                st.markdown(f"- ❌ {fail}")

        else:
            st.warning("### Status: REFER TO CREDIT MANAGER (Amber Channel)")
            st.info("Application falls into intermediate risk band or requires manual property legal review.")

        # Explainability Drivers
        st.write("#### Decision Attribution (SHAP Factors)")
        e1, e2 = st.columns(2)
        with e1:
            st.markdown("**Positive Contributing Factors (+):**")
            for p in res.get("positive_drivers", []):
                st.markdown(f"- ✅ {p}")
        with e2:
            st.markdown("**Negative Contributing Factors (-):**")
            for n in res.get("negative_drivers", []):
                st.markdown(f"- ⚠️ {n}")

    except requests.exceptions.ConnectionError:
        st.error("🚨 Error: Unable to connect to the backend server. Make sure `backend_api.py` is running on port 8000!")
    except Exception as e:
        st.error(f"An unexpected error occurred: {e}")
