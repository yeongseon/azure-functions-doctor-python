import azure.functions as func
from azure_functions_logging import with_context
from azure_functions_validation import validate_http

app = func.FunctionApp()


@app.route(route="inverted")
@validate_http()
@with_context
def inverted(req: func.HttpRequest, context: func.Context) -> func.HttpResponse:
    return func.HttpResponse("inverted")


@app.route(route="uncovered")
def uncovered(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("uncovered")
