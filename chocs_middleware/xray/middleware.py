from typing import Type
from copy import deepcopy

from chocs import HttpMethod, HttpRequest, HttpResponse
from chocs.middleware import Middleware, MiddlewareHandler
from aws_xray_sdk.core.lambda_launcher import check_in_lambda
from aws_xray_sdk.core.models import http
from aws_xray_sdk.core.utils import stacktrace
from aws_xray_sdk.ext.util import (
    construct_xray_header,
    prepare_response_header,
)

from aws_xray_sdk.core import xray_recorder, AWSXRayRecorder
from aws_xray_sdk.core.async_recorder import AsyncAWSXRayRecorder

__all__ = ["AwsXRayMiddleware"]


class AwsXRayMiddleware(Middleware):
    def __init__(self, recorder: AWSXRayRecorder = None, capture_response: bool = True, capture_error: bool = True, name: str = None):
        self._recorder = recorder if recorder is not None else xray_recorder
        self._capture_response = capture_response
        self._capture_error = capture_error
        self._name = name

    def __deepcopy__(self, memo):
        # Handle issue with deepcopying middleware when generating the MiddlewarePipeline for the application.
        # Since `xray_recorder` is globally instanciated, we can handle it separately to other attributes when
        # handling the deepcopy. This fix will work for cases where no custom recorder is used, however if one
        # does want to use a custom recorder, they may need to handle their own deepcopy pickling.
        result = type(self)()
        memo[id(self)] = result

        for k, v in self.__dict__.items():
            if v == xray_recorder:
                setattr(result, k, xray_recorder)
                continue
            setattr(result, k, deepcopy(v, memo))

        return result

    def handle(self, request: HttpRequest, next: MiddlewareHandler) -> HttpResponse:
        # If we are not in lambda environment just ignore the middleware
        if not check_in_lambda():
            return next(request)

        # There is some malfunction, so lets ignore it.
        if "__handler__" not in request.attributes:
            return next(request)

        lambda_handler = request.attributes["__handler__"]

        # Get the name of the handler function to use as the segment name.
        segment_name = lambda_handler.__name__

        # Extract x-ray trace header from inbound request headers. Used by AWS internally to track
        # request/response cycle. When locally testing, the `aws_event` flag is not set on the request
        # attributes. In this case we fallback to the requests headers.
        xray_header = construct_xray_header(request.attributes.get("aws_event", {}).get("headers", request.headers))

        # Start subsegment for x-ray recording. We are in a lambda so we will always have a parent segment.
        segment = self._recorder.begin_subsegment(segment_name)

        # Save x-ray trace header information to the current subsegment.
        segment.save_origin_trace_header(xray_header)

        try:
            response = next(request)
        except Exception as error:
            # An error was raised during handling of the request. Extract the stacktrace and attach it to
            # the current subsegment.
            stack = stacktrace.get_stacktrace(limit=self._recorder._max_trace_back)
            segment.add_exception(error, stack)

            # End the current subsegment before raising the error. If not done, current subsegment information
            # won't be sent to AWS
            self._recorder.end_subsegment()
            raise error

        # Add the xray header from the inbound request to the response. Needed for AWS to keep track of the
        # request/response cycle internally in x-ray.
        response.headers[http.XRAY_HEADER] = prepare_response_header(xray_header, segment)

        # End the current subsegement before handing off. If not done, AWS won't record this subsegment.
        self._recorder.end_subsegment()

        return response
