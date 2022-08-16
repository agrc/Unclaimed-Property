#!/usr/bin/env python
# * coding: utf8 *
"""
enhance.py
A module that handles appending information to the geocoded csv files
"""

try:
    import arcpy
except:
    pass
import csv
from pathlib import Path
from timeit import default_timer
import pandas as pd

UTM = "PROJCS['NAD_1983_UTM_Zone_12N',GEOGCS['GCS_North_American_1983',DATUM['D_North_American_1983',SPHEROID['GRS_1980',6378137.0,298.257222101]],PRIMEM['Greenwich',0.0],UNIT['Degree',0.0174532925199433]],PROJECTION['Transverse_Mercator'],PARAMETER['False_Easting',500000.0],PARAMETER['False_Northing',0.0],PARAMETER['Central_Meridian',-111.0],PARAMETER['Scale_Factor',0.9996],PARAMETER['Latitude_Of_Origin',0.0],UNIT['Meter',1.0]];-5120900 -9998100 10000;-100000 10000;-100000 10000;0.001;0.001;0.001;IsHighPrecision"

gdb_name = 'enhance.gdb'

enhancement_layers = [{
    'table': 'political.senate_districts_2022_to_2032',
    'fields': ['dist'],
    'rename': ['senate_district']
}, {
    'table': 'political.house_districts_2022_to_2032',
    'fields': ['dist'],
    'rename': ['house_district']
}, {
    'table': 'boundaries.county_boundaries',
    'fields': ['name'],
    'rename': ['county_name']
}, {
    'table': 'demographic.census_tracts_2020',
    'fields': ['geoid20'],
    'rename': ['census_id']
}]


def create_enhancement_gdb(parent_folder):
    """Creates the file geodatabase that will be used to store the enhanced layers

    :param parent_folder: The parent path to the file geodatabase to create
    :type parent_folder: Path
    """
    parent_folder = Path(parent_folder)
    gdb_path = parent_folder / gdb_name

    if gdb_path.exists():
        print(f'{gdb_name} exists. deleting and recreating with fresh data')

        arcpy.management.Delete(str(gdb_path))

    print('creating file geodatabase')
    start = default_timer()

    arcpy.management.CreateFileGDB(str(parent_folder), gdb_name)

    print(f'file geodatabase created in {default_timer() - start} seconds')

    add_enhancement_layers(parent_folder / gdb_name)


def add_enhancement_layers(output_gdb):
    """Adds the enhancement layers to the file geodatabase
    :param output_gdb: The path to the file geodatabase to add the enhancement layers to
    :type output_gdb: Path
    """
    print('adding enhancement layers')
    start = default_timer()

    maps = Path(__file__).parent.parent.parent / 'maps'
    workspace = (maps / 'opensgid.agrc.utah.gov.sde').resolve()

    with arcpy.EnvManager(workspace=str(workspace)):
        for layer in enhancement_layers:
            table_start = default_timer()
            print(f'    adding {layer["table"]}')
            mapping = arcpy.FieldMappings()
            mapping.addTable(layer['table'])

            fields = arcpy.ListFields(layer['table'])

            filter_mapping(mapping, fields, layer)

            arcpy.conversion.FeatureClassToFeatureClass(
                in_features=layer['table'],
                out_path=str(output_gdb),
                out_name=layer['table'].split('.')[1],
                field_mapping=mapping
            )

            print(f'    {layer["table"]} finished in {default_timer() - table_start} seconds')

    print(f'enhancement layers added in {default_timer() - start} seconds')


def merge(parent_folder):
    """Creates a single csv file containing all the enhanced data

    :param parent_folder: The parent path to the results folder
    :type parent_folder: Path
    """
    parent_folder = Path(parent_folder)

    address_csv_files = sorted(parent_folder.glob('*_step_*.csv'))

    frames = []

    #: read all csv's delimiter='|', quoting=csv.QUOTE_MINIMAL
    for address_csv_file in address_csv_files:
        temp = pd.read_csv(
            address_csv_file, sep='|', encoding='utf-8', names=['type', 'id', 'county', 'senate', 'house', 'census']
        )

        frames.append(temp)

    #: merge all csv's
    merged = pd.DataFrame()
    for frame in frames:
        merged = merged.append(frame)

    merged.to_csv(parent_folder / 'all.csv', sep='|', header=False, index=False, encoding='utf-8')


def filter_mapping(mapping, fields, table_metadata):
    """Filters the field mapping to only include the fields that are needed
    :param mapping: The field mapping to filter
    :type mapping: arcpy.FieldMappings
    :param fields: The fields on the table
    :type fields: list[arcpy.Field]
    :param table_metadata: The table metadata to use to filter the field mapping
    :type table_metadata: dict
    """
    table_metadata['fields'].append('shape')

    for field in fields:
        index = mapping.findFieldMapIndex(field.name)

        if index == -1:
            continue

        if field.name.lower() not in table_metadata['fields']:
            try:
                mapping.removeFieldMap(index)
            except Exception as ex:
                print(field.name.lower())
                raise ex
        else:
            if field.name.lower() == 'shape':
                continue

            field_map = mapping.getFieldMap(index)
            outputField = field_map.outputField
            outputField.name = table_metadata['rename'][0]

            field_map.outputField = outputField
            mapping.replaceFieldMap(index, field_map)


def enhance(parent_folder):
    """enhances the csv table data from the identity tables

    :param parent_folder: The parent path to the csv files to enhance
    :type parent_folder: Path
    """
    parent_folder = Path(parent_folder).resolve()
    address_csv_files = sorted(parent_folder.glob('*.csv'))

    print(f'enhancing {len(address_csv_files)} csv files in {parent_folder}')

    data = Path(__file__).parent.parent.parent / 'data'
    workspace = (data / 'enhanced' / gdb_name).resolve()

    arcpy.env.workspace = str(workspace)

    for address_csv in address_csv_files:
        job = enhance_data(address_csv)

        prepare_output(job)
        convert_to_csv(job)
        remove_temp_tables(job)


def enhance_data(address_csv):
    """enhance the data in the csv file
    """
    table_name = address_csv.stem

    print(f'1. creating points from csv as {table_name}')

    if not arcpy.Exists(f'{table_name}_step_1'):
        arcpy.management.MakeXYEventLayer(
            table=str(address_csv),
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
            in_layer_or_view=f'{table_name}_step_1', selection_type='NEW_SELECTION', where_clause='score>0'
        )
    else:
        print('    skipping')

    print('   separating matched addresses')

    if not arcpy.Exists(f'{table_name}_step_2'):
        arcpy.management.CopyFeatures(in_features=f'{table_name}_step_1', out_feature_class=f'{table_name}_step_2')
    else:
        print('    skipping')

    step = 2
    for identity in enhancement_layers:
        start = default_timer()
        print('{}. enhancing data with {} from {}'.format(step, "'".join(identity['fields']), identity['table']))

        enhance_table_name = identity['table'].split('.')[1]

        if not arcpy.Exists(f'{table_name}_step_{step + 1}'):
            arcpy.analysis.Identity(
                in_features=f'{table_name}_step_{step}',
                identity_features=enhance_table_name,
                out_feature_class=f'{table_name}_step_{step + 1}',
                join_attributes='NO_FID',
                cluster_tolerance=None,
                relationship='NO_RELATIONSHIPS'
            )
        else:
            print('    skipping')
            step = step + 1

            continue

        step = step + 1
        print(f'completed: {default_timer() - start}')

    return f'{table_name}_step_{step}'


def prepare_output(table):
    """prepares the output by splitting the primary key and the other field
    """
    print('adding type field')

    absolute_table = str(Path(arcpy.env.workspace) / table)

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

    destination = Path(__file__).parent.parent.parent / 'data' / 'results' / f'{table}.csv'

    with arcpy.da.SearchCursor(
        in_table=table,
        field_names=['type', 'primary_key', 'county_name', 'senate_district', 'house_district', 'census_id'],
        where_clause='message is null'
    ) as cursor, open(destination, 'w', newline='') as result_file:
        writer = csv.writer(result_file, delimiter='|', quoting=csv.QUOTE_MINIMAL)

        for row in cursor:
            writer.writerow(row)


def remove_temp_tables(table):
    """clean up method
    """
    temp_tables = sorted(arcpy.ListFeatureClasses(wild_card=f'{table[:-1]}*', feature_type='Point'))
    removed = False

    print('removing ', ', '.join(temp_tables[:-1]))

    try:
        arcpy.management.Delete(temp_tables[:-1])
        removed = True
    except:
        print('could not delete intermediate tables. trying one at a time')

    if not removed:  #: try pro < 2.9 style
        for table in temp_tables[:-1]:
            arcpy.management.Delete(table)

    print('intermediate tables removed')
