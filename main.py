from typing import Annotated

from fastapi import FastAPI, Request, Path
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from jagriti import (
    fetch_states,
    fetch_commissions,
    State,
    Commission,
    Case,
    JagritiError,
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
    if error['loc'][1] == 'state_id':
        raise ApiException(
            name='invalidId', message='State ID must be an integer', status_code=400
        )
    return JSONResponse(
        status_code=400,
        content=jsonable_encoder({'detail': e.errors()}),
    )


@app.get('/', tags=['system'])
def about() -> dict:
    return {'app': app_title, 'version': version}


@app.get('/cases', response_model=list[Case], tags=['cases'])
def list_cases() -> list[Case]:
    return []


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
        return await fetch_commissions(state_id)
    except JagritiError as e:
        raise ApiException(
            name=e.name,
            message=e.message,
            status_code=400 if e.name == 'notFound' else 500,
        )
    except Exception as e:
        raise ApiException(name='fetchError', message=f'Error getting states: {e}')
