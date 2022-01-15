from aws_xray_sdk.core import xray_recorder
from chocs_middleware.xray import AwsXRayMiddleware
from chocs import HttpRequest, HttpResponse, Application, HttpMethod, HttpStatus
from unittest import mock


def test_can_instantiate() -> None:
    # given
    instance = AwsXRayMiddleware()

    # then
    assert isinstance(instance, AwsXRayMiddleware)


def test_is_handler_providing_its_name() -> None:
    # given
    app = Application(AwsXRayMiddleware())

    @app.get("/test")
    def example_handler(req: HttpRequest) -> HttpResponse:
        assert req.attributes["__handler__"].__name__ == "example_handler"
        return HttpResponse("OK")

    # when
    with mock.patch("chocs_middleware.xray.middleware.check_in_lambda") as check_in_lambda:
        check_in_lambda.return_value = True

        # Start a parent segment. Normally this would be done for us in AWS however here we need to do it ourselves.
        with xray_recorder.in_segment("## lambda container"):
            response = app(HttpRequest(HttpMethod.GET, "/test"))

    # then
    assert response.status_code == HttpStatus.OK
