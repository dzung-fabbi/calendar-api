"""No-auth public gia phả endpoints (phase 9):
`GET /public/{slug}/tree` and `GET /public/{slug}/persons/{pid}`.

Both views share `PublicNoAuthAPIView`'s rules:

1. UNKNOWN SLUG, REVOKED SLUG, PRIVATE CLAN, SOFT-DELETED CLAN ALL 404,
   NEVER 403. Same house rule as `permissions.py` -- a 403 would confirm a
   clan exists at that slug even when it shouldn't be reachable.
2. THROTTLED under the dedicated `giapha-public` scope
   (`djangopj.settings.REST_FRAMEWORK['DEFAULT_THROTTLE_RATES']`).
   `AllowAny` means there is no per-user bucket at all otherwise. THIS IS A
   PER-IP RATE LIMIT, NOT A HARD STOP: it is only as sound as
   `djangopj.settings.REST_FRAMEWORK['NUM_PROXIES']` matches the real
   deployment topology (see that setting's comment) -- with the wrong
   count, or from enough distinct source IPs, a caller can still scrape
   past it. It raises the cost of scraping/brute-forcing from one source,
   it does not remove the possibility outright.
3. `X-Robots-Tag: noindex, nofollow` AND `Cache-Control: no-store` on
   EVERY response, including 404s/405s/exceptions -- see
   `finalize_response` below.
4. `GET`/`HEAD` only (no `OPTIONS`, no `POST`, ...) and JSON-only rendering
   -- see the class attributes below.
"""

from django.conf import settings
from rest_framework.exceptions import NotFound
from rest_framework.permissions import AllowAny
from rest_framework.renderers import JSONRenderer
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView

from giapha.selectors.clan import get_clan_by_public_slug
from giapha.selectors.public import public_person_row, public_tree_payload
from giapha.serializers.public import PublicPersonSerializer, PublicTreeSerializer
from giapha.services.public_person import public_person_payload

CLAN_NOT_FOUND_DETAIL = 'Không tìm thấy gia phả công khai.'
PERSON_NOT_FOUND_DETAIL = 'Không tìm thấy thành viên.'
NOINDEX_HEADER_VALUE = 'noindex, nofollow'
CACHE_CONTROL_HEADER_VALUE = 'no-store'


def _clan_or_404(slug):
    clan = get_clan_by_public_slug(slug)
    if clan is None:
        raise NotFound(CLAN_NOT_FOUND_DETAIL)
    return clan


class PublicNoAuthAPIView(APIView):
    """Shared base for every no-auth public gia phả endpoint.

    `http_method_names`/`renderer_classes` close two holes the plain
    `APIView` defaults leave open on a no-auth PII surface:

    - Without pinning `http_method_names`, DRF answers `OPTIONS`
      automatically WITHOUT ever calling `get()` -- so `_clan_or_404` never
      runs, and an invalid slug returns 200 with a body describing the
      view's allowed methods/parsers instead of 404ing like every other
      method does. Restricting to `get`/`head` makes `OPTIONS` (and
      anything else) a plain 405 through the same dispatch path as a real
      mismatched method, before any slug lookup happens.
    - Without pinning `renderer_classes`, DRF's default content
      negotiation includes `BrowsableAPIRenderer`, so `Accept: text/html`
      (a browser's default) renders the ENTIRE public payload as an
      interactive HTML page -- several KB of markup for what should be a
      lean JSON API, and a needless attack surface (HTML rendering of
      user-controlled `ho_ten`/`tieu_su` text) for a page that has no
      business being browsed as HTML at all.
    """

    http_method_names = ['get', 'head']
    renderer_classes = [JSONRenderer]
    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'giapha-public'

    def finalize_response(self, request, response, *args, **kwargs):
        """Runs for EVERY response DRF produces for this view -- the 200
        happy path, a 404 from `_clan_or_404`/`NotFound`, a 405 from the
        `http_method_names` restriction above, even a 500 rendered by DRF's
        exception handler. Overriding here (rather than setting headers at
        the end of `get()`) is what makes both headers unconditional
        instead of "only on the happy path".

        `Cache-Control: no-store` matters as much as the noindex header:
        with NEITHER `Cache-Control` nor `Expires` set, a 200 GET is
        heuristically cacheable by any shared cache in front of this
        service (a CDN, a corporate proxy) purely from response headers a
        cache is allowed to assume absent explicit denial -- which would
        let such a cache keep serving a PII payload, keyed by the secret
        URL, even after the owner calls `DELETE /public-link` and the slug
        stops resolving at the origin. `no-store` (not just `no-cache`)
        says the response must not be persisted anywhere, which is what
        "the old link is dead immediately" actually requires.
        """
        response = super().finalize_response(request, response, *args, **kwargs)
        response['X-Robots-Tag'] = NOINDEX_HEADER_VALUE
        response['Cache-Control'] = CACHE_CONTROL_HEADER_VALUE
        return response


class ClanPublicTreeAPIView(PublicNoAuthAPIView):
    """`GET`, no auth. See module + `PublicNoAuthAPIView` docstrings for
    the 404/throttle/header/method rules shared with
    `ClanPublicPersonDetailAPIView`.
    """

    def get(self, request, slug):
        clan = _clan_or_404(slug)
        payload = public_tree_payload(
            clan.id, clan.ten_ho,
            max_persons=settings.MAX_CLAN_PERSONS,
            hide_living_details=clan.hide_living_details,
        )
        # No `{'data': ...}` envelope -- matches `views.tree.
        # ClanTreeAPIView.get`, the internal counterpart this mirrors.
        return Response(PublicTreeSerializer(payload).data)


class ClanPublicPersonDetailAPIView(PublicNoAuthAPIView):
    """`GET`, no auth. See module + `PublicNoAuthAPIView` docstrings for
    the 404/throttle/header/method rules shared with
    `ClanPublicTreeAPIView`.
    """

    def get(self, request, slug, person_id):
        clan = _clan_or_404(slug)
        row, is_living = public_person_row(clan.id, person_id)
        if row is None:
            raise NotFound(PERSON_NOT_FOUND_DETAIL)

        payload = public_person_payload(
            row, is_living=is_living, hide_living_details=clan.hide_living_details,
        )
        return Response({'data': PublicPersonSerializer(payload).data})
