import pytest
from internships_project.city_source_merge import merge_source_bytes
from internships_project.marketdesk_city import CityError


def test_parallel_registry_additions_preserve_both_employers():
    base=b'REGISTRY = {\n    "Existing": "board",\n}\n'
    current=base.replace(b'    "Existing"',b'    "Capital Group": "capital",\n    "Existing"')
    mission=base.replace(b'    "Existing"',b'    "Maven": "maven",\n    "Existing"')
    merged=merge_source_bytes(base,mission,current)
    assert all(value in merged for value in (b'Capital Group',b'Maven',b'Existing'))
    compile(merged,'registry.py','exec')


def test_parallel_edits_to_same_employer_are_not_overwritten():
    base=b'REGISTRY = {\n    "Existing": "board",\n}\n'
    with pytest.raises(CityError,match='code existant'):
        merge_source_bytes(base,base.replace(b'board',b'one'),base.replace(b'board',b'two'))


def test_conflicting_new_entries_for_same_employer_are_not_combined():
    base=b'REGISTRY = {\n    "Existing": "board",\n}\n'
    first=base.replace(b'    "Existing"',b'    "New": "one",\n    "Existing"')
    second=base.replace(b'    "Existing"',b'    "New": "two",\n    "Existing"')
    with pytest.raises(CityError,match='même entreprise'):merge_source_bytes(base,first,second)


def test_parallel_function_changes_outside_registry_are_not_union_merged():
    with pytest.raises(CityError):merge_source_bytes(b'x=1\n',b'x=2\n',b'x=3\n')


def test_already_integrated_mission_preserves_newer_current_code():
    assert merge_source_bytes(b'x=1\n',b'x=1\n',b'x=2\n')==b'x=2\n'


def test_windows_line_endings_do_not_create_a_whole_file_conflict():
    base=b'REGISTRY = {\r\n    "Existing": "board",\r\n}\r\n'
    mission=base.replace(b'    "Existing"',b'    "Maven": "maven",\r\n    "Existing"')
    current=base.replace(b'\r\n',b'\n').replace(b'    "Existing"',b'    "Capital": "capital",\n    "Existing"')
    result=merge_source_bytes(base,mission,current)
    assert b'Capital' in result and b'Maven' in result


def test_parallel_category_additions_keep_all_existing_members():
    merged=merge_source_bytes(b"TRADING = {'Existing'}\n",b"TRADING = {'Maven','Existing'}\n",b"TRADING = {'Squarepoint','Existing'}\n")
    values={};exec(merged,values)
    assert values['TRADING']=={'Existing','Maven','Squarepoint'}


def test_category_merge_refuses_to_restore_or_hide_a_deletion():
    with pytest.raises(CityError):
        merge_source_bytes(b"TRADING = {'A','B'}\n",b"TRADING = {'A','B','C'}\n",b"TRADING = {'A'}\n")
