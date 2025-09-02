from datetime import datetime
from typing import Optional, List, Annotated

from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
import httpx
from fastapi import FastAPI, HTTPException, Request, Path
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

app_title = "Son's Lexi Demo API"
version = "0.1.0"


class State(BaseModel):
    id: int
    name: str


class Commission(BaseModel):
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
    def __init__(self, name: str, message: str, status_code: int = 500):
        self.name = name
        self.message = message
        self.status_code = status_code


jagriti_api_url = 'https://e-jagriti.gov.in/services/report/report'
headers = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 '
                  'Safari/537.36'
}


async def fetch_states() -> list[State]:
    """
    Fetches states from Jagriti API and returns it.
    """
    response = httpx.get(jagriti_api_url + "/getStateCommissionAndCircuitBench",
                         headers=headers)
    response.raise_for_status()  # Raises an exception for 4xx/5xx responses
    states = [State(id=item['commissionId'], name=item['commissionNameEn'])
              for item in response.json()['data']]
    return states


async def fetch_commissions(state_id: int) -> list[Commission]:
    """
    Fetches commissions of a state from Jagriti API and returns it.
    """
    response = httpx.get(jagriti_api_url + f"/getDistrictCommissionByCommissionId?commissionId={state_id}",
                         headers=headers)
    response.raise_for_status()
    json = response.json()
    if json['error'] == 'True' or json['status'] != 200:
        raise ApiException(name='fetchError',
                           message=f"Error fetching commissions from API: {json['message']}")
    data = json['data']
    if len(data) == 0:
        raise ApiException(name='notFound',
                           message=f"No state found with this ID",
                           status_code=400)
    commissions = [Commission(id=item['commissionId'], name=item['commissionNameEn'])
                   for item in data]
    return commissions


app = FastAPI(title=app_title, version=version)


@app.exception_handler(ApiException)
async def app_exception_handler(request: Request, e: ApiException):
    return JSONResponse(
        status_code=e.status_code,
        content={"code": e.name, "message": e.message},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, e):
    raise ApiException(name='apiError', message=str(e), status_code=e.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, e):
    error = e.errors()[0]
    if error['loc'][1] == 'state_id':
        raise ApiException(name='invalidId',
                           message='State ID must be an integer',
                           status_code=400)
    return JSONResponse(
        status_code=400,
        content=jsonable_encoder({"detail": e.errors()}),
    )


@app.get("/", tags=["system"])
def about() -> dict:
    return {"app": app_title,
            "version": version}


@app.get("/cases", response_model=list[Case], tags=["cases"])
def list_cases() -> list[Case]:
    return []


@app.get("/states", response_model=list[State], tags=["states"])
async def get_states() -> list[State]:
    try:
        return await fetch_states()
    except Exception as e:
        raise ApiException(name='fetchError',
                           message=F"Error fetching states from API: {e}")


@app.get("/commissions/{state_id}", response_model=list[Commission], tags=["commissions"])
async def get_commissions_by_state(state_id: Annotated[int, Path(title="The ID of the state to get commissions from")]) \
        -> list[Commission]:
    try:
        return await fetch_commissions(state_id)
    except ApiException as e:
        raise e
    except Exception as e:
        raise ApiException(name='fetchError',
                           message=F"Error fetching commissions from API: {e}")
