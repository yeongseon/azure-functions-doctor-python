import azure.functions as func

app = func.FunctionApp()


@app.route(route="work", auth_level=func.AuthLevel.ANONYMOUS)
def work(req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("ok")
