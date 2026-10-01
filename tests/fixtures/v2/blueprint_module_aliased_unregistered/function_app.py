import azure.functions as f

bp = f.Blueprint()


@bp.route(route="hello")
def hello(req):
    return req
