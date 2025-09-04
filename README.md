This is a demo **FastAPI** application built by Son Nguyen <sonnhjamy@gmail.com> for Lexi, to query information
from **Jagriti** API for serving from a custom API as per task requirements.

- Connects directly to external API, no need for scraping
- Caches fetched static data for efficiency
- Thorough input data validation
- Custom error response with user-friendly messages, ready for direct use by client UI, reducing frontend work

## Codebase

Developed under Python 3.12

- `jagriti.py`: Module for fetching and manage data from Jagriti API
- `main.py`: FastAPI application using Jagriti module for data

Documentation is added intensively in code, and also displayed by the API doc.

## Live Hosted Site

[https://lexi.sonnguyen.online/docs]{https://lexi.sonnguyen.online/docs)

## Notes on Searching Cases

All endpoints require 3 parameters in request body:

- `state_name (str)`: Name of the state to search in (exact case-insensitive matching)
- `commission_name (str)`: Name of the commission to search in (exact case-insensitive matching)
- `query (str)`: Search value, can be case number, complainant's name, etc.

The date range is set from start of this year (Jagriti UI's default) to current day.

The `document_link` field is always set to an empty string, since Jagriti API only returns the document as
embedded Base64-encoded string.

##  

