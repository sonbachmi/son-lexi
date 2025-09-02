from datetime import datetime
from typing import Optional, List

from pydantic import BaseModel
import httpx
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

app_title = "Son's Lexi Demo API"
version = "0.1.0"


class State(BaseModel):
    id: int
    name: str


class Case(BaseModel):
    id: int
    stage: str
    filing_date: datetime
    complainant: str
    complainant_advocate: str
    respondent: str
    respondent_advocate: str
    document_link: str


class ApiException(Exception):
    def __init__(self, name: str, message: str):
        self.name = name
        self.message = message


jagriti_api_url = 'https://e-jagriti.gov.in'
headers = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 '
                  'Safari/537.36'
}

async def fetch_states() -> list[State]:
    """
    Fetches states from Jagriti API and returns it.
    """
    response = httpx.get(jagriti_api_url + "/services/report/report/getStateCommissionAndCircuitBench",
                         headers=headers)
    response.raise_for_status()  # Raises an exception for 4xx/5xx responses
    states = [State(id=item['commissionId'], name=item['commissionNameEn'])
              for item in response.json()['data']]
    return states


app = FastAPI(title=app_title, version=version)


@app.exception_handler(ApiException)
async def app_exception_handler(request: Request, e: ApiException):
    return JSONResponse(
        status_code=500,
        content={"code": e.name, "message": e.message},
    )


@app.get("/", tags=["system"])
def about() -> dict:
    return {"app": app_title,
            "version": version}


@app.get("/cases", response_model=list[Case], tags=["cases"])
def list_cases() -> list[Case]:
    return list(DB.values())


@app.get("/states", response_model=list[State], tags=["states"])
async def get_states() -> list[State]:
    try:
        return await fetch_states()
    except Exception as e:
        raise ApiException(name='fetchError',
                           message=F"Error fetching from API: {e}")
