import azure.functions as func

app = func.FunctionApp()


@app.route(route="dependencies")
def dependencies(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("dependency demo")
