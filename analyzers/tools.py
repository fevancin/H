from pathlib import Path
import argparse
import json
import time
import csv


def get_subproblem_results_value(master_instance, master_results, day_name):

    is_priority = True
    for patient in master_instance['patients'].values():
        if 'priority' not in patient:
            is_priority = False
            break

    value = 0
    for schedule_item in master_results['scheduled'][day_name]:
        
        service_name = schedule_item['service']
        service_duration = master_instance['services'][service_name]['duration']
        
        if is_priority:
            
            patient_name = schedule_item['patient']
            patient_priority = master_instance['patients'][patient_name]['priority']
            
            value += service_duration * patient_priority
        
        else:
            value += service_duration
    
    return value


def get_master_results_value(master_instance, master_results):

    value = 0
    for day_name in master_results['scheduled']:
        value += get_subproblem_results_value(master_instance, master_results, day_name)
    
    return value


def get_satisfied_window_number(master_results):

    satisfied_window_number = 0
    for day in master_results['scheduled'].values():
        satisfied_window_number += len(day)
    
    return satisfied_window_number


def analyze_master_results(master_instance, master_results, instance_path):
    
    data = {}
    data['group'] = instance_path.parent.name
    data['instance'] = instance_path.stem
    data = master_results['info']
    data['satisfied_window_number'] = get_satisfied_window_number(master_results)
    data['rejected_window_number'] = len(master_results['rejected'])
    data['solution_value'] = get_master_results_value(master_instance, master_results)

    return data


def common_main_analyzer(command_name, analyzer_function, analysis_file_name, need_results):

    parser = argparse.ArgumentParser(prog=command_name, description='Analyze instances')
    parser.add_argument('-i', '--input', type=Path, help='Group instances directory path', required=True)
    parser.add_argument('-v', '--verbose', action='store_true', help='Show what is done')
    args = parser.parse_args()

    group_directory_path = Path(args.input).resolve()
    is_verbose = bool(args.verbose)

    if not group_directory_path.exists():
        raise ValueError(f'Group directory \'{group_directory_path}\' does not exists')
    elif not group_directory_path.is_dir():
        raise ValueError(f'Group \'{group_directory_path}\' is not a directory')
    
    input_directory_path = group_directory_path.joinpath('input')
    if not input_directory_path.exists():
        raise ValueError(f'Input directory \'{input_directory_path}\' does not exists')
    elif not input_directory_path.is_dir():
        raise ValueError(f'Input \'{input_directory_path}\' is not a directory')

    if need_results:
        results_directory_path = group_directory_path.joinpath('results')
        if not results_directory_path.exists():
            raise ValueError(f'Input directory \'{results_directory_path}\' does not exists')
        elif not results_directory_path.is_dir():
            raise ValueError(f'Input \'{results_directory_path}\' is not a directory')

    if is_verbose:
        print(f'Analyzing data in directory \'{group_directory_path}\'')
        total_start_time = time.perf_counter()
        instance_number = 0

    analysis_data = []

    for instance_file_path in input_directory_path.iterdir():

        if not instance_file_path.is_file() or instance_file_path.suffix != '.json':
            continue

        instance_file_name = instance_file_path.name.removesuffix('.json')
        with open(instance_file_path, 'r') as file:
            instance = json.load(file)
        
        if need_results:
            results_file_path = results_directory_path.joinpath(f'{instance_file_name}_results.json')
        
            if not results_file_path.is_file():
                continue

            with open(results_file_path, 'r') as file:
                results = json.load(file)

        if is_verbose:
            print(f'Start analyzing instance \'{instance_file_name}\'')
            instance_number += 1
            analyzing_start_time = time.perf_counter()

        if need_results:
            analysis_data.append(analyzer_function(instance, results, instance_file_path))
        else:
            analysis_data.append(analyzer_function(instance, instance_file_path))

        if is_verbose:
            analyzing_end_time = time.perf_counter()
            print(f'End analyzing instance \'{instance_file_name}\'. Took {analyzing_start_time - analyzing_end_time} seconds.')

    if is_verbose and len(analysis_data) == 0:
        print(f'Directory \'{group_directory_path}\' has no instances')
        return
    
    field_names = list(analysis_data[0].keys())
    
    with open(group_directory_path.joinpath(group_directory_path.joinpath(analysis_file_name)), 'w', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=field_names, dialect='excel-tab')
        writer.writeheader()
        writer.writerows(analysis_data)

    if is_verbose:
        total_end_time = time.perf_counter()
        print(f'End analyzing process. Time elapsed: {total_end_time - total_start_time} seconds')
        print(f'Analyzed {instance_number} instances')