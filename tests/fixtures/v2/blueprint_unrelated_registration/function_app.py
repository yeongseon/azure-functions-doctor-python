import azure.functions as func


class Loader:
    def register_functions(self, blueprint):
        return blueprint


app = func.FunctionApp()
bp = func.Blueprint()


@bp.route(route="hello")
def hello(req):
    return req


Loader().register_functions(bp)
