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
    """Error raised by this module"""

    def __init__(self, name: str, message):
        self.name = name
        self.message = message


async def fetch_api(
    url: str, data_name='data', method: str = 'GET', data: dict | None = None
) -> list:
    """
    Common function to Fetch data from Jagriti API.

    Raises error if API call fails.

    Parameters:
        url (str): The API endpoint URL relative to base; must start with slash.
        data_name (str): Name of the data to fetch, used for error messages.
        method (str): HTTP method, GET by default
        data (dict): payload for POST fetch

    Returns:
        list: The fetched data, which is a JSON list in all cases.
    """

    # Base API URL for all endpoints
    jagriti_api_url = 'https://e-jagriti.gov.in/services'
    # Must spoof a standard browser to allow access
    headers = {
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 '
        'Safari/537.36',
        'content-type': 'application/json',
    }
    response = (
        httpx.get(jagriti_api_url + url, headers=headers)
        if method.upper() == 'GET'
        else httpx.post(jagriti_api_url + url, headers=headers, json=data)
    )
    # Raises an exception for 4xx/5xx responses
    response.raise_for_status()
    json = response.json()
    data = json['data']
    if json['error'].lower() == 'true' or json['status'] != 200 or data is None:
        raise JagritiError(
            name='fetchError',
            message=f'Error fetching {data_name} from API: {json["message"]}',
        )
    return data


##
# These two functions fetch common data from Jagriti API.
# For performance, the fetched results are cached on first use for later reuse
# As the cache is invalidated on app restart, and these data are extremely unlikely to change,
#    there is no risk of stale data
##

stored_states: list[State] = []


async def fetch_states() -> list[State]:
    """
    Fetch states from Jagriti API and return in a list.
    """
    global stored_states
    if len(stored_states) > 0:
        print('Reusing cached states')
        return stored_states

    data = await fetch_api('/report/report/getStateCommissionAndCircuitBench', 'states')
    states = [
        State(id=item['commissionId'], name=item['commissionNameEn']) for item in data
    ]
    stored_states = states
    return states


stored_commissions_by_state: dict[int, list[Commission]] = {}


async def fetch_commissions_by_state(state_id: int) -> list[Commission]:
    """
    Fetch commissions of a state from Jagriti API and return in a list.

    Parameters:
        state_id (int): ID of the state to fetch commissions for.
    """
    global stored_states
    global stored_commissions_by_state
    # Check for state existence first if cache is available
    if len(stored_states) > 0:
        states = [s for s in stored_states if s.id == state_id]
        if len(states) == 0:
            raise JagritiError(name='notFound', message=f'No state found with this ID')

    commissions = stored_commissions_by_state.get(state_id)
    if commissions is not None:
        print(f'Reusing cached commissions by state ID {state_id}')
        return commissions

    data = await fetch_api(
        f'/report/report/getDistrictCommissionByCommissionId?commissionId={state_id}',
        'commissions',
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
    """Get a state by its ID"""
    states = [s for s in await fetch_states() if s.id == state_id]
    return states[0] if len(states) > 0 else None


async def get_state_by_name(state_name: str) -> State | None:
    """Get a state by its name, using exact case-insensitive string matching."""
    states = [
        s for s in await fetch_states() if s.name.lower() == state_name.strip().lower()
    ]
    # Replace with below for non-exact (inclusion) string matching
    # states = [s for s in await fetch_states() if state_name.strip().lower() in s.name.lower()]
    return states[0] if len(states) > 0 else None


async def get_commission_by_name(
    commission_name: str, state_id: int
) -> Commission | None:
    """
    Get a commission by its name, using exact case-insensitive string matching.

    Requires ID of the state.
    """
    state = await get_state_by_id(state_id)
    if state is None:
        return None
    commissions = [
        c
        for c in await fetch_commissions_by_state(state_id)
        if c.name.lower() == commission_name.strip().lower()
    ]
    # Replace with below for non-exact (inclusion) string matching
    # commissions = [c for c in await fetch_commissions_by_state(state_id)
    #       if commission_name.strip().lower() in c.name.lower()]
    return commissions[0] if len(commissions) > 0 else None


class SearchType(Enum):
    """Search types for case search as used by Jagriti API."""

    CASE_NUMBER = 1
    COMPLAINANT = 2
    RESPONDENT = 3
    COMPLAINANT_ADVOCATE = 4
    RESPONDENT_ADVOCATE = 5
    INDUSTRY_TYPE = 6
    JUDGE = 7


async def search_cases_by_type(
    state_name: str, commission_name: str, query: str, search_type: SearchType
) -> list[Case]:
    """
    Search cases from Jagriti API based on search type and value.

    Parameters:
        state_name (str): Name of the state to search in. Must be exact but case-insensitive.
        commission_name (str): Name of the commission to search in. Must be exact but case-insensitive.
        search_type (SearchType): Type of search to perform.
    """

    # Find state and commission by name internally
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
    # If search by judge, fetch judge list from API and retrieves first judge whose name matches query, if any.
    # The name matching is non-exact and case-insensitive.
    if search_type == SearchType.JUDGE:
        data = await fetch_api(
            f'/master/master/v2/getJudgeListForHearing?commissionId={commission.id}&activeStatus=true',
            'judge list',
            'POST',
        )
        judges = [j for j in data if query.lower() in j['judgesNameEn'].lower()]
        if len(judges) > 0:
            judge_id = judges[0]['judgeId']

    # Build payload for API call.
    data = {
        'commissionId': commission.id,
        'orderType': 1,
        'dateRequestType': 1,
        'serchType': search_type.value,
        'serchTypeValue': search_type.value
        if search_type == SearchType.INDUSTRY_TYPE or search_type == SearchType.JUDGE
        else query,
        'fromDate': '2025-01-01',  # From date same as default used by Jagriti UI
        'toDate': datetime.today().strftime('%Y-%m-%d'),  # Use current date as to date
        'judgeId': judge_id,
    }
    # print(data)
    data = await fetch_api(
        f'/case/caseFilingService/v2/getCaseDetailsBySearchType', 'cases', 'POST', data
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



