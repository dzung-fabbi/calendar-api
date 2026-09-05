"""Factory for the star through-table inlines.

There used to be 25 near-identical `TabularInline` subclasses here. They differ
only in their model and label, so they are built from one factory -- which also
removes the drift that had crept in: one hour inline autocompleted the wrong
field, and another was missing autocomplete entirely.
"""

from django.contrib import admin

STAR_FIELD = 'sao'


def through_inline(model, verbose_name=None, autocomplete=(STAR_FIELD,)):
    """Build a TabularInline for a `sao` through-table."""
    attrs = {
        'model': model,
        'extra': 0,
        'autocomplete_fields': tuple(autocomplete),
    }
    if verbose_name is not None:
        attrs['verbose_name'] = verbose_name
        attrs['verbose_name_plural'] = verbose_name
    return type('{}Inline'.format(model.__name__), (admin.TabularInline,), attrs)


def through_inlines(models, label):
    """Build one inline per model, labelled '<label> N' (1-based)."""
    return [
        through_inline(model, verbose_name='{} {}'.format(label, index))
        for index, model in enumerate(models, start=1)
    ]
