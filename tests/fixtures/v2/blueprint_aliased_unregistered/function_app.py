import azure.functions as func
from azure.functions import Blueprint as BP

app = func.FunctionApp()
bp = BP()


@bp.route(route="hello")
def hello(req):
    return req
