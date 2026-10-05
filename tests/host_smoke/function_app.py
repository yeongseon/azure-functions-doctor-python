import azure.functions as func

app = func.FunctionApp()


@app.route(route="smoke", auth_level=func.AuthLevel.ANONYMOUS)
def smoke(_req: func.HttpRequest) -> func.HttpResponse:
    return func.HttpResponse("doctor-host-smoke")
