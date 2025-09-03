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


class ApiException(Exception):
    def __init__(self, name: str, message: str, status_code: int = 500):
        self.name = name
        self.message = message
        self.status_code = status_code


app = FastAPI(title=app_title, version=version)


@app.exception_handler(ApiException)
async def app_exception_handler(request: Request, e: ApiException):
    return JSONResponse(
        status_code=e.status_code,
        content={'code': e.name, 'message': e.message},
    )


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, e):
    raise ApiException(name='apiError', message=str(e), status_code=e.status_code)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, e):
    error = e.errors()[0]
    error_type = error['type']
    match error['loc'][1]:
        case 'state_id':
            raise ApiException(
                name='invalidId', message='State ID must be an integer', status_code=4
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


@app.get('/', tags=['system'])
def about() -> dict:
    return {'app': app_title, 'version': version}


@app.get('/states', response_model=list[State], tags=['states'])
async def get_states() -> list[State]:
    try:
        return await fetch_states()
    except JagritiError as e:
        raise ApiException(name=e.name, message=e.message)
    except Exception as e:
        raise ApiException(name='fetchError', message=f'Error getting states: {e}')


@app.get(
    '/commissions/{state_id}', response_model=list[Commission], tags=['commissions']
)
async def get_commissions_by_state(
    state_id: Annotated[int, Path(title='The ID of the state to get commissions from')],
) -> list[Commission]:
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
    return await handle_search_cases_by_type(request, SearchType.CASE_NUMBER)


@app.post('/cases/by_complainant', response_model=list[Case], tags=['cases'])
async def search_cases_by_complainant(request: SearchCasesRequest) -> list[Case]:
    return await handle_search_cases_by_type(request, SearchType.COMPLAINANT)


@app.post('/cases/by_complainant_advocate', response_model=list[Case], tags=['cases'])
async def search_cases_by_complainant(request: SearchCasesRequest) -> list[Case]:
    return await handle_search_cases_by_type(request, SearchType.COMPLAINANT_ADVOCATE)


@app.post('/cases/by_respondent', response_model=list[Case], tags=['cases'])
async def search_cases_by_complainant(request: SearchCasesRequest) -> list[Case]:
    return await handle_search_cases_by_type(request, SearchType.RESPONDENT)


@app.post('/cases/by_respondent_advocate', response_model=list[Case], tags=['cases'])
async def search_cases_by_complainant(request: SearchCasesRequest) -> list[Case]:
    return await handle_search_cases_by_type(request, SearchType.RESPONDENT_ADVOCATE)


@app.post('/cases/by_industry_type', response_model=list[Case], tags=['cases'])
async def search_cases_by_industry_type(request: SearchCasesRequest) -> list[Case]:
    return await handle_search_cases_by_type(request, SearchType.INDUSTRY_TYPE)

@app.post('/cases/by_judge', response_model=list[Case], tags=['cases'])
async def search_cases_by_judge(request: SearchCasesRequest) -> list[Case]:
    return await handle_search_cases_by_type(request, SearchType.JUDGE)