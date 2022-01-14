from typing import Callable, Dict, List, Any

from chocs import HttpMethod, HttpRequest, HttpResponse
from chocs.middleware import Middleware, MiddlewareHandler
from aws_xray_sdk.core.lambda_launcher import LambdaContext, check_in_lambda
from aws_xray_sdk.ext.util import (
    calculate_sampling_decision,
    calculate_segment_name,
    construct_xray_header,
    prepare_response_header,
)

from aws_lambda_powertools.tracing import Tracer
from aws_xray_sdk.core import xray_recorder, AsyncAWSXRayRecorder, AWSXRayRecorder

__all__ = ["AwsXRayMiddleware"]


class AwsXRayMiddleware(Middleware):
    def __init__(self, recorder: AWSXRayRecorder = None, capture_response: bool = True, capture_error: bool = True, name: str = None):
        self._recorder = recorder if recorder is not None else AsyncAWSXRayRecorder()
        self._capture_response = capture_response
        self._capture_error = capture_error
        self._name = name

    def handle(self, request: HttpRequest, next: MiddlewareHandler) -> HttpResponse:
        # If we are not in lambda environment just ignore the middleware
        if not check_in_lambda():
            return next(request)

        # There is some malfunction, so lets ignore it.
        if "__handler__" not in request.attributes:
            return next(request)

        lambda_handler = request.attributes["__handler__"]

        segment_name = self._name or lambda_handler.__name__
        xray_header = construct_xray_header(request.attributes["aws_event"].get("headers"))

        self._recorder.begin_subsegment(segment_name)

        return next(request)
