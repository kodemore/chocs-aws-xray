from aws_xray_sdk.core import AWSXRayRecorder, xray_recorder
from aws_xray_sdk.core.lambda_launcher import check_in_lambda
from aws_xray_sdk.core.models import http
from aws_xray_sdk.core.models.segment import Segment
from aws_xray_sdk.core.utils import stacktrace
from aws_xray_sdk.ext.util import construct_xray_header, prepare_response_header
from chocs import HttpRequest, HttpResponse, HttpStatus
from chocs.errors import HttpError
from chocs.middleware import Middleware, MiddlewareHandler
from typing import Callable

__all__ = ["AwsXRayMiddleware"]


ErrorHandler = Callable[[HttpRequest, Exception, Segment], HttpResponse]
SegmentHandler = Callable[[HttpRequest, Segment], None]


def default_error_handler(
    request: HttpRequest, error: Exception, segment: Segment
) -> HttpResponse:

    stack = stacktrace.get_stacktrace(limit=10)
    segment.add_exception(error, stack)

    if isinstance(error, HttpError):
        response = HttpResponse(error.http_message, error.status_code)
    else:
        response = HttpResponse("Server Error", HttpStatus.INTERNAL_SERVER_ERROR)

    return response


class AwsXRayMiddleware(Middleware):
    def __init__(
        self,
        recorder: AWSXRayRecorder = None,
        error_handler: ErrorHandler = default_error_handler,
        segment_handler: SegmentHandler = None,
    ):
        """

        :param recorder:
        :param error_handler: A callable that will be used if any error occurs during application execution
        :param segment_handler: A callable that will be used to provide extra information for x-ray segment
        """

        self._recorder = recorder if recorder is not None else xray_recorder
        self._error_handler = error_handler
        self._segment_handler = segment_handler

    def __deepcopy__(self, memo):
        # Handle issue with deepcopying middleware when generating the MiddlewarePipeline for the application.
        # Since `xray_recorder` is globally instanciated, we can handle it separately to other attributes when
        # handling the deepcopy. This fix will work for cases where no custom recorder is used, however if one
        # does want to use a custom recorder, they may need to handle their own deepcopy pickling.

        return AwsXRayMiddleware(
            self._recorder, self._error_handler, self._segment_handler
        )

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
        xray_header = construct_xray_header(
            request.attributes.get("aws_event", {}).get("headers", request.headers)
        )

        # Start subsegment for x-ray recording. We are in a lambda so we will always have a parent segment.
        segment = self._recorder.begin_subsegment(segment_name)

        request.attributes["aws_xray_recorder"] = self._recorder

        # Save x-ray trace header information to the current subsegment.
        segment.save_origin_trace_header(xray_header)

        # Add request metadata to x-ray segment.
        segment.put_http_meta(http.METHOD, str(request.method))
        segment.put_http_meta(
            http.URL,
            str(request.path)
            + ("?" + str(request.query_string) if request.query_string else ""),
        )

        # Allow to append extra metadata to x-ray segment.
        if self._segment_handler:
            self._segment_handler(request, segment)

        try:
            response = next(request)
        except Exception as error:
            response = self._error_handler(request, error, segment)

        # Add the xray header from the inbound request to the response. Needed for AWS to keep track of the
        # request/response cycle internally in x-ray.
        response.headers[http.XRAY_HEADER] = prepare_response_header(
            xray_header, segment
        )
        segment.put_http_meta(http.STATUS, int(response.status_code))

        self._recorder.end_subsegment()

        return response
