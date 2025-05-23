from typing import Any

from fastapi import FastAPI, HTTPException, Security, Body
from fastapi.security import OAuth2PasswordBearer
from fastapi.responses import StreamingResponse
from orjson import orjson

from flux.catalogs import WorkflowCatalog
from flux.context_managers import ContextManager

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def validate_token(token):
    # TODO
    is_valid = True
    error_message = None
    return is_valid, error_message


@app.post("/{workflow}", response_model=dict[str, Any])
async def execute(
    workflow: str,
    input: Any = Body(default=None),
    token: str = Security(oauth2_scheme),
):
    if not validate_token(token):
        is_valid, error_message = validate_token(token)
        if not is_valid:
            raise HTTPException(status_code=401, detail=f"Token validation failed: {error_message}")

    wf = WorkflowCatalog.create().get(workflow).code
    ctx = await wf.run(input)
    return ctx.summary()

@app.get("/monitor/{execution_id}")
async def monitor(execution_id: str):
    async def stream_logs():
        ctx = ContextManager.default().get(execution_id)
        for event in ctx.events:
            yield f"data: {orjson.dumps(event.__dict__)}\n\n"
    return StreamingResponse(stream_logs(), media_type="text/event-stream")