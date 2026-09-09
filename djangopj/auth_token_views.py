"""The `/auth/token` and `/auth/revoke-token` endpoints. Username/password only.

WHY THIS EXISTS -- do not "simplify" it into `oauth2_provider.views.TokenView`.

Shipped mobile clients call both URLs, and some of them send a JSON body.
django-oauth-toolkit's own views are plain Django `View`s that read `request.POST`,
i.e. form-encoded bodies ONLY -- swap this module out for them and every JSON
client starts getting `unsupported_grant_type`. This module accepts BOTH body
formats (see `_copy_parsed_body_into_post`) and `djangopj/urls.py` keeps the
trailing slash optional. Both are wire contracts with already-released clients,
not preferences.

Properties worth keeping if this is ever rewritten again:
  * a non-mapping JSON body answers 400, never a 500;
  * oauthlib's response headers (notably `WWW-Authenticate`, required by
    RFC 6749 section 5.2 on a 401) are copied onto the response;
  * `sensitive_post_parameters` / `sensitive_variables` keep the password out of
    error reports;
  * revoke answers 204 with an empty body.

The URLs, status codes and body shapes are frozen: they match what the endpoints
returned before this module replaced the third-party package that used to serve
them, so no released client can tell the difference.
"""
from json import loads as json_loads

from django.utils.decorators import method_decorator
from django.views.decorators.debug import sensitive_post_parameters, sensitive_variables
from oauth2_provider.models import AccessToken
from oauth2_provider.views.mixins import OAuthLibMixin
from rest_framework.exceptions import ParseError
from rest_framework.fields import CharField
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.serializers import Serializer
from rest_framework.status import HTTP_204_NO_CONTENT, HTTP_400_BAD_REQUEST
from rest_framework.views import APIView


@sensitive_variables('data')
def _copy_parsed_body_into_post(request, data):
    """Expose DRF's parsed body as `request.POST` so oauthlib can read it.

    DRF consumes the request stream while parsing, so by the time
    django-oauth-toolkit looks at the underlying `HttpRequest.POST` a JSON body
    has left it empty -- and every JSON client would get `unsupported_grant_type`.
    The original `POST` QueryDict is immutable, hence the `.copy()` before writing.

    Note the copy leaves the credentials (password included) sitting in
    `request.POST`; `sensitive_post_parameters` on `dispatch` is what keeps them
    out of Django's error reports. Any request-logging middleware added later
    must redact them itself.
    """
    if not hasattr(data, 'items'):
        # A JSON body that is a list/string/number/null. Upstream let this raise
        # `AttributeError` -> 500 on an unauthenticated endpoint; 400 is the
        # honest answer and cannot be told apart from success by any real client.
        raise ParseError('Request body must be an object.')
    request._request.POST = request._request.POST.copy()
    for key, value in data.items():
        request._request.POST[key] = value


def _with_oauthlib_headers(response, headers):
    """Carry oauthlib's headers over, e.g. the `WWW-Authenticate` that RFC 6749
    section 5.2 requires on a 401. Never let them clobber DRF's own
    `Content-Type`, which is set by the renderer after this returns."""
    for key, value in (headers or {}).items():
        if key.lower() != 'content-type':
            response[key] = value
    return response


# `sensitive_post_parameters` asserts it received a real `HttpRequest`, and DRF's
# `Request` is not one -- so it MUST decorate `dispatch` (which the URL resolver
# calls with the raw request), never `post` (which receives DRF's wrapper).
# No `csrf_exempt` here: DRF's `APIView.as_view()` already wraps the view in it.
@method_decorator(sensitive_post_parameters('password'), name='dispatch')
class TokenView(OAuthLibMixin, APIView):
    """`POST /auth/token` -- OAuth2 `password` and `refresh_token` grants."""

    permission_classes = (AllowAny,)
    # Client credentials travel in the body, never in a Bearer header. Running the
    # default authenticators here would let a stale token 401 a valid refresh.
    authentication_classes = ()
    # `renderer_classes` is deliberately NOT narrowed to `JSONRenderer`. Doing so
    # makes DRF answer `Accept: text/html` with 406 instead of the 200 this
    # endpoint has always returned -- a silent, unrecoverable login failure for
    # any client that sends that header.

    @sensitive_variables('request')
    def post(self, request, *args, **kwargs):
        _copy_parsed_body_into_post(request, request.data)
        try:
            url, headers, body, status = self.create_token_response(request._request)
        except AccessToken.DoesNotExist:
            return Response(
                data={'invalid_grant': 'The access token of your Refresh Token does not exist.'},
                status=HTTP_400_BAD_REQUEST,
            )
        return _with_oauthlib_headers(Response(data=json_loads(body), status=status), headers)


class _RevokeTokenSerializer(Serializer):
    """`client_id` and `token` are required, in this exact shape: the 400 body a
    missing field produces is already being parsed by released clients.

    `client_secret` is OPTIONAL because the production application is a `public`
    client (RFC 8252: a native app cannot keep a secret -- it ships inside the
    binary). Required here, it made logout unreachable: a public client has no
    secret to send, and the serializer rejected the request before oauthlib ever
    saw it. Omitted or blank, `client_authentication_required` falls through to
    `authenticate_client_id`, which accepts a non-confidential client.

    Loosening is safe for released clients: one that still sends the field is
    validated exactly as before. A CONFIDENTIAL application that omits it now
    answers 401 `invalid_client` (oauthlib's own error) instead of a 400 field
    error -- the honest status for a client that failed to authenticate.
    """

    client_id = CharField(max_length=100)
    client_secret = CharField(max_length=255, required=False, allow_blank=True)
    token = CharField(max_length=500)


class RevokeTokenView(OAuthLibMixin, APIView):
    """`POST /auth/revoke-token` -- logout."""

    permission_classes = (AllowAny,)
    authentication_classes = ()

    def post(self, request, *args, **kwargs):
        serializer = _RevokeTokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        _copy_parsed_body_into_post(request, serializer.validated_data)
        url, headers, body, status = self.create_revocation_response(request._request)
        # oauthlib answers a successful revocation with an empty body. Upstream
        # turned that into `Response(data='', status=204)`, which renders as the
        # two bytes `""` with a JSON Content-Type -- keep exactly that, a client
        # may be calling `JSON.parse` on it.
        response = Response(
            data=json_loads(body) if body else '',
            status=status if body else HTTP_204_NO_CONTENT,
        )
        return _with_oauthlib_headers(response, headers)
