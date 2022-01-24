#!/usr/bin/env python
# * coding: utf8 *
"""
Point Extraction

Usage:
  extract.py enhance <csv> --as=name

Options:
	--as=name          the new name of the csv outputs [default: job]
"""
import csv
from pathlib import Path
from timeit import default_timer

from docopt import docopt

import arcpy

UTM = "PROJCS['NAD_1983_UTM_Zone_12N',GEOGCS['GCS_North_American_1983',DATUM['D_North_American_1983',SPHEROID['GRS_1980',6378137.0,298.257222101]],PRIMEM['Greenwich',0.0],UNIT['Degree',0.0174532925199433]],PROJECTION['Transverse_Mercator'],PARAMETER['False_Easting',500000.0],PARAMETER['False_Northing',0.0],PARAMETER['Central_Meridian',-111.0],PARAMETER['Scale_Factor',0.9996],PARAMETER['Latitude_Of_Origin',0.0],UNIT['Meter',1.0]];-5120900 -9998100 10000;-100000 10000;-100000 10000;0.001;0.001;0.001;IsHighPrecision"
IDENTITY = [{
    'table': 'utahsenatedistricts2012',
    'fields': ['dist'],
    'rename': ['senate_district']
}, {
    'table': 'utahhousedistricts2012',
    'fields': ['dist'],
    'rename': ['house_district']
}, {
    'table': 'countyboundaries',
    'fields': ['name'],
    'rename': ['county_name']
}, {
    'table': 'census_tracts_2020',
    'fields': ['geoid20'],
    'rename': ['census_id']
}]


def main():
    """the main entry point for the script
    """
    args = docopt(__doc__, version='point data extraction cli v1.0.0')

    table = args['<csv>']
    table_name = args['--as']

    start = default_timer()
    job = extract(table, table_name)
    print(f'extract job took {default_timer() - start} seconds')
    prepare = default_timer()
    prepare_output(job)
    print(f'prepare output took {default_timer() - prepare} seconds')
    convert = default_timer()
    convert_to_csv(job)
    print(f'convert to csv took {default_timer() - convert} seconds')
    remove = default_timer()
    remove_temp_tables(job)
    print(f'remove temp tables took {default_timer() - remove} seconds')
    print(f'finished in {default_timer() - start} seconds')


def extract(table, table_name):
    """extracts data from the identity tables
    """
    print(f'1. creating points from csv as {table_name}')

    if not arcpy.Exists(f'{table_name}_step_1'):
        arcpy.management.MakeXYEventLayer(
            table=table,
            in_x_field='x',
            in_y_field='y',
            out_layer=f'{table_name}_temp',
            spatial_reference=UTM,
            in_z_field=None
        )
    else:
        print('    skipping')

    print('   creating feature class')

    if not arcpy.Exists(f'{table_name}_step_1'):
        arcpy.management.XYTableToPoint(
            in_table=f'{table_name}_temp',
            out_feature_class=f'{table_name}_step_1',
            x_field='x',
            y_field='y',
            z_field=None,
            coordinate_system=UTM
        )
    else:
        print('    skipping')

    print('   selecting match addresses')

    if not arcpy.Exists(f'{table_name}_step_2'):
        arcpy.management.SelectLayerByAttribute(
            in_layer_or_view=f'{table_name}_step_1', selection_type='NEW_SELECTION', where_clause='message IS NULL'
        )
    else:
        print('    skipping')

    print('   separating matched addresses')

    if not arcpy.Exists(f'{table_name}_step_2'):
        arcpy.management.CopyFeatures(in_features=f'{table_name}_step_1', out_feature_class=f'{table_name}_step_2')
    else:
        print('    skipping')

    step = 2
    for identity in IDENTITY:
        start = default_timer()
        print('{}. enhancing data with {} from {}'.format(step, "'".join(identity['fields']), identity['table']))

        if not arcpy.Exists(f'{table_name}_step_{step + 1}'):
            arcpy.analysis.Identity(
                in_features=f'{table_name}_step_{step}',
                identity_features=identity['table'],
                out_feature_class=f'{table_name}_step_{step + 1}',
                join_attributes='NO_FID',
                cluster_tolerance=None,
                relationship='NO_RELATIONSHIPS'
            )
        else:
            print('    skipping')
            step = step + 1

            continue

        metadata = arcpy.da.Describe(identity['table'])
        job_metadata = arcpy.da.Describe(f'{table_name}_step_{step + 1}')

        fields = [field.name.lower() for field in metadata['fields']]
        job_fields = [field.name.lower() for field in job_metadata['fields']]

        skip_fields = identity['fields'] + [metadata['shapeFieldName'].lower(), metadata['OIDFieldName'].lower()]
        extra_fields = [field for field in fields if field.lower() not in skip_fields]

        print(f'   removing extra fields: {" ".join(extra_fields)}')

        if len(extra_fields) > 0:
            arcpy.management.DeleteField(in_table=f'{table_name}_step_{step + 1}', drop_field=';'.join(extra_fields))

        for i, field in enumerate(identity['fields']):
            print(f'   renaming {field} -> {identity["rename"][i]}')

            if not field.lower() in job_fields:
                continue

            arcpy.management.AlterField(
                in_table=f'{table_name}_step_{step + 1}',
                field=field,
                new_field_name=identity['rename'][i],
                new_field_alias=identity['rename'][i]
            )

        step = step + 1
        print(f'completed: {default_timer() - start}')

    return f'{table_name}_step_{step}'


def prepare_output(table):
    """prepares the output but splitting the primary key and the other field
    """
    print('adding type field')

    absolute_table = str(Path(arcpy.env.workspace).joinpath(table))

    fields = arcpy.ListFields(absolute_table)
    if 'type' in [field.name.lower() for field in fields]:
        print('    skipping')
        return

    arcpy.management.AddField(absolute_table, 'type', 'TEXT', '', '', '1')

    print('splitting type and id')
    arcpy.management.CalculateField(
        in_table=table, field='type', expression='left($feature.primary_key, 1)', expression_type='ARCADE'
    )

    arcpy.management.CalculateField(
        in_table=table, field='primary_key', expression='mid($feature.primary_key, 1, 20)', expression_type='ARCADE'
    )


def convert_to_csv(table):
    """writes table to csv
    """
    print(f'writing {table} to csv')

    with arcpy.da.SearchCursor(
        in_table=table,
        field_names=['type', 'primary_key', 'county_name', 'senate_district', 'house_district', 'census_id'],
        where_clause='message is null'
    ) as cursor, open(f'{table}_result.csv', 'w', newline='') as result_file:
        writer = csv.writer(result_file, delimiter='|', quoting=csv.QUOTE_MINIMAL)

        for row in cursor:
            writer.writerow(row)


def remove_temp_tables(table):
    """clean up method
    """
    temp_tables = sorted(arcpy.ListFeatureClasses(wild_card=f'{table[:-1]}*', feature_type='Point'))

    print('removing ', ', '.join(temp_tables[:-1]))

    arcpy.management.Delete(temp_tables[:-1])


if __name__ == '__main__':
    gdb = str(Path('..\\..\\data\\enhanced\\enhance.gdb').absolute())
    print(gdb)

    if not arcpy.Exists(gdb):
        raise Exception('The enhancement geodatabase was not found. Run this command from the post-process folder.')

    arcpy.env.workspace = gdb

    main()
