"""Response-hardening tests for the phase-9 public gia phả surface (M1/M2/
M3/L2 in the phase-9 security review): headers that must be present on
EVERY response (not just the 200 happy path), and that the surface answers
only `GET`/`HEAD` with JSON, never a browsable HTML page.

Split out of `test_public_security.py` once that file crossed the
200-line ceiling.
"""

from giapha.tests.factories import build_clan_fixture, build_person
from giapha.tests.public_helpers import PublicEndpointTestCase, anon_client, enable_public_link, public_tree_url


class ResponseHeaderTests(PublicEndpointTestCase):
    """`X-Robots-Tag`/`Cache-Control` must be set unconditionally --
    `views.public.PublicNoAuthAPIView.finalize_response` is what makes
    that true for a 404 too, not just a 200.
    """

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_public_headers')
        cls.clan = cls.fixture['clan']
        cls.slug = enable_public_link(cls.clan)
        cls.person = build_person(cls.clan, ho_ten='Ai đó')

    def test_tree_200_has_noindex_and_no_store_headers(self):
        response = anon_client().get(public_tree_url(self.slug))
        self.assertEqual(200, response.status_code)
        self.assertEqual('noindex, nofollow', response['X-Robots-Tag'])
        self.assertEqual('no-store', response['Cache-Control'])

    def test_unknown_slug_404_still_has_noindex_and_no_store_headers(self):
        """M2 fix: a 404 (DRF's exception response, not the `get()` happy
        path) used to skip both headers entirely -- a shared cache could
        heuristically cache the PII payload from an earlier 200 and keep
        serving it after revoke, and a 404 page for a real slug typo would
        be Google-indexable.
        """
        response = anon_client().get(public_tree_url('this-slug-was-never-issued'))
        self.assertEqual(404, response.status_code)
        self.assertEqual('noindex, nofollow', response['X-Robots-Tag'])
        self.assertEqual('no-store', response['Cache-Control'])


class MethodAndRendererRestrictionTests(PublicEndpointTestCase):
    """M3/L2 fixes: `OPTIONS` used to bypass `_clan_or_404` entirely (DRF
    answers it without calling `get()`), and with no `renderer_classes`
    restriction an `Accept: text/html` request rendered the whole payload
    as a multi-KB browsable-API HTML page.
    """

    @classmethod
    def setUpTestData(cls):
        cls.fixture = build_clan_fixture(suffix='_public_method_restriction')
        cls.clan = cls.fixture['clan']
        cls.slug = enable_public_link(cls.clan)
        cls.person = build_person(cls.clan, ho_ten='Ai đó')

    def test_options_on_tree_is_405(self):
        response = anon_client().options(public_tree_url(self.slug))
        self.assertEqual(405, response.status_code)

    def test_options_on_an_invalid_slug_is_still_405_not_a_200_leak(self):
        """Before the fix: `OPTIONS` on ANY slug (valid or not) returned
        200 with a body describing allowed methods/parsers, because
        `_clan_or_404` never ran. Restricting `http_method_names` makes
        `OPTIONS` 405 through the normal dispatch path, before any slug
        lookup.
        """
        response = anon_client().options(public_tree_url('this-slug-was-never-issued'))
        self.assertEqual(405, response.status_code)

    def test_accept_text_html_returns_json_not_the_browsable_api(self):
        """With `renderer_classes = [JSONRenderer]` and no HTML renderer
        registered at all, DRF's content negotiation correctly answers
        `text/html` with 406 Not Acceptable rather than silently falling
        back to a renderer that CAN produce HTML (`BrowsableAPIRenderer`)
        -- which is exactly the point: there is no code path left on this
        view that can ever emit an HTML page, happy path or error path.
        """
        response = anon_client().get(public_tree_url(self.slug), HTTP_ACCEPT='text/html')
        self.assertEqual(406, response.status_code)
        self.assertEqual('application/json', response['Content-Type'])
        # The browsable API would render `<html>`; DRF's own 406 body,
        # rendered by the only registered renderer (JSONRenderer), is JSON.
        self.assertTrue(response.content.decode().strip().startswith('{'))
        self.assertNotIn('<html', response.content.decode().lower())
