"""Blueprint example: Azure Functions Python v2 with a Blueprint.

Demonstrates how to organise functions into a Blueprint module
(`http_blueprint.py`) and register it on the main FunctionApp.
This keeps large projects modular and testable.
"""

import azure.functions as func
from http_blueprint import bp

app = func.FunctionApp()
# Register all functions defined in http_blueprint.py.
app.register_functions(bp)
