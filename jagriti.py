from datetime import datetime
from enum import Enum

import httpx
from pydantic import BaseModel


class State(BaseModel):
    id: int
    name: str


class Commission(BaseModel):
    id: int
    name: str


class Case(BaseModel):
    case_number: str
    case_stage: str
    filing_date: str
    complainant: str | None
    complainant_advocate: str | None
    respondent: str | None
    respondent_advocate: str | None
    document_link: str


class JagritiError(Exception):
    def __init__(self, name: str, message):
        self.name = name
        self.message = message


jagriti_api_url = 'https://e-jagriti.gov.in/services'
headers = {
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 '
        'Safari/537.36',
    'content-type': 'application/json'
}

##
# These two functions fetch data from Jagriti API.
# For performance, the fetched results are cached on first use for later reuse
# As the cache is invalidated on app restart, and these data are extremely unlikely to change,
#    there is no risk of stale data
##

stored_states: list[State] = []


async def fetch_states() -> list[State]:
    """
    Fetches states from Jagriti API and returns it.
    """
    global stored_states
    if len(stored_states) > 0:
        print('Reusing cached states')
        return stored_states

    response = httpx.get(
        jagriti_api_url + '/report/report/getStateCommissionAndCircuitBench',
        headers=headers,
    )
    response.raise_for_status()  # Raises an exception for 4xx/5xx responses
    states = [
        State(id=item['commissionId'], name=item['commissionNameEn'])
        for item in response.json()['data']
    ]
    stored_states = states
    return states


stored_commissions_by_state: dict[int, list[Commission]] = {}


async def fetch_commissions_by_state(state_id: int) -> list[Commission]:
    """
    Fetches commissions of a state from Jagriti API and returns it.
    """
    global stored_states
    global stored_commissions_by_state
    if len(stored_states) > 0:
        states = [s for s in stored_states if s.id == state_id]
        if len(states) == 0:
            raise JagritiError(name='notFound', message=f'No state found with this ID')
    commissions = stored_commissions_by_state.get(state_id)
    if commissions is not None:
        print(f'Reusing cached commissions by state ID {state_id}')
        return commissions

    response = httpx.get(
        jagriti_api_url
        + f'/report/report/getDistrictCommissionByCommissionId?commissionId={state_id}',
        headers=headers,
    )
    response.raise_for_status()
    json = response.json()
    data = json['data']
    if json['error'].lower() == 'true' or json['status'] != 200 or data is None:
        raise JagritiError(
            name='fetchError',
            message=f'Error fetching commissions from API: {json["message"]}',
        )
    if len(data) == 0:
        raise JagritiError(name='notFound', message=f'No state found with this ID')
    commissions = [
        Commission(id=item['commissionId'], name=item['commissionNameEn'])
        for item in data
    ]
    stored_commissions_by_state[state_id] = commissions
    return commissions


async def get_state_by_id(state_id: int) -> State | None:
    states = [s for s in await fetch_states() if s.id == state_id]
    return states[0] if len(states) > 0 else None


async def get_state_by_name(state_name: str) -> State | None:
    states = [
        s for s in await fetch_states() if s.name.lower() == state_name.strip().lower()
    ]
    # Replace with below for non-exact (inclusion) text matching
    # states = [s for s in await fetch_states() if state_name.strip().lower() in s.name.lower()]
    return states[0] if len(states) > 0 else None


async def get_commission_by_name(
    commission_name: str, state_id: int
) -> Commission | None:
    state = await get_state_by_id(state_id)
    if state is None:
        return None
    commissions = [
        c
        for c in await fetch_commissions_by_state(state_id)
        if c.name.lower() == commission_name.strip().lower()
    ]
    # Replace with below for non-exact (inclusion) text matching
    # commissions = [c for c in await fetch_commissions_by_state(state_id)
    #       if commission_name.strip().lower() in c.name.lower()]
    return commissions[0] if len(commissions) > 0 else None


class SearchType(Enum):
    CASE_NUMBER = 1
    COMPLAINANT = 2
    RESPONDENT = 3
    COMPLAINANT_ADVOCATE = 4
    RESPONDENT_ADVOCATE = 5
    INDUSTRY_TYPE = 6
    JUDGE = 7


async def search_cases_by_type(state_name: str, commission_name: str, query: str, search_type: SearchType) -> list[Case]:
    state = await get_state_by_name(state_name)
    if state is None:
        raise JagritiError(
            name='notFound', message=f'No state found with name "{state_name}"'
        )
    commission = await get_commission_by_name(commission_name, state.id)
    if commission is None:
        raise JagritiError(
            name='notFound',
            message=f'No commission with name "{commission_name}" found in state "{state_name}"',
        )

    judge_id: int | str = ''
    if search_type == SearchType.JUDGE:
        response = httpx.post(
            jagriti_api_url + f'/master/master/v2/getJudgeListForHearing?commissionId={commission.id}&activeStatus=true',
            headers=headers
        )
        response.raise_for_status()
        json = response.json()
        data = json['data']
        if json['error'].lower() == 'true' or json['status'] != 200 or data is None:
            raise JagritiError(
                name='fetchError',
                message=f'Error fetching judge list from API: {json["message"]}',
            )
        judges = [j for j in data if query.lower() in j['judgesNameEn'].lower()]
        if len(judges) > 0:
            judge_id = judges[0]['judgeId']

    data = {
        'commissionId': commission.id,
        'orderType': 1,
        'dateRequestType': 1,
        'serchType': search_type.value,
        'serchTypeValue': search_type.value if search_type == SearchType.INDUSTRY_TYPE or search_type == SearchType.JUDGE
            else query,
        'fromDate': '2025-01-01',
        'toDate': datetime.today().strftime("%Y-%m-%d"),
        'judgeId': judge_id
    }
    print(data)
    response = httpx.post(
        jagriti_api_url + f'/case/caseFilingService/v2/getCaseDetailsBySearchType',
        headers=headers,
        json=data,
    )
    response.raise_for_status()
    json = response.json()
    data = json['data']
    if json['error'].lower() == 'true' or json['status'] != 200 or data is None:
        raise JagritiError(
            name='fetchError',
            message=f'Error fetching cases from API: {json["message"]}',
        )
    cases = [
        Case(
            case_number=item['caseNumber'],
            case_stage=item['caseStageName'],
            filing_date=item['caseFilingDate'],
            complainant=item['complainantName'],
            complainant_advocate=item['complainantAdvocateName'],
            respondent=item['respondentName'],
            respondent_advocate=item['respondentAdvocateName'],
            document_link='',
        )
        for item in data
    ]
    return cases
