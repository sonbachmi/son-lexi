from datetime import datetime

import httpx
from pydantic import BaseModel


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


class JagritiError(Exception):
    def __init__(self, name: str, message):
        self.name = name
        self.message = message


jagriti_api_url = 'https://e-jagriti.gov.in/services'
headers = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 '
                  'Safari/537.36'
}


async def fetch_states() -> list[State]:
    """
    Fetches states from Jagriti API and returns it.
    """
    response = httpx.get(jagriti_api_url + "/report/report/getStateCommissionAndCircuitBench",
                         headers=headers)
    response.raise_for_status()  # Raises an exception for 4xx/5xx responses
    states = [State(id=item['commissionId'], name=item['commissionNameEn'])
              for item in response.json()['data']]
    return states


async def fetch_commissions(state_id: int) -> list[Commission]:
    """
    Fetches commissions of a state from Jagriti API and returns it.
    """
    response = httpx.get(
        jagriti_api_url + f"/report/report/getDistrictCommissionByCommissionId?commissionId={state_id}",
        headers=headers)
    response.raise_for_status()
    json = response.json()
    if json['error'] == 'True' or json['status'] != 200:
        raise JagritiError(name='fetchError',
                           message=f"Error fetching commissions from API: {json['message']}")
    data = json['data']
    if len(data) == 0:
        raise JagritiError(name='notFound',
                           message=f"No state found with this ID")
    commissions = [Commission(id=item['commissionId'], name=item['commissionNameEn'])
                   for item in data]
    return commissions
