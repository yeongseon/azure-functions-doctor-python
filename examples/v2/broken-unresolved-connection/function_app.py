import azure.functions as func

app = func.FunctionApp()


@app.queue_trigger(arg_name="message", queue_name="tasks", connection="MyStorage")
def process(message: func.QueueMessage) -> None:
    message.get_body()
