"""Clan create/list/detail/update/soft-delete, plus the phase-9 public-link
toggle (`ClanPublicLinkAPIView`, at the bottom of this file).
"""

from django.db import IntegrityError, transaction
from django.urls import reverse
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from giapha.exceptions import BadRequestException
from giapha.models import ClanMember
from giapha.permissions import IsClanMember, IsClanOwner
from giapha.selectors.clan import clans_for_user, get_clan_or_none, roles_for_clans
from giapha.serializers.clan import ClanSerializer
from giapha.services.public_slug import generate_public_slug

NOT_FOUND_DETAIL = 'Không tìm thấy dòng họ.'
SLUG_RETRY_EXHAUSTED_DETAIL = 'Không thể tạo link công khai, vui lòng thử lại.'
# `public_slug` is 22 random chars (`generate_public_slug`) against a
# unique column -- a collision is astronomically unlikely. This cap exists
# only so a freak collision degrades to a clear 400, never a 500, matching
# the retry-loop shape already used for invite codes
# (`views.clan_membership.ClanInviteListCreateAPIView`).
MAX_SLUG_ATTEMPTS = 5


class ClanListCreateAPIView(APIView):
    """`GET` lists clans the caller belongs to. `POST` creates a new one."""

    permission_classes = [IsAuthenticated]

    def get(self, request):
        clans = list(clans_for_user(request.user))
        roles = roles_for_clans(request.user, [clan.id for clan in clans])
        context = {'request': request, 'roles': roles}
        return Response({'data': ClanSerializer(clans, many=True, context=context).data})

    def post(self, request):
        serializer = ClanSerializer(data=request.data, context={'request': request})
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            clan = serializer.save()
            ClanMember.objects.create(clan=clan, user=request.user, role='owner')

        # The creator is the owner; seed the cache so the response can
        # include public_slug without an extra role lookup.
        request._giapha_role_cache = {clan.id: 'owner'}
        out = ClanSerializer(clan, context={'request': request})
        return Response({'data': out.data}, status=status.HTTP_201_CREATED)


class ClanDetailAPIView(APIView):
    """`GET` for any member, `PATCH`/`DELETE` (soft) for the owner only."""

    def get_permissions(self):
        classes = [IsClanMember] if self.request.method in SAFE_METHODS else [IsClanOwner]
        return [IsAuthenticated()] + [cls() for cls in classes]

    def get(self, request, clan_id):
        clan = get_clan_or_none(clan_id)
        if clan is None:
            raise NotFound(NOT_FOUND_DETAIL)
        return Response({'data': ClanSerializer(clan, context={'request': request}).data})

    def patch(self, request, clan_id):
        clan = get_clan_or_none(clan_id)
        if clan is None:
            raise NotFound(NOT_FOUND_DETAIL)

        serializer = ClanSerializer(
            clan, data=request.data, partial=True, context={'request': request},
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        serializer.save()
        return Response({'data': serializer.data})

    def delete(self, request, clan_id):
        clan = get_clan_or_none(clan_id)
        if clan is None:
            raise NotFound(NOT_FOUND_DETAIL)
        clan.is_deleted = True
        clan.save(update_fields=['is_deleted'])
        return Response(status=status.HTTP_204_NO_CONTENT)


class ClanPublicLinkAPIView(APIView):
    """`POST` turns on the public gia phả page: mints a fresh
    `public_slug` and sets `visibility='public_link'` together, in one
    `transaction.atomic()` -- a request that fails partway must never leave
    a slug set with the clan still `private` (unreachable but leaked in a
    DB dump) or `public_link` with no slug (reachable by nobody, but a
    confusing half-state). `DELETE` revokes: it does not merely clear the
    slug, it also resets `visibility` to `'private'`, so even a client that
    still has the old `public_slug` cached (or a proxy that cached the old
    response) gets a 404 the moment it's used again -- both fields lie on
    the same "is this link live" question.

    Re-enabling after a revoke always mints a DIFFERENT slug (fresh call to
    `generate_public_slug()`) -- there is no "restore the old link" path.

    NOT LOCKED against a concurrent `POST` from two tabs/requests for the
    SAME clan: both can pass the not-deleted check, both write a `slug`,
    and whichever commits last wins the `public_slug` column -- the losing
    caller's response hands out a slug that immediately 404s on the public
    endpoints. Fails closed (nobody gets a slug that actually works when it
    shouldn't), just not gracefully; a real lock is not worth it for an
    owner-only settings toggle at MVP.

    Owner only, matching every other clan-settings mutation.
    """

    permission_classes = [IsAuthenticated, IsClanOwner]

    def post(self, request, clan_id):
        clan = get_clan_or_none(clan_id)
        if clan is None:
            raise NotFound(NOT_FOUND_DETAIL)

        for _attempt in range(MAX_SLUG_ATTEMPTS):
            slug = generate_public_slug()
            try:
                with transaction.atomic():
                    clan.public_slug = slug
                    clan.visibility = 'public_link'
                    clan.save(update_fields=['public_slug', 'visibility'])
                break
            except IntegrityError:
                # Savepoint-safe: each attempt has its own `atomic()` block,
                # so a failed INSERT/UPDATE here does not poison a wider
                # transaction (`docs/code-standards.md` -> Errors).
                continue
        else:
            raise BadRequestException(SLUG_RETRY_EXHAUSTED_DETAIL)

        url = request.build_absolute_uri(
            reverse('public-clan-tree', kwargs={'slug': clan.public_slug}),
        )
        return Response({'data': {'slug': clan.public_slug, 'url': url}})

    def delete(self, request, clan_id):
        clan = get_clan_or_none(clan_id)
        if clan is None:
            raise NotFound(NOT_FOUND_DETAIL)

        clan.public_slug = None
        clan.visibility = 'private'
        clan.save(update_fields=['public_slug', 'visibility'])
        return Response(status=status.HTTP_204_NO_CONTENT)
