from typing import Annotated

from fastapi import FastAPI, Request, Path
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

from jagriti import (
    State,
    Commission,
    Case,
    SearchType,
    JagritiError,
    fetch_states,
    fetch_commissions_by_state,
    search_cases_by_type,
)

app_title = "Son's Lexi Demo API"
version = '0.1.0'
description = """

This is a demo **FastAPI** application built by Son Nguyen <sonnhjamy@gmail.com> for Lexi, to query information
 from **Jagriti** API for serving from a custom API as per task requirements.

- Connects directly to external API, no need for scraping
- Caches fetched static data for efficiency
- Thorough input data validation
- Custom error response with user-friendly messages, ready for direct use by client UI, reducing frontend work

### Notes on searching cases

All endpoints require 3 parameters in request body:

- `state_name (str)`: Name of the state to search in (exact case-insensitive matching)
- `commission_name (str)`: Name of the commission to search in (exact case-insensitive matching)
- `query (str)`: Search value, can be case number, complainant's name, etc.
    
The date range is set from start of this year (Jagriti UI's default) to current day.

The `document_link` field is always set to an empty string, since Jagriti API only returns the document as
embedded Base64-encoded string.

---
For more technical details, refer to [Readme](https://github.com/sonbachmi/son-lexi/blob/main/README.md) in codebase.

"""


class ApiException(Exception):
    """
    Custom exception raised by this module.

    To be sent to client in custom error response format.
    """
    def __init__(self, name: str, message: str, status_code: int = 500):
        self.name = name
        self.message = message
        self.status_code = status_code


class ErrorResponse(BaseModel):
    """Custom error response to return to client, replacing FastAPI's default."""
    error: str
    message: str

app = FastAPI(title=app_title, version=version, description=description)


@app.exception_handler(ApiException)
async def app_exception_handler(request, e: ApiException):
    return JSONResponse(
        status_code=e.status_code,
        content=jsonable_encoder(ErrorResponse(error = e.name, message = e.message))
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, e):
    raise ApiException(name='apiError', message=str(e), status_code=e.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, e):
    """Custom data validation error handler to return custom error response format."""
    error = e.errors()[0]
    error_type = error['type']
    loc = error['loc']
    match loc[len(loc)-1]:
        case 'state_id':
            raise ApiException(
                name='invalidId', message='State ID must be an integer', status_code=422
            )
        case 'state_name':
            if error_type == 'missing':
                raise ApiException(
                    name='noData', message='Missing state name', status_code=422
                )
            else:
                raise ApiException(
                    name='invalidData',
                    message='State name must be a string',
                    status_code=422,
                )
        case 'commission_name':
            if error_type == 'missing':
                raise ApiException(
                    name='noData',
                    message='Missing commission name',
                    status_code=422,
                )
            else:
                raise ApiException(
                    name='invalidData',
                    message='Commission name must be a string',
                    status_code=422,
                )
        case 'query':
            if error_type == 'missing':
                raise ApiException(
                    name='noData',
                    message='Missing search value',
                    status_code=422,
                )
            else:
                raise ApiException(
                    name='invalidData',
                    message='Search value must be a string',
                    status_code=422,
                )
        case _:
            return JSONResponse(
                status_code=400,
                content=jsonable_encoder({'detail': e.errors()}),
            )


class AboutResponse(BaseModel):
    app: str
    version: str
@app.get('/', tags=['info'])
def about() -> AboutResponse:
    """Get information about this application."""
    return AboutResponse(app = app_title, version = version)


@app.get('/states', response_model=list[State], tags=['states'])
async def get_states() -> list[State]:
    """Get list of all states."""
    try:
        return await fetch_states()
    except JagritiError as e:
        raise ApiException(name=e.name, message=e.message)
    except Exception as e:
        raise ApiException(name='fetchError', message=f'Error getting states: {e}')


@app.get(
    '/commissions/{state_id}', response_model=list[Commission] | ErrorResponse, tags=['commissions']
)
async def get_commissions_by_state(
    state_id: Annotated[int, Path(title='The ID of the state to get commissions from')],
) -> list[Commission]:
    """
    Get list of commissions by state.

    Parameters (in path):

         state_id (int): The ID of the state to get commissions from.
    """
    try:
        return await fetch_commissions_by_state(state_id)
    except JagritiError as e:
        raise ApiException(
            name=e.name,
            message=e.message,
            status_code=400 if e.name == 'notFound' else 500,
        )
    except Exception as e:
        raise ApiException(name='fetchError', message=f'Error getting states: {e}')


class SearchCasesRequest(BaseModel):
    state_name: str
    commission_name: str
    query: str


async def handle_search_cases_by_type(
    request: SearchCasesRequest, search_type: SearchType
) -> list[Case]:
    """
    Common function to search for cases from Jagriti API.

    Acts as FastAPI path operation, to be used by all endpoints below.

    Parameters:
        request (SearchCasesRequest): The request body containing search data.
        search_type (SearchType): The type of search to perform, as defined by Jagriti API.

    Returns:
        list[Case]: The fetched list of cases, to be sent as JSON to client.
    """
    # Input validation: make sure all required data is not empty
    if len(request.state_name) == 0:
        raise ApiException(
            name='emptyData',
            message='Missing state name',
            status_code=422,
        )
    if len(request.commission_name) == 0:
        raise ApiException(
            name='emptyData',
            message='Missing commission name',
            status_code=422,
        )
    if len(request.query) == 0:
        raise ApiException(
            name='emptyData',
            message='Missing search value',
            status_code=422,
        )
    try:
        return await search_cases_by_type(
            request.state_name, request.commission_name, request.query, search_type
        )
    except JagritiError as e:
        raise ApiException(
            name=e.name,
            message=e.message,
            status_code=400 if e.name == 'notFound' else 500,
        )
    except Exception as e:
        raise ApiException(name='fetchError', message=f'Error searching cases: {e}')


@app.post('/cases/by_case_number', response_model=list[Case], tags=['cases'])
async def search_cases_by_case_number(request: SearchCasesRequest) -> list[Case]:
    """Search cases by exact case number."""
    return await handle_search_cases_by_type(request, SearchType.CASE_NUMBER)


@app.post('/cases/by_complainant', response_model=list[Case], tags=['cases'])
async def search_cases_by_complainant(request: SearchCasesRequest) -> list[Case]:
    """Search cases by complainant's name."""
    return await handle_search_cases_by_type(request, SearchType.COMPLAINANT)


@app.post('/cases/by_complainant_advocate', response_model=list[Case], tags=['cases'])
async def search_cases_by_complainant_advocate(request: SearchCasesRequest) -> list[Case]:
    """Search cases by complainant advocate's name."""
    return await handle_search_cases_by_type(request, SearchType.COMPLAINANT_ADVOCATE)


@app.post('/cases/by_respondent', response_model=list[Case], tags=['cases'])
async def search_cases_by_respondent(request: SearchCasesRequest) -> list[Case]:
    """Search cases by respondent's name."""
    return await handle_search_cases_by_type(request, SearchType.RESPONDENT)


@app.post('/cases/by_respondent_advocate', response_model=list[Case], tags=['cases'])
async def search_cases_by_respondent_advocate(request: SearchCasesRequest) -> list[Case]:
    """Search cases by respondent advocate's name."""
    return await handle_search_cases_by_type(request, SearchType.RESPONDENT_ADVOCATE)


@app.post('/cases/by_industry_type', response_model=list[Case], tags=['cases'])
async def search_cases_by_industry_type(request: SearchCasesRequest) -> list[Case]:
    """
    Search cases by industry type.

    Jagriti API appears to ignore the search value and always return an empty list,
    though a likely bug in the portal UI still displays results from the previous search.
    """
    return await handle_search_cases_by_type(request, SearchType.INDUSTRY_TYPE)

@app.post('/cases/by_judge', response_model=list[Case], tags=['cases'])
async def search_cases_by_judge(request: SearchCasesRequest) -> list[Case]:
    """
    Search cases by judge's name.

    Returns list of cases from the first judge found whose name matches the query (non-exact, case-insensitive), if any
    """
    return await handle_search_cases_by_type(request, SearchType.JUDGE)