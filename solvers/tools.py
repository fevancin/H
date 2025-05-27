from datetime import datetime
from pathlib import Path
import argparse
import json
import time
import yaml
import shutil
import pyomo.environ as pyo


def clamp(start: int, end: int, start_bound: int, end_bound: int) -> tuple[int, int]:
    """
    This function reduces the interval span [start, end] in order to make it
    stay inside the greater one defined by [start_bound, end_bound].
    If the interval is completely outside then a dummy interval [None, None] is
    returned.
    """

    if start > end_bound or end < start_bound:
        return (None, None)
    
    if start < start_bound:
        start = start_bound

    if end > end_bound:
        end = end_bound

    return (start, end)

    parser = argparse.ArgumentParser(prog=command_name, description='Solve instances')
    parser.add_argument('-i', '--input', type=Path, help='Group instances directory path', required=True)
    parser.add_argument('-c', '--config', type=Path, help='YAML file configuration path', required=True)
    parser.add_argument('-v', '--verbose', action='store_true', help='Show what is done')
    args = parser.parse_args()

    group_directory_path = Path(args.input).resolve()
    config_file_path = Path(args.config).resolve()
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

    if not config_file_path.exists():
        raise FileNotFoundError(f'Configuration file \'{config_file_path}\' does not exists.')
    if not config_file_path.is_file() or config_file_path.is_dir():
        raise ValueError(f'Configuration file \'{config_file_path}\' is not a file')
    if config_file_path.suffix != '.yaml':
        raise ValueError(f'Configuration file \'{config_file_path}\' is not a YAML file')

    with open(config_file_path, 'r') as file:
        config = yaml.load(file, yaml.Loader)

    results_directory_path = group_directory_path.joinpath('results')
    if results_directory_path.exists():
        shutil.rmtree(results_directory_path)
    results_directory_path.mkdir()

    if 'keep_logs' in config and config['keep_logs']:
        log_directory_path = group_directory_path.joinpath('logs')
        if log_directory_path.exists():
            shutil.rmtree(log_directory_path)
        log_directory_path.mkdir()

    solver_config_file_path = group_directory_path.joinpath('solver_config.yaml')
    with open(solver_config_file_path, 'w') as file:
        yaml.dump(config, file, default_flow_style=False)

    if is_verbose:
        print(f'Solving data in directory \'{group_directory_path}\' with configuration from \'{config_file_path}\'')
        total_start_time = time.perf_counter()
        instance_number = 0

    for instance_file_path in input_directory_path.iterdir():

        if not instance_file_path.is_file() or instance_file_path.suffix != '.json':
            continue

        with open(instance_file_path, 'r') as file:
            instance = json.load(file)
        
        instance_file_name = instance_file_path.name.removesuffix('.json')

        if is_verbose:
            print(f'Solving instance \'{instance_file_name}\'')
            print(f'Start model creation of instance \'{instance_file_name}\'')
            instance_number += 1
            model_creation_start_time = time.perf_counter()

        model = create_model_function(instance, config['additional_info'])
        
        if is_verbose:
            model_creation_end_time = time.perf_counter()
            print(f'End model creation of instance \'{instance_file_name}\'. Took {model_creation_end_time - model_creation_start_time} seconds.')

        if 'solver' in config:
            opt = pyo.SolverFactory(config['solver'])
        else:
            opt = pyo.SolverFactory('gurobi')

        if 'time_limit' in config:
            if config['solver'] == 'glpk':
                opt.options['tmlim'] = config['time_limit']
            else:
                opt.options['TimeLimit'] = config['time_limit']
        if 'max_memory' in config:
            opt.options['SoftMemLimit'] = config['max_memory']

        if is_verbose:
            print(f'Start solving process of instance {instance_file_name}')
            solving_start_time = time.perf_counter()
        
        if 'keep_logs' in config and config['keep_logs']:
            log_file_path = log_directory_path.joinpath(f'{instance_file_name}_log.log')
            model_results = opt.solve(model, tee=is_verbose, logfile=log_file_path)
        else:
            model_results = opt.solve(model, tee=is_verbose)
        
        if is_verbose:
            solving_end_time = time.perf_counter()
            print(f'End solving process of instance \'{instance_file_name}\'. Took {solving_end_time - solving_start_time} seconds.')

        model.solutions.store_to(model_results)
        solution = model_results.solution[0]
        lower_bound = float(model_results['problem'][0]['Lower bound'])
        upper_bound = float(model_results['problem'][0]['Upper bound'])
        gap = float(solution['gap'])
        if gap <= 1e-5 and lower_bound != upper_bound:
            gap = (upper_bound - lower_bound) / upper_bound
        value = float(solution['objective']['total_satisfied_service_durations']['Value'])

        results = {'info': {
            'timestamp': datetime.now().strftime('%a_%d_%m_%Y_%H_%M_%S'),
            'model_creation_time': model_creation_end_time - model_creation_start_time,
            'model_solving_time': solving_end_time - solving_start_time,
            'solver_internal_time': float(model_results.solver.time),
            'status': str(model_results.solver.status),
            'termination_condition': str(model_results.solver.termination_condition),
            'lower_bound': lower_bound,
            'upper_bound': upper_bound if upper_bound <= 1e9 else 'infinity',
            'gap': gap,
            'objective_function_value': value
        }}
        
        results.update(get_results_function(model, config['additional_info']))

        result_file_path = results_directory_path.joinpath(f'{instance_file_name}_results.json')
        with open(result_file_path, 'w') as file:
            json.dump(results, file, indent=4)
        
        if is_verbose:
            print(f'Instance {instance_file_name} finished. Results are in \'{result_file_path}\'')
    
    if is_verbose:
        total_end_time = time.perf_counter()
        print(f'End checking process. Time elapsed: {total_end_time - total_start_time} seconds')
        print(f'Solved {instance_number} instances')