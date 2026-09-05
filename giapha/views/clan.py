"""Clan create/list/detail/update/soft-delete."""

from django.db import transaction
from rest_framework import status
from rest_framework.exceptions import NotFound
from rest_framework.permissions import SAFE_METHODS, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from giapha.models import ClanMember
from giapha.permissions import IsClanMember, IsClanOwner
from giapha.selectors.clan import clans_for_user, get_clan_or_none, roles_for_clans
from giapha.serializers.clan import ClanSerializer

NOT_FOUND_DETAIL = 'Không tìm thấy dòng họ.'


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
