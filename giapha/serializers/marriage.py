"""Marriage serializer.

No read/write split needed here (unlike Person) -- Marriage has no revision
history and no public-facing variant planned yet.
"""

from rest_framework import serializers

from giapha.models import MARRIAGE_STATUS, Marriage


class MarriageSerializer(serializers.ModelSerializer):
    husband_id = serializers.IntegerField()
    wife_id = serializers.IntegerField()
    husband_name = serializers.CharField(source='husband.ho_ten', read_only=True)
    wife_name = serializers.CharField(source='wife.ho_ten', read_only=True)
    # Optional on input: the view defaults it to max(existing order for the
    # husband) + 1 when omitted. 1 means "vợ cả".
    order = serializers.IntegerField(required=False, min_value=1)
    status = serializers.ChoiceField(choices=MARRIAGE_STATUS)

    class Meta:
        model = Marriage
        fields = (
            'id', 'husband_id', 'husband_name', 'wife_id', 'wife_name',
            'order', 'status', 'note',
        )
        read_only_fields = ('id', 'husband_name', 'wife_name')
