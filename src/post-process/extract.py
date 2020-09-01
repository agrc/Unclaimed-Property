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
    'table': 'parcels_utah',
    'fields': ['ownername'],
    'rename': ['owner_name']
}, {
    'table': 'countyboundaries',
    'fields': ['name'],
    'rename': ['county_name']
}, {
    'table': 'census_tracts_2010',
    'fields': ['geoid10'],
    'rename': ['census_id']
}]


def main():
    """the main entry point for the script
    """
    args = docopt(__doc__, version='point data extraction cli v1.0.0')

    table = args['<csv>']
    table_name = args['--as']

    job = extract(table, table_name)
    prepare_output(job)
    convert_to_csv(job)
    remove_temp_tables(job)


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

    print('   selecting match addresses')

    arcpy.management.SelectLayerByAttribute(
        in_layer_or_view=f'{table_name}_step_1', selection_type='NEW_SELECTION', where_clause='message IS NULL'
    )

    print('   separating matched addresses')

    arcpy.management.CopyFeatures(in_features=f'{table_name}_step_1', out_feature_class=f'{table_name}_step_2')

    step = 2
    for identity in IDENTITY:
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

    return f'{table_name}_step_{step}'


def prepare_output(table):
    """prepares the output but splitting the primary key and the other field
    """
    print('adding type field')

    arcpy.management.AddField(str(Path(arcpy.env.workspace).joinpath(table)), 'type', 'TEXT', '', '', '1')

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
    print('writing to csv')

    with arcpy.da.SearchCursor(
        in_table=table,
        field_names=['type', 'primary_key', 'senate_district', 'house_district', 'owner_name', 'census_id'],
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
    arcpy.env.workspace = '..\\..\\data\\enhanced\\enhance.gdb'
    main()
