# mypy: disable-error-code="untyped-decorator"

import azure.functions as func

app = func.FunctionApp()


@app.route(route="smoke", auth_level=func.AuthLevel.ANONYMOUS)
def smoke(req: func.HttpRequest) -> func.HttpResponse:
    del req
    return func.HttpResponse("doctor-host-smoke")
