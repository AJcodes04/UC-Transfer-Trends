"""Introduce the Major table and point TransferData at it.

One Major per distinct major_name is created and linked, then the alias/grouping
rules are applied. Not reversible: the major_name column is dropped at the end.
"""

import django.db.models.deletion
from django.db import migrations, models


def seed_majors(apps, schema_editor):
    Major = apps.get_model('api', 'Major')
    TransferData = apps.get_model('api', 'TransferData')
    names = TransferData.objects.order_by().values_list('major_name', flat=True).distinct()
    Major.objects.bulk_create([Major(name=n) for n in names], ignore_conflicts=True)
    for name, major_id in Major.objects.order_by().values_list('name', 'id'):
        TransferData.objects.filter(major_name=name).update(major_id=major_id)

    from api.services.major_sync import sync_major_groups
    sync_major_groups(Major)


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0005_campus'),
    ]

    operations = [
        migrations.CreateModel(
            name='Major',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100, unique=True)),
                ('canonical', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.PROTECT,
                                                related_name='aliases', to='api.major')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL,
                                             related_name='children', to='api.major')),
            ],
            options={'ordering': ['name']},
        ),
        migrations.AddConstraint(
            model_name='major',
            constraint=models.CheckConstraint(
                condition=models.Q(('canonical__isnull', True), ('parent__isnull', True), _connector='OR'),
                name='major_alias_has_no_parent',
            ),
        ),
        migrations.RemoveConstraint(model_name='transferdata', name='transferdata_unique_campus_year_major_college'),
        migrations.AlterModelOptions(
            name='transferdata',
            options={'ordering': ['-year', 'campus__code'],
                     'verbose_name': 'Transfer Data', 'verbose_name_plural': 'Transfer Data'},
        ),
        migrations.AddField(
            model_name='transferdata',
            name='major',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='transfer_rows', to='api.major'),
        ),
        migrations.RunPython(seed_majors, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='transferdata',
            name='major',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                    related_name='transfer_rows', to='api.major'),
        ),
        migrations.RemoveField(model_name='transferdata', name='major_name'),
        migrations.AddConstraint(
            model_name='transferdata',
            constraint=models.UniqueConstraint(
                fields=('campus', 'year', 'major', 'college_school'),
                name='transferdata_unique_campus_year_major_college',
            ),
        ),
        migrations.AlterModelOptions(
            name='transferdata',
            options={'ordering': ['-year', 'campus__code', 'major__name'],
                     'verbose_name': 'Transfer Data', 'verbose_name_plural': 'Transfer Data'},
        ),
    ]
