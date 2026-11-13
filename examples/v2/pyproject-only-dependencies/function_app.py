import logging

import azure.functions as func

app = func.FunctionApp()


@app.route(route="HttpExample", auth_level=func.AuthLevel.ANONYMOUS)
def HttpExample(req: func.HttpRequest) -> func.HttpResponse:  # noqa: N802 (Azure style name retained)
    """Basic HTTP trigger function (Programming Model v2).

    Returns a greeting. If a name is provided via query string or JSON body,
    it personalizes the response.
    """
    logging.info("Python v2 HTTP trigger function processed a request.")

    name = req.params.get("name")
    if not name:
        try:
            req_body = req.get_json()
        except ValueError:
            req_body = {}
        name = req_body.get("name")

    if name:
        return func.HttpResponse(
            f"Hello, {name}. This v2 HTTP triggered function executed successfully.",
            status_code=200,
        )
    return func.HttpResponse(
        "This v2 HTTP triggered function executed successfully. "
        "Pass a name in the query string or request body for a personalized response.",
        status_code=200,
    )
