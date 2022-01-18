from aws_xray_sdk.core import xray_recorder
from aws_xray_sdk.core.models.segment import Segment
from chocs import Application, HttpMethod, HttpRequest, HttpResponse, HttpStatus
from unittest import mock

from chocs_middleware.xray import AwsXRayMiddleware
from tests.fixtures import XRayRecorderMock


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
    with mock.patch(
        "chocs_middleware.xray.middleware.check_in_lambda"
    ) as check_in_lambda:
        check_in_lambda.return_value = True

        # Start a parent segment. Normally this would be done for us in AWS however here we need to do it ourselves.
        with xray_recorder.in_segment("## lambda container"):
            response = app(HttpRequest(HttpMethod.GET, "/test"))

    # then
    assert response.status_code == HttpStatus.OK


def test_can_catch_an_error() -> None:
    # given
    def error_handler(
        request: HttpRequest, error: Exception, segment_: Segment
    ) -> HttpResponse:
        segment_.put_metadata("test", "ok")
        return HttpResponse("NOT OK", HttpStatus.GATEWAY_TIMEOUT)

    recorder = XRayRecorderMock()
    app = Application(AwsXRayMiddleware(error_handler=error_handler, recorder=recorder))

    @app.get("/test")
    def example_handler(req: HttpRequest) -> HttpResponse:
        raise Exception("NOT TODAY")

    # when
    with mock.patch(
        "chocs_middleware.xray.middleware.check_in_lambda"
    ) as check_in_lambda:
        check_in_lambda.return_value = True

        # Start a parent segment. Normally this would be done for us in AWS however here we need to do it ourselves.
        with recorder.in_segment("## lambda container"):
            response = app(HttpRequest(HttpMethod.GET, "/test"))

    # then
    assert response.status_code == HttpStatus.GATEWAY_TIMEOUT
    segments = recorder.stored_subsegments
    assert len(segments) == 1
    assert segments[0].metadata == {"default": {"test": "ok"}}
    assert segments[0].http["request"]["url"] == "/test"
    assert segments[0].http["response"]["status"] == int(HttpStatus.GATEWAY_TIMEOUT)


def test_can_access_xray_recorder() -> None:
    recorder = XRayRecorderMock()
    app = Application(AwsXRayMiddleware(recorder=recorder))

    @app.get("/test")
    def example_handler(req: HttpRequest) -> HttpResponse:
        assert req.attributes["aws_xray_recorder"] is recorder
        return HttpResponse("OK")

    # when
    with mock.patch(
        "chocs_middleware.xray.middleware.check_in_lambda"
    ) as check_in_lambda:
        check_in_lambda.return_value = True

        with recorder.in_segment("## lambda container"):
            response = app(HttpRequest(HttpMethod.GET, "/test"))

    # then
    assert response.status_code == HttpStatus.OK
