from chocs import HttpRequest, HttpResponse, Application
from chocs_middleware.xray import AwsXRayMiddleware


app = Application(AwsXRayMiddleware())


@app.get("/hello")
def say_hello(request: HttpRequest) -> HttpResponse:
    ...
