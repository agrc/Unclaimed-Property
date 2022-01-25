#!/usr/bin/env python
# * coding: utf8 *
"""
enhance.py
A module that handles appending information to the geocoded csv files
"""

import arcpy
from timeit import default_timer
from pathlib import Path

gdb_name = 'enhancement.gdb'

enhancement_layers = [{
    'table': 'political.senate_districts_2012',
    'fields': ['dist']
}, {
    'table': 'political.house_districts_2012',
    'fields': ['dist'],
}, {
    'table': 'boundaries.county_boundaries',
    'fields': ['name']
}, {
    'table': 'demographic.census_tracts_2020',
    'fields': ['geoid20']
}]


def create_enhancement_gdb(parent_folder):
    """Creates the file geodatabase that will be used to store the enhanced layers

    :param parent_folder: The parent path to the file geodatabase to create
    :type parent_folder: Path
    """

    if parent_folder.exists():
        print(f'{gdb_name} exists. deleting and recreating with fresh data')

        arcpy.management.Delete(str(parent_folder / gdb_name))

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

    maps = Path(__file__) / '..' / '..' / 'maps'
    workspace = (maps / 'opensgid.agrc.utah.gov.sde').absolute()

    with arcpy.EnvManager(workspace=str(workspace)):
        for layer in enhancement_layers:
            table_start = default_timer()
            print(f'    adding {layer["table"]}')
            mapping = arcpy.FieldMappings()
            mapping.addTable(layer['table'])

            filter_mapping(mapping, layer)

            arcpy.conversion.FeatureClassToFeatureClass(
                layer['table'], output_gdb, layer['table'], field_mapping=mapping
            )

            print(f'    {layer["table"]} finished in {default_timer() - table_start} seconds')

    print(f'enhancement layers added in {default_timer() - start} seconds')


def filter_mapping(mapping, table_metadata):
    """Filters the field mapping to only include the fields that are needed
    :param mapping: The field mapping to filter
    :type mapping: arcpy.FieldMappings
    :param table_metadata: The table metadata to use to filter the field mapping
    :type table_metadata: dict
    """
    fields = arcpy.ListFields(table_metadata['table'])

    for field in fields:
        if field.name.lower() not in table_metadata['fields']:
            index = mapping.findFieldMapIndex(field.name)
            mapping.removeFieldMap(index)
