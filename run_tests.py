import argparse
from pathlib import Path
import yaml
import shutil
import json
import time
import pyomo.environ as pyo
from datetime import datetime

from checkers.master_instance_checker import check_master_instance
from checkers.subproblem_instance_checker import check_subproblem_instance
from checkers.master_results_checker import check_master_results
from checkers.subproblem_results_checker import check_subproblem_results
from checkers.final_results_checker import check_final_results

from analyzers.master_instance_analyzer import analyze_master_instance
from analyzers.subproblem_instance_analyzer import analyze_subproblem_instance
from analyzers.master_results_analyzer import analyze_master_results
from analyzers.subproblem_results_analyzer import analyze_subproblem_results
from analyzers.final_results_analyzer import analyze_final_results

from solvers.monolithic_solver import get_monolithic_model, get_results_from_monolithic_model
from solvers.master_solver import get_master_model, get_results_from_master_model
from solvers.subproblem_solver import get_subproblem_model, get_results_from_subproblem_model

from plotters.tools import plot_master_results
from plotters.tools import plot_subproblem_results


if __name__ != '__main__':
    exit(0)

parser = argparse.ArgumentParser(prog='Test instance groups', description='Solve and analyze instances')
parser.add_argument('-i', '--input', type=Path, help='Groups input directory path', required=True)
parser.add_argument('-o', '--output', type=Path, help='Groups output directory path', required=True)
parser.add_argument('-c', '--config', type=Path, help='YAML file configuration path', required=True)
args = parser.parse_args()

groups_input_directory_path = Path(args.input).resolve()
groups_output_directory_path = Path(args.output).resolve()
config_file_path = Path(args.config).resolve()

if not groups_input_directory_path.exists():
    raise ValueError(f'Group directory \'{groups_input_directory_path}\' does not exists')
elif not groups_input_directory_path.is_dir():
    raise ValueError(f'Group \'{groups_input_directory_path}\' is not a directory')

if not config_file_path.exists():
    raise FileNotFoundError(f'Configuration file \'{config_file_path}\' does not exists.')
if not config_file_path.is_file() or config_file_path.is_dir():
    raise ValueError(f'Configuration file \'{config_file_path}\' is not a file')
if config_file_path.suffix != '.yaml':
    raise ValueError(f'Configuration file \'{config_file_path}\' is not a YAML file')

if not groups_output_directory_path.exists():
    groups_output_directory_path.mkdir()

with open(config_file_path, 'r') as file:
    configs = yaml.load(file, yaml.Loader)

for config in configs:

    for group_directory_path in groups_input_directory_path.iterdir():
        if not group_directory_path.is_dir():
            continue

        group_name = group_directory_path.name
        group_input_directory_path = group_directory_path.joinpath('input')

        new_group_directory_path = groups_output_directory_path.joinpath(f'{group_name}_{config['name']}')
        if new_group_directory_path.exists():
            shutil.rmtree(new_group_directory_path)
        new_group_directory_path.mkdir()

        input_directory_path = new_group_directory_path.joinpath('input')
        input_directory_path.mkdir()

        if config['save_results']:
            results_directory_path = new_group_directory_path.joinpath('results')
            if results_directory_path.exists():
                shutil.rmtree(results_directory_path)
            results_directory_path.mkdir()

        if config['solver_config']['keep_logs']:
            logs_directory_path = new_group_directory_path.joinpath('logs')
            if logs_directory_path.exists():
                shutil.rmtree(logs_directory_path)
            logs_directory_path.mkdir()
        
        if config['analyze_instance'] or config['analyze_results']:
            analysis_directory_path = new_group_directory_path.joinpath('analysis')
            if analysis_directory_path.exists():
                shutil.rmtree(analysis_directory_path)
            analysis_directory_path.mkdir()

        if config['plot_results']:
            plots_directory_path = new_group_directory_path.joinpath('plots')
            if plots_directory_path.exists():
                shutil.rmtree(plots_directory_path)
            plots_directory_path.mkdir()
            
        for instance_file_path in group_input_directory_path.iterdir():
            
            with open(instance_file_path, 'r') as file:
                instance = json.load(file)
            
            new_instance_file_path = input_directory_path.joinpath(instance_file_path.name)
            with open(new_instance_file_path, 'w') as file:
                json.dump(instance, file, indent=4)
            
            if config['check_instance']:
                if config['checks_throw_exceptions']:
                    if config['mode'] == 'subproblem':
                        check_subproblem_instance(instance)
                    else:
                        check_master_instance(instance)
                else:
                    try:
                        if config['mode'] == 'subproblem':
                            check_subproblem_instance(instance)
                        else:
                            check_master_instance(instance)
                    except Exception as exception:
                        print(exception)
            
            config_file_path = new_group_directory_path.joinpath('config.yaml')
            with open(config_file_path, 'w') as file:
                yaml.dump(config, file, default_flow_style=False, sort_keys=False)

            if config['analyze_instance']:
                if config['mode'] == 'subproblem':
                    instance_analysis = analyze_subproblem_instance(instance, new_instance_file_path)
                else:
                    instance_analysis = analyze_master_instance(instance, new_instance_file_path)
                
                instance_analysis_file_path = analysis_directory_path.joinpath('instance_analysis.json')
                with open(instance_analysis_file_path, 'w') as file:
                    json.dump(instance_analysis, file, indent=4)

            print(f'Solving instance \'{instance_file_path}\' with configuration from \'{config_file_path}\'')
            total_start_time = time.perf_counter()

            if config['print_time_taken_by_model_creation']:
                print(f'Start model creation')
            model_creation_start_time = time.perf_counter()

            if config['mode'] == 'monolithic':
                model = get_monolithic_model(instance, config['solver_config'])
            elif config['mode'] == 'master':
                model = get_master_model(instance, config['solver_config'])
            elif config['mode'] == 'subproblem':
                model = get_subproblem_model(instance, config['solver_config'])

            model_creation_end_time = time.perf_counter()
            if config['print_time_taken_by_model_creation']:
                print(f'End model creation. Took {model_creation_end_time - model_creation_start_time} seconds.')

            opt = pyo.SolverFactory(config['solver_config']['solver'])

            if 'time_limit' in config['solver_config']:
                if config['solver_config']['solver'] == 'glpk':
                    opt.options['tmlim'] = config['solver_config']['time_limit']
                elif config['solver_config']['solver'] == 'gurobi':
                    opt.options['TimeLimit'] = config['solver_config']['time_limit']
            if 'max_memory' in config['solver_config']:
                opt.options['SoftMemLimit'] = config['solver_config']['max_memory']

            if config['print_time_taken_by_solver']:
                print(f'Start solving process')
            solving_start_time = time.perf_counter()
            
            if config['solver_config']['keep_logs']:
                log_file_path = logs_directory_path.joinpath(f'{instance_file_path.stem}_log.log')
                model_results = opt.solve(model, tee=config['print_solver_output'], logfile=log_file_path)
            else:
                model_results = opt.solve(model, tee=config['print_solver_output'])
            
            solving_end_time = time.perf_counter()
            if config['print_time_taken_by_solver']:
                print(f'End solving process. Took {solving_end_time - solving_start_time} seconds.')

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

            if config['mode'] == 'monolithic':
                results.update(get_results_from_monolithic_model(model, config['solver_config']['additional_info']))
            elif config['mode'] == 'master':
                results.update(get_results_from_master_model(model, config['solver_config']['additional_info']))
            elif config['mode'] == 'subproblem':
                results.update(get_results_from_subproblem_model(model, config['solver_config']['additional_info']))

            if config['save_results']:
                results_file_path = results_directory_path.joinpath(f'{instance_file_path.stem}_results.json')
                with open(results_file_path, 'w') as file:
                    json.dump(results, file, indent=4)
            
            if config['check_results']:
                if config['checks_throw_exceptions']:
                    if config['mode'] == 'monolithic':
                        check_final_results(instance, results)
                    elif config['mode'] == 'master':
                        check_master_results(instance, results)
                    elif config['mode'] == 'subproblem':
                        check_subproblem_results(instance, results)
                else:
                    try:
                        if config['mode'] == 'monolithic':
                            check_final_results(instance, results)
                        elif config['mode'] == 'master':
                            check_master_results(instance, results)
                        elif config['mode'] == 'subproblem':
                            check_subproblem_results(instance, results)
                    except Exception as exception:
                        print(exception)

            if config['analyze_results']:
                if config['mode'] == 'monolithic':
                    results_analysis = analyze_final_results(instance, results, instance_file_path)
                elif config['mode'] == 'master':
                    results_analysis = analyze_master_results(instance, results, instance_file_path)
                elif config['mode'] == 'subproblem':
                    results_analysis = analyze_subproblem_results(instance, results, instance_file_path)
                results_analysis_file_name = analysis_directory_path.joinpath(f'{instance_file_path.stem}_results_analysis.json')
                with open(results_analysis_file_name, 'w') as file:
                    json.dump(results_analysis, file, indent=4)

            if config['plot_results']:
                plot_file_name = plots_directory_path.joinpath(f'{instance_file_path.stem}_results_plot.png')
                if config['mode'] == 'monolithic':
                    plot_master_results(instance, results, plot_file_name)
                elif config['mode'] == 'master':
                    plot_master_results(instance, results, plot_file_name)
                elif config['mode'] == 'subproblem':
                    plot_subproblem_results(instance, results, plot_file_name)