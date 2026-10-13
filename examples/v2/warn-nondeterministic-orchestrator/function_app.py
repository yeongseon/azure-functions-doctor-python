import random

import azure.durable_functions as df
import azure.functions as func

app = df.DFApp(http_auth_level=func.AuthLevel.FUNCTION)


@app.orchestration_trigger(context_name="context")
def orchestrator(context: df.DurableOrchestrationContext) -> int:
    return random.randint(1, 9)
