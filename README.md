# chocs-aws-xray
AWS X-Ray middleware for chocs library.

## Installation 
through poetry:
```shell
poetry add chocs_middleware.xray
```
or through pip:
```shell
pip install chocs_middleware.xray
```

## Usage

The following snippet is the simplest integration example.

> Please note x-ray won't work in WSGI mode, it has to be deployed as aws lambda in order to work.
> 
```python
from chocs import Application, HttpResponse, serve
from chocs_middleware.xray import AwsXRayMiddleware

app = Application(AwsXRayMiddleware())


@app.get("/hello")
def say_hello(request):
    return HttpResponse("Hello")

serve(app)
```

### Setting up custom error handler

AWS X-Ray middleware provides a way to setup a custom error handler which may become handy when you
need to supplement your logs with additional information. Please consider the following example:

```python
from chocs import Application, HttpResponse, HttpStatus
from chocs_middleware.xray import AwsXRayMiddleware

def error_handler(request, error, segment):
    segment.add_exception(error)
    
    return HttpResponse("NOT OK", HttpStatus.INTERNAL_SERVER_ERROR)

app = Application(AwsXRayMiddleware(error_handler=error_handler))


@app.get("/hello")
def say_hello(request):
    raise Exception("Not Today!")
    return HttpResponse("Hello")

```

> To learn more about error_handler interface please click [here.]("./chocs_middleware/xray/middleware.py:16") 

### Accessing x-ray recorded from within your application layer
```python
from chocs import Application, HttpResponse
from chocs_middleware.xray import AwsXRayMiddleware

app = Application(AwsXRayMiddleware())

@app.get("/hello")
def say_hello(request):
    xray_recorder = request.attributes["aws_xray_recorder"] # Here is the instance of your recorder.
    
    return HttpResponse("OK")

```

That's all.
