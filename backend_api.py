# backend_api.py
from fastapi import FastAPI
from pydantic import BaseModel
from underwriting_logic import MortgageEngine

app = FastAPI(title="Hero Housing Underwriting API", version="1.0")
engine = MortgageEngine()

# Input Data Schema
class UnderwritingRequest(BaseModel):
    application_id: str
    loan_type: str
    requested_amount: float
    requested_tenor_months: int
    applicant: dict
    bureau: dict
    banking: dict
    property: dict
    fraud: dict

@app.get("/")
def health_check():
    return {"status": "ONLINE", "message": "Hero Underwriting Engine API is healthy"}

@app.post("/api/underwrite")
def process_underwriting(request: UnderwritingRequest):
    # Convert incoming Pydantic payload to dict and pass to engine
    result = engine.evaluate(request.model_dump())
    return {
        "application_id": request.application_id,
        "applicant_name": request.applicant.get("full_name", "Applicant"),
        "result": result
    }

if __name__ == "__main__":
    import uvicorn
    # Runs the server on localhost port 8000
    uvicorn.run("backend_api:app", host="127.0.0.1", port=8000, reload=True)
