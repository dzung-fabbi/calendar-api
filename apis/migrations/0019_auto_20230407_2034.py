# Generated by Django 3.1 on 2023-04-07 13:34

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('apis', '0018_auto_20230407_1008'),
    ]

    operations = [
        migrations.DeleteModel(
            name='TuDaiCatThoiOld',
        ),
        migrations.AlterModelOptions(
            name='quynhan',
            options={'verbose_name': 'Quý nhân đăng thiên môn', 'verbose_name_plural': 'Quý nhân đăng thiên môn'},
        ),
        migrations.AlterModelOptions(
            name='saohiepky',
            options={'verbose_name': 'Sao tốt xấu', 'verbose_name_plural': 'Sao theo ngày'},
        ),
        migrations.AlterModelOptions(
            name='saohour1',
            options={'verbose_name': 'Giờ tý', 'verbose_name_plural': 'Giờ tý'},
        ),
        migrations.AlterModelOptions(
            name='saohour10',
            options={'verbose_name': 'Giờ dậu', 'verbose_name_plural': 'Giờ dậu'},
        ),
        migrations.AlterModelOptions(
            name='saohour11',
            options={'verbose_name': 'Giờ tuất', 'verbose_name_plural': 'Giờ tuất'},
        ),
        migrations.AlterModelOptions(
            name='saohour12',
            options={'verbose_name': 'Giờ hợi', 'verbose_name_plural': 'Giờ hợi'},
        ),
        migrations.AlterModelOptions(
            name='saohour2',
            options={'verbose_name': 'Giờ sửu', 'verbose_name_plural': 'Giờ sửu'},
        ),
        migrations.AlterModelOptions(
            name='saohour3',
            options={'verbose_name': 'Giờ dần', 'verbose_name_plural': 'Giờ dần'},
        ),
        migrations.AlterModelOptions(
            name='saohour4',
            options={'verbose_name': 'Giờ mão', 'verbose_name_plural': 'Giờ mão'},
        ),
        migrations.AlterModelOptions(
            name='saohour5',
            options={'verbose_name': 'Giờ thìn', 'verbose_name_plural': 'Giờ thìn'},
        ),
        migrations.AlterModelOptions(
            name='saohour6',
            options={'verbose_name': 'Giờ tỵ', 'verbose_name_plural': 'Giờ tỵ'},
        ),
        migrations.AlterModelOptions(
            name='saohour7',
            options={'verbose_name': 'Giờ ngọ', 'verbose_name_plural': 'Giờ ngọ'},
        ),
        migrations.AlterModelOptions(
            name='saohour8',
            options={'verbose_name': 'Giờ mùi', 'verbose_name_plural': 'Giờ mùi'},
        ),
        migrations.AlterModelOptions(
            name='saohour9',
            options={'verbose_name': 'Giờ thân', 'verbose_name_plural': 'Giờ thân'},
        ),
        migrations.AlterModelOptions(
            name='tudaicatthoi',
            options={'verbose_name': 'Tứ đại cát thời', 'verbose_name_plural': 'Tứ đại cát thời'},
        ),
        migrations.AlterModelOptions(
            name='tudaicatthoisao',
            options={'verbose_name': 'Sao', 'verbose_name_plural': 'Sao'},
        ),
        migrations.AddField(
            model_name='tudaicatthoi',
            name='sao',
            field=models.ManyToManyField(related_name='sao', through='apis.TuDaiCatThoiSao', to='apis.Sao'),
        ),
        migrations.AlterField(
            model_name='hourinday',
            name='lunar_day',
            field=models.CharField(choices=[('GIÁP TÝ', 'GIÁP TÝ'), ('ẤT SỬU', 'ẤT SỬU'), ('BÍNH DẦN', 'BÍNH DẦN'), ('ĐINH MÃO', 'ĐINH MÃO'), ('MẬU THÌN', 'MẬU THÌN'), ('KỶ TỴ', 'KỶ TỴ'), ('CANH NGỌ', 'CANH NGỌ'), ('TÂN MÙI', 'TÂN MÙI'), ('NHÂM THÂN', 'NHÂM THÂN'), ('QUÝ DẬU', 'QUÝ DẬU'), ('GIÁP TUẤT', 'GIÁP TUẤT'), ('ẤT HỢI', 'ẤT HỢI'), ('BÍNH TÝ', 'BÍNH TÝ'), ('ĐINH SỬU', 'ĐINH SỬU'), ('MẬU DẦN', 'MẬU DẦN'), ('KỶ MÃO', 'KỶ MÃO'), ('CANH THÌN', 'CANH THÌN'), ('TÂN TỴ', 'TÂN TỴ'), ('NHÂM NGỌ', 'NHÂM NGỌ'), ('QUÝ MÙI', 'QUÝ MÙI'), ('GIÁP THÂN', 'GIÁP THÂN'), ('ẤT DẬU', 'ẤT DẬU'), ('BÍNH TUẤT', 'BÍNH TUẤT'), ('ĐINH HỢI', 'ĐINH HỢI'), ('MẬU TÝ', 'MẬU TÝ'), ('KỶ SỬU', 'KỶ SỬU'), ('CANH DẦN', 'CANH DẦN'), ('TÂN MÃO', 'TÂN MÃO'), ('NHÂM THÌN', 'NHÂM THÌN'), ('QUÝ TỴ', 'QUÝ TỴ'), ('GIÁP NGỌ', 'GIÁP NGỌ'), ('ẤT MÙI', 'ẤT MÙI'), ('BÍNH THÂN', 'BÍNH THÂN'), ('ĐINH DẬU', 'ĐINH DẬU'), ('MẬU TUẤT', 'MẬU TUẤT'), ('KỶ HỢI', 'KỶ HỢI'), ('CANH TÝ', 'CANH TÝ'), ('TÂN SỬU', 'TÂN SỬU'), ('NHÂM DẦN', 'NHÂM DẦN'), ('QUÝ MÃO', 'QUÝ MÃO'), ('GIÁP THÌN', 'GIÁP THÌN'), ('ẤT TỴ', 'ẤT TỴ'), ('BÍNH NGỌ', 'BÍNH NGỌ'), ('ĐINH MÙI', 'ĐINH MÙI'), ('MẬU THÂN', 'MẬU THÂN'), ('KỶ DẬU', 'KỶ DẬU'), ('CANH TUẤT', 'CANH TUẤT'), ('TÂN HỢI', 'TÂN HỢI'), ('NHÂM TÝ', 'NHÂM TÝ'), ('QUÝ SỬU', 'QUÝ SỬU'), ('GIÁP DẦN', 'GIÁP DẦN'), ('ẤT MÃO', 'ẤT MÃO'), ('BÍNH THÌN', 'BÍNH THÌN'), ('ĐINH TỴ', 'ĐINH TỴ'), ('MẬU NGỌ', 'MẬU NGỌ'), ('KỶ MÙI', 'KỶ MÙI'), ('CANH THÂN', 'CANH THÂN'), ('TÂN DẬU', 'TÂN DẬU'), ('NHÂM TUẤT', 'NHÂM TUẤT'), ('QUÝ HỢI', 'QUÝ HỢI')], max_length=255, unique=True, verbose_name='Ngày can chi'),
        ),
        migrations.AlterField(
            model_name='quynhan',
            name='am_duong',
            field=models.CharField(choices=[('Âm quý', 'Âm quý'), ('Dương quý', 'Dương quý')], max_length=255, null=True, verbose_name='Âm dương'),
        ),
        migrations.AlterField(
            model_name='quynhan',
            name='can_ngay',
            field=models.CharField(choices=[('Giáp', 'Tý'), ('Ất', 'Sửu'), ('Bính', 'Dần'), ('Đinh', 'Mão'), ('Mậu', 'Thìn'), ('Kỷ', 'Tỵ'), ('Canh', 'Ngọ'), ('Tân', 'Mùi'), ('Nhâm', 'Thân'), ('Quý', 'Dậu')], max_length=255, verbose_name='Can ngày'),
        ),
        migrations.AlterField(
            model_name='quynhan',
            name='hour',
            field=models.CharField(choices=[('Tý', 'Tý'), ('Sửu', 'Sửu'), ('Dần', 'Dần'), ('Mão', 'Mão'), ('Thìn', 'Thìn'), ('Tỵ', 'Tỵ'), ('Ngọ', 'Ngọ'), ('Mùi', 'Mùi'), ('Thân', 'Thân'), ('Dậu', 'Dậu'), ('Tuất', 'Tuất'), ('Hợi', 'Hợi')], max_length=255, verbose_name='Giờ'),
        ),
        migrations.AlterField(
            model_name='quynhan',
            name='quy_nhan',
            field=models.CharField(choices=[('Tý', 'Tý'), ('Sửu', 'Sửu'), ('Dần', 'Dần'), ('Mão', 'Mão'), ('Thìn', 'Thìn'), ('Tỵ', 'Tỵ'), ('Ngọ', 'Ngọ'), ('Mùi', 'Mùi'), ('Thân', 'Thân'), ('Dậu', 'Dậu'), ('Tuất', 'Tuất'), ('Hợi', 'Hợi')], max_length=255, null=True, verbose_name='Quý nhân'),
        ),
        migrations.AlterField(
            model_name='quynhan',
            name='tiet_khi',
            field=models.CharField(choices=[('Lập Xuân', 'Lập Xuân'), ('Vũ Thủy', 'Vũ Thủy'), ('Kinh Trập', 'Kinh Trập'), ('Xuân Phân', 'Xuân Phân'), ('Thanh Minh', 'Thanh Minh'), ('Cốc Vũ', 'Cốc Vũ'), ('Lập Hạ', 'Lập Hạ'), ('Tiểu Mãn', 'Tiểu Mãn'), ('Mang Chủng', 'Mang Chủng'), ('Hạ Chí', 'Hạ Chí'), ('Tiểu Thử', 'Tiểu Thử'), ('Đại Thử', 'Đại Thử'), ('Lập Thu', 'Lập Thu'), ('Xử Thử', 'Xử Thử'), ('Bạch Lộ', 'Bạch Lộ'), ('Thu Phân', 'Thu Phân'), ('Hàn Lộ', 'Hàn Lộ'), ('Sương Giáng', 'Sương Giáng'), ('Lập Đông', 'Lập Đông'), ('Tiểu Tuyết', 'Tiểu Tuyết'), ('Đại Tuyết', 'Đại Tuyết'), ('Đông Chí', 'Đông Chí'), ('Tiểu Hàn', 'Tiểu Hàn'), ('Đại Hàn', 'Đại Hàn')], max_length=255, verbose_name='Tiết khí'),
        ),
        migrations.AlterField(
            model_name='sao',
            name='is_mountain',
            field=models.IntegerField(blank=True, choices=[(1, 'Cung'), (2, 'Sơn')], null=True, verbose_name='Thuộc cung hay sơn'),
        ),
        migrations.AlterField(
            model_name='sao',
            name='property',
            field=models.TextField(blank=True, null=True, verbose_name='Thuộc tính'),
        ),
        migrations.AlterField(
            model_name='saohiepky',
            name='hiepky',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='apis.hiepky', verbose_name='Ngày'),
        ),
        migrations.AlterField(
            model_name='saohour1',
            name='hour_1',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='apis.hourinday', verbose_name='Giờ tý'),
        ),
        migrations.AlterField(
            model_name='saohour10',
            name='hour_10',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='apis.hourinday', verbose_name='Giờ dậu'),
        ),
        migrations.AlterField(
            model_name='saohour11',
            name='hour_11',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='apis.hourinday', verbose_name='Giờ tuất'),
        ),
        migrations.AlterField(
            model_name='saohour12',
            name='hour_12',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='apis.hourinday', verbose_name='Giờ hợi'),
        ),
        migrations.AlterField(
            model_name='saohour2',
            name='hour_2',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='apis.hourinday', verbose_name='Giờ sửu'),
        ),
        migrations.AlterField(
            model_name='saohour3',
            name='hour_3',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='apis.hourinday', verbose_name='Giờ dần'),
        ),
        migrations.AlterField(
            model_name='saohour4',
            name='hour_4',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='apis.hourinday', verbose_name='Giờ mão'),
        ),
        migrations.AlterField(
            model_name='saohour5',
            name='hour_5',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='apis.hourinday', verbose_name='Giờ thìn'),
        ),
        migrations.AlterField(
            model_name='saohour6',
            name='hour_6',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='apis.hourinday', verbose_name='Giờ tỵ'),
        ),
        migrations.AlterField(
            model_name='saohour7',
            name='hour_7',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='apis.hourinday', verbose_name='Giờ ngọ'),
        ),
        migrations.AlterField(
            model_name='saohour8',
            name='hour_8',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='apis.hourinday', verbose_name='Giờ mùi'),
        ),
        migrations.AlterField(
            model_name='saohour9',
            name='hour_9',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='apis.hourinday', verbose_name='Giờ thân'),
        ),
        migrations.AlterField(
            model_name='tudaicatthoi',
            name='can_ngay',
            field=models.CharField(choices=[('Giáp', 'Tý'), ('Ất', 'Sửu'), ('Bính', 'Dần'), ('Đinh', 'Mão'), ('Mậu', 'Thìn'), ('Kỷ', 'Tỵ'), ('Canh', 'Ngọ'), ('Tân', 'Mùi'), ('Nhâm', 'Thân'), ('Quý', 'Dậu')], max_length=255, null=True, verbose_name='Can ngày'),
        ),
        migrations.AlterField(
            model_name='tudaicatthoi',
            name='hour',
            field=models.CharField(choices=[('Tý', 'Tý'), ('Sửu', 'Sửu'), ('Dần', 'Dần'), ('Mão', 'Mão'), ('Thìn', 'Thìn'), ('Tỵ', 'Tỵ'), ('Ngọ', 'Ngọ'), ('Mùi', 'Mùi'), ('Thân', 'Thân'), ('Dậu', 'Dậu'), ('Tuất', 'Tuất'), ('Hợi', 'Hợi')], max_length=255, verbose_name='Giờ'),
        ),
        migrations.AlterField(
            model_name='tudaicatthoi',
            name='tiet_khi',
            field=models.CharField(choices=[('Lập Xuân', 'Lập Xuân'), ('Vũ Thủy', 'Vũ Thủy'), ('Kinh Trập', 'Kinh Trập'), ('Xuân Phân', 'Xuân Phân'), ('Thanh Minh', 'Thanh Minh'), ('Cốc Vũ', 'Cốc Vũ'), ('Lập Hạ', 'Lập Hạ'), ('Tiểu Mãn', 'Tiểu Mãn'), ('Mang Chủng', 'Mang Chủng'), ('Hạ Chí', 'Hạ Chí'), ('Tiểu Thử', 'Tiểu Thử'), ('Đại Thử', 'Đại Thử'), ('Lập Thu', 'Lập Thu'), ('Xử Thử', 'Xử Thử'), ('Bạch Lộ', 'Bạch Lộ'), ('Thu Phân', 'Thu Phân'), ('Hàn Lộ', 'Hàn Lộ'), ('Sương Giáng', 'Sương Giáng'), ('Lập Đông', 'Lập Đông'), ('Tiểu Tuyết', 'Tiểu Tuyết'), ('Đại Tuyết', 'Đại Tuyết'), ('Đông Chí', 'Đông Chí'), ('Tiểu Hàn', 'Tiểu Hàn'), ('Đại Hàn', 'Đại Hàn')], max_length=255, verbose_name='Tiết khí'),
        ),
        migrations.AlterUniqueTogether(
            name='hiepky',
            unique_together={('month', 'lunar_day')},
        ),
    ]
