"""Shared fixtures for the `/v1/family` test modules."""

from django.contrib.auth.models import User
from django.urls import reverse
from rest_framework.test import APIClient

from giapha.models import Family, FamilyPerson, FamilySpouse
from giapha.services.family_graph import canonical_pair


def make_user(username):
    return User.objects.create_user(username=username, password='pw')


def client_for(user):
    client = APIClient()
    client.force_authenticate(user=user)
    return client


def family_of(user):
    family, _ = Family.objects.get_or_create(user=user)
    return family


def make_person(family, name='Người', gender='unknown', **overrides):
    return FamilyPerson.objects.create(family=family, name=name, gender=gender, **overrides)


def make_spouse(family, a, b, spouse_type='married'):
    low, high = canonical_pair(a.id, b.id)
    return FamilySpouse.objects.create(family=family, person_a_id=low, person_b_id=high, type=spouse_type)


def url(name, **kwargs):
    return reverse(name, kwargs=kwargs)


def person_by_id(persons, person_id):
    wanted = str(person_id)
    return next(p for p in persons if p['id'] == wanted)


def relation(client, name, body):
    """POST one `relations/*` mutation and return the response."""
    return client.post(url(name), body, format='json')
