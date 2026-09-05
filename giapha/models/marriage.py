"""Marriage between two Person records."""

from django.db import models

from giapha.models.choices import MARRIAGE_STATUS
from giapha.models.person import Person


class Marriage(models.Model):
    husband = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name='marriages_as_husband', verbose_name='Chồng',
    )
    wife = models.ForeignKey(
        Person, on_delete=models.CASCADE, related_name='marriages_as_wife', verbose_name='Vợ',
    )
    # 1 = vợ cả, 2+ = vợ lẽ / tái hôn.
    order = models.IntegerField(default=1, verbose_name='Thứ tự')
    status = models.CharField(max_length=16, choices=MARRIAGE_STATUS, verbose_name='Trạng thái')
    note = models.CharField(max_length=255, blank=True, verbose_name='Ghi chú')

    class Meta:
        verbose_name = 'Hôn nhân'
        verbose_name_plural = 'Hôn nhân'
        unique_together = ('husband', 'wife')

    def __str__(self):
        return '{} - {}'.format(self.husband, self.wife)
