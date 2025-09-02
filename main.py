from datetime import datetime
from typing import Optional, List

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app_title = "Son's Lexi Demo API"
version = "0.1.0"
app = FastAPI(title=app_title, version=version)


class Case(BaseModel):
    id: int
    stage: str
    filing_date: datetime
    complainant: str
    complainant_advocate: str
    respondent: str
    respondent_advocate: str
    document_link: str


# In-memory "database"
DB: dict[int, Case] = {}


@app.get("/", tags=["system"])
def about() -> dict:
    return {"app": app_title,
            "version": version}


@app.get("/cases", response_model=list[Case], tags=["Cases"])
def list_cases() -> list[Case]:
    return list(DB.values())


@app.get("/cases/{case_id}", response_model=Case, tags=["Cases"])
def get_case(case_id: int) -> Case:
    case = DB.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case


@app.post("/cases", response_model=Case, status_code=201, tags=["Cases"])
def create_case(case: Case) -> Case:
    if case.id in DB:
        raise HTTPException(status_code=409, detail="Case with this id already exists")
    DB[case.id] = case
    return case


@app.put("/cases/{case_id}", response_model=Case, tags=["Cases"])
def update_case(case_id: int, case: Case) -> Case:
    if case_id != case.id:
        raise HTTPException(status_code=400, detail="Path id and body id must match")
    if case_id not in DB:
        raise HTTPException(status_code=404, detail="Case not found")
    DB[case_id] = case
    return case


@app.delete("/cases/{case_id}", status_code=204, tags=["Cases"])
def delete_case(case_id: int) -> None:
    if case_id not in DB:
        raise HTTPException(status_code=404, detail="Case not found")
    del DB[case_id]
    return None
