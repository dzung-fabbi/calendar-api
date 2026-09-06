"""`POST /clans/{clan_id}/photo-urls` -- batched presigned GET (phase 8).

Split out of `views/photo.py` purely to keep that file under the 200-line
limit (`docs/code-standards.md` -> Files); the two together are still "the
photo endpoints" for the 503-on-unconfigured-storage rule.

This is the ONLY place besides `GET /persons/{pid}` that ever mints a
presigned GET URL -- `/tree` deliberately never does (phase-08 spec). Not
because presigning is a network call (it's a local HMAC, ~0.3ms, see
`services.tree.node_from_row`'s comment for the real reasons: per-node CPU/
payload cost plus the 1-hour TTL burning down before the client even looks
at most nodes). A client that wants photos for a page of tree nodes calls
here with the ids it actually needs, capped at
`serializers.photo.PHOTO_URLS_MAX_IDS`.
"""

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from giapha.permissions import IsClanMember
from giapha.selectors.person import photo_keys_for
from giapha.serializers.photo import PhotoUrlsRequestSerializer
from giapha.services import storage
from giapha.views.photo import require_storage


class ClanPhotoUrlsAPIView(APIView):
    """`POST` only, any clan member (read-only intent, no write happens)."""

    permission_classes = [IsAuthenticated, IsClanMember]

    def post(self, request, clan_id):
        require_storage()
        serializer = PhotoUrlsRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        # `photo_keys_for` already drops ids from another clan or that don't
        # exist, so the response simply never mentions them -- not an error,
        # not another clan's photo.
        photo_keys = photo_keys_for(clan_id, serializer.validated_data['person_ids'])
        data = {
            person_id: storage.presign_get(photo_key) if photo_key else None
            for person_id, photo_key in photo_keys.items()
        }
        return Response({'data': data})
