import azure.functions as func

app = func.FunctionApp()


@app.route(route="runtime")
def runtime(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("runtime demo")
