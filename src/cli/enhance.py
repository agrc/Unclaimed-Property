#!/usr/bin/env python
# * coding: utf8 *
"""
enhance.py
A module that handles appending information to the geocoded csv files
"""

import arcpy
from timeit import default_timer
from pathlib import Path

gdb_name = 'enhance.gdb'

enhancement_layers = [{
    'table': 'political.senate_districts_2012',
    'fields': ['dist'],
    'rename': ['senate_district']
}, {
    'table': 'political.house_districts_2012',
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

        if field.name.lower() not in table_metadata['fields']:
            mapping.removeFieldMap(index)
        else:
            if field.name.lower() == 'shape':
                continue

            field_map = mapping.getFieldMap(index)
            outputField = field_map.outputField
            outputField.name = table_metadata['rename'][0]

            field_map.outputField = outputField
            mapping.replaceFieldMap(index, field_map)
