"""Introduce the Campus table and point TransferData and CampusStats at it.

Data is copied from the existing code columns so this runs unattended on production.
Not reversible: the old text columns are dropped at the end.
"""

import django.db.models.deletion
from django.db import migrations, models

CAMPUS_NAMES = {
    'UCB': 'University of California, Berkeley',
    'UCD': 'University of California, Davis',
    'UCI': 'University of California, Irvine',
    'UCLA': 'University of California, Los Angeles',
    'UCM': 'University of California, Merced',
    'UCR': 'University of California, Riverside',
    'UCSB': 'University of California, Santa Barbara',
    'UCSC': 'University of California, Santa Cruz',
    'UCSD': 'University of California, San Diego',
}


def seed_campuses(apps, schema_editor):
    Campus = apps.get_model('api', 'Campus')
    TransferData = apps.get_model('api', 'TransferData')
    CampusStats = apps.get_model('api', 'CampusStats')
    codes = set(CAMPUS_NAMES)
    codes.update(TransferData.objects.order_by().values_list('university', flat=True).distinct())
    codes.update(CampusStats.objects.order_by().values_list('campus_code', flat=True).distinct())
    for code in sorted(codes):
        Campus.objects.get_or_create(code=code, defaults={'name': CAMPUS_NAMES.get(code, code)})


def link_campuses(apps, schema_editor):
    Campus = apps.get_model('api', 'Campus')
    TransferData = apps.get_model('api', 'TransferData')
    CampusStats = apps.get_model('api', 'CampusStats')
    for campus in Campus.objects.order_by('code'):
        TransferData.objects.filter(university=campus.code).update(campus=campus)
        CampusStats.objects.filter(campus_code=campus.code).update(campus=campus)


class Migration(migrations.Migration):

    dependencies = [
        ('api', '0004_prune_indexes'),
    ]

    operations = [
        migrations.CreateModel(
            name='Campus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('code', models.CharField(max_length=10, unique=True)),
                ('name', models.CharField(max_length=100)),
            ],
            options={'ordering': ['code'], 'verbose_name_plural': 'Campuses'},
        ),
        migrations.RemoveConstraint(model_name='transferdata', name='transferdata_unique_campus_year_major_college'),
        migrations.RemoveIndex(model_name='transferdata', name='api_transfe_univers_0539ed_idx'),
        migrations.RemoveConstraint(model_name='campusstats', name='campusstats_unique_campus_year'),
        migrations.RenameField(model_name='campusstats', old_name='campus', new_name='campus_code'),
        migrations.RunPython(seed_campuses, migrations.RunPython.noop),
        migrations.AddField(
            model_name='transferdata',
            name='campus',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='transfer_rows', to='api.campus'),
        ),
        migrations.AddField(
            model_name='campusstats',
            name='campus',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.PROTECT,
                                    related_name='yearly_stats', to='api.campus'),
        ),
        migrations.RunPython(link_campuses, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='transferdata',
            name='campus',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                    related_name='transfer_rows', to='api.campus'),
        ),
        migrations.AlterField(
            model_name='campusstats',
            name='campus',
            field=models.ForeignKey(on_delete=django.db.models.deletion.PROTECT,
                                    related_name='yearly_stats', to='api.campus'),
        ),
        migrations.RemoveField(model_name='transferdata', name='university'),
        migrations.RemoveField(model_name='campusstats', name='campus_code'),
        migrations.AddConstraint(
            model_name='transferdata',
            constraint=models.UniqueConstraint(
                fields=('campus', 'year', 'major_name', 'college_school'),
                name='transferdata_unique_campus_year_major_college',
            ),
        ),
        migrations.AddIndex(
            model_name='transferdata',
            index=models.Index(fields=['campus', 'year'], name='transferdata_campus_year_idx'),
        ),
        migrations.AddConstraint(
            model_name='campusstats',
            constraint=models.UniqueConstraint(fields=('campus', 'year'), name='campusstats_unique_campus_year'),
        ),
        migrations.AlterModelOptions(
            name='transferdata',
            options={'ordering': ['-year', 'campus__code', 'major_name'],
                     'verbose_name': 'Transfer Data', 'verbose_name_plural': 'Transfer Data'},
        ),
        migrations.AlterModelOptions(
            name='campusstats',
            options={'ordering': ['-year', 'campus__code'],
                     'verbose_name': 'Campus Stats', 'verbose_name_plural': 'Campus Stats'},
        ),
    ]
