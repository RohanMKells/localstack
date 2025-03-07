import functools
import sys
from typing import Any, NamedTuple, Optional, Type, Union

from localstack.aws.connect import InternalRequestParameters

if sys.version_info >= (3, 8):
    from typing import Protocol, TypedDict
else:
    from typing_extensions import Protocol, TypedDict

from botocore.model import OperationModel, ServiceModel

from localstack.http import Request, Response

# FIXME: deprecated, use localstack.http.Request and localstack.http.Response instead
HttpRequest = Request
HttpResponse = Response


class ServiceRequest(TypedDict):
    pass


ServiceResponse = Any


class ServiceException(Exception):
    """
    An exception that indicates that a service error occurred.
    These exceptions, when raised during the execution of a service function, will be serialized and sent to the client.
    Do not use this exception directly (use the generated subclasses or CommonsServiceException instead).
    """

    code: str
    status_code: int
    sender_fault: bool
    message: str

    def __init__(self, *args, **kwargs):
        super(ServiceException, self).__init__(*args)

        if len(args) >= 1:
            self.message = args[0]
        else:
            self.message = ""
        for key, value in kwargs.items():
            setattr(self, key, value)


class CommonServiceException(ServiceException):
    """
    An exception which can be raised within a service during its execution, even if it is not specified (i.e. it's not
    generated based on the service specification).
    In the AWS API references, this kind of errors are usually referred to as "Common Errors", f.e.:
    https://docs.aws.amazon.com/AWSSimpleQueueService/latest/APIReference/CommonErrors.html
    """

    def __init__(self, code: str, message: str, status_code: int = 400, sender_fault: bool = False):
        super(CommonServiceException, self).__init__(message)
        self.code = code
        self.status_code = status_code
        self.sender_fault = sender_fault


Operation = Type[ServiceRequest]


class ServiceOperation(NamedTuple):
    service: str
    operation: str


class RequestContext:
    """
    A RequestContext object holds the information of an HTTP request that is processed by the LocalStack Gateway. The
    context holds information about the request, such as which AWS service the request is made to, which operation is
    being invoked, and other metadata such as the account or the region. The context is continuously populated as the
    request moves through the handler chain. Once the HTTP request has been parsed, the context also holds the parsed
    request parameters of the AWS API call. The handler chain may also add the AWS response from the backend to the
    context, so it can be used for logging or modification before going to the serializer.
    """

    request: Optional[Request]
    """The underlying incoming HTTP request."""
    service: Optional[ServiceModel]
    """The botocore ServiceModel of the service the request is made to."""
    operation: Optional[OperationModel]
    """The botocore OperationModel of the AWS operation being invoked."""
    region: Optional[str]
    """The region the request is made to."""
    account_id: Optional[str]
    """The account the request is made from."""
    service_request: Optional[ServiceRequest]
    """The AWS operation parameters."""
    service_response: Optional[ServiceResponse]
    """The response from the AWS emulator backend."""
    service_exception: Optional[ServiceException]
    """The exception the AWS emulator backend may have raised."""
    internal_request_params: Optional[InternalRequestParameters]
    """Data sent by client-side LocalStack during internal calls."""

    def __init__(self) -> None:
        self.service = None
        self.operation = None
        self.region = None
        self.account_id = None
        self.request = None
        self.service_request = None
        self.service_response = None
        self.service_exception = None
        self.internal_request_params = None

    @property
    def is_internal_call(self) -> bool:
        """
        Whether this request is an internal cross-service call.
        """
        return self.internal_request_params is not None

    @property
    def service_operation(self) -> Optional[ServiceOperation]:
        """
        If both the service model and the operation model are set, this returns a tuple of the service name and
        operation name.

        :return: a tuple like ("s3", "PutObject") or ("lambda", "CreateFunction")
        """
        if not self.service or not self.operation:
            return None
        return ServiceOperation(self.service.service_name, self.operation.name)

    def __repr__(self):
        return f"<RequestContext {self.service=}, {self.operation=}, {self.region=}, {self.account_id=}, {self.request=}>"


class ServiceRequestHandler(Protocol):
    """
    A protocol to describe a Request--Response handler that processes an AWS API call with the already parsed request.
    """

    def __call__(
        self, context: RequestContext, request: ServiceRequest
    ) -> Optional[Union[ServiceResponse, Response]]:
        """
        Handle the given request.

        :param context: the request context
        :param request: the request parameters, e.g., ``{"Bucket": "my-bucket-name"}`` for an s3 create bucket operation
        :return: either an already serialized HTTP Response object, or a service response dictionary.
        """
        raise NotImplementedError


def handler(operation: str = None, context: bool = True, expand: bool = True):
    """
    Decorator that indicates that the given function is a handler
    """

    def wrapper(fn):
        @functools.wraps(fn)
        def operation_marker(*args, **kwargs):
            return fn(*args, **kwargs)

        operation_marker.operation = operation
        operation_marker.expand_parameters = expand
        operation_marker.pass_context = context

        return operation_marker

    return wrapper
