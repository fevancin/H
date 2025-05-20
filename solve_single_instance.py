from datetime import datetime
from pathlib import Path
import argparse
import json
import time
import yaml
import shutil
import pyomo.environ as pyo

from checkers.master_instance_checker import check_master_instance
from checkers.master_results_checker import check_master_results
from checkers.subproblem_instance_checker import check_subproblem_instance
from checkers.subproblem_results_checker import check_subproblem_results
from checkers.final_results_checker import check_final_results

from solvers.master_solver import get_master_model, get_results_from_master_model
from solvers.subproblem_solver import get_subproblem_model, get_results_from_subproblem_model

from cores.compute_cores import compute_dumb_cores, compute_basic_cores, compute_reduced_cores, aggregate_and_remove_duplicate_cores
from cores.compute_cores import add_cores_constraint_class_to_master_model, add_cores_constraints_to_master_model
from cores.expand_core_days import compute_expanded_days, expand_core_days, remove_core_days_without_exact_requests
from cores.expand_core_patients_services import get_max_possible_master_requests, expand_core_patients_services

from plotters.tools import plot_master_results
from plotters.tools import plot_subproblem_results

from analyzers.tools import get_master_results_value, get_subproblem_results_value
from analyzers.master_instance_analyzer import analyze_master_instance
from analyzers.master_results_analyzer import analyze_master_results
from analyzers.subproblem_instance_analyzer import analyze_subproblem_instance
from analyzers.subproblem_results_analyzer import analyze_subproblem_results
from analyzers.final_results_analyzer import analyze_final_results


def compute_subproblem_instance_from_master(master_instance, master_results, day_name):
    
    patients = {}
    if day_name not in master_results['scheduled']:
        return None
    for schedule_item in master_results['scheduled'][day_name]:
        patient_name = schedule_item['patient']
        service_name = schedule_item['service']
        if patient_name not in patients:
            patients[patient_name] = {
                'priority': master_instance['patients'][patient_name]['priority'],
                'requests': set()
            }
        patients[patient_name]['requests'].add(service_name)
    
    for patient in patients.values():
        patient['requests'] = sorted(patient['requests'])
    
    return {
        'patients': patients,
        'day': master_instance['days'][day_name],
        'services': master_instance['services']
    }


def compose_final_results(master_instance, master_results, all_subproblem_results):

    max_day_index = len(master_instance['days']) - 1

    all_scheduled_results = {}
    for day_name, subproblem_results in all_subproblem_results.items():
        all_scheduled_results[day_name] = subproblem_results['scheduled']
    
    final_results = {
        'info': master_results['info'],
        'scheduled': all_scheduled_results,
        'rejected': master_results['rejected']
    }

    for day_name, subproblem_results in all_subproblem_results.items():
        for rejected_request in subproblem_results['rejected']:
            
            patient_name = rejected_request['patient']
            service_name = rejected_request['service']

            windows_containing_rejected_request = []
            for protocol in master_instance['patients'][patient_name]['protocols'].values():
                for protocol_service in protocol['protocol_services']:
                    
                    if protocol_service['service'] != service_name:
                        continue
                    
                    start = protocol_service['start'] + protocol['initial_shift']
                    tolerance = protocol_service['tolerance']
                    frequency = protocol_service['frequency']
                    times = protocol_service['times']


                    if times == 1:
                        
                        window_start = start - tolerance
                        window_end = start + tolerance

                        if window_start < 0:
                            window_start = 0
                        if window_end > max_day_index:
                            window_end = max_day_index
                        
                        if int(day_name) >= window_start and int(day_name) <= window_end:
                            windows_containing_rejected_request.append([window_start, window_end])
                        
                        continue

                    for central_day in range(start, start + frequency * times, frequency):
                        
                        window_start = central_day - tolerance
                        window_end = central_day + tolerance

                        if window_start < 0:
                            window_start = 0
                        if window_end > max_day_index:
                            window_end = max_day_index
                        
                        if int(day_name) >= window_start and int(day_name) <= window_end:
                            windows_containing_rejected_request.append([window_start, window_end])

            for window in windows_containing_rejected_request:
                final_results['rejected'].append({
                    'patient': patient_name,
                    'service': service_name,
                    'window': [window[0], window[1]]
                })

    unique_rejected = []
    for rejected_1 in final_results['rejected']:
        already_present = False
        for rejected_2 in unique_rejected:
            if rejected_1['patient'] == rejected_2['patient'] and rejected_1['service'] == rejected_2['service'] and rejected_1['window'][0] == rejected_2['window'][0] and rejected_1['window'][1] == rejected_2['window'][1]:
                already_present = True
                break
        if not already_present:
            unique_rejected.append(rejected_1)
    final_results['rejected'] = unique_rejected

    true_results_objective_function_value = 0
    true_results_lower_bound = 0
    true_results_upper_bound = 0

    for subproblem_results in all_subproblem_results.values():

        true_results_objective_function_value += subproblem_results['info']['objective_function_value']
        true_results_lower_bound += subproblem_results['info']['lower_bound']
        true_results_upper_bound += subproblem_results['info']['upper_bound']
        
        final_results['info']['model_creation_time'] += subproblem_results['info']['model_creation_time']
        final_results['info']['model_solving_time'] += subproblem_results['info']['model_solving_time']
        final_results['info']['solver_internal_time'] += subproblem_results['info']['solver_internal_time']
    
    final_results['info']['objective_function_value'] = true_results_objective_function_value
    final_results['info']['solution_value'] = true_results_objective_function_value
    final_results['info']['lower_bound'] = true_results_lower_bound
    final_results['info']['upper_bound'] = true_results_upper_bound
    final_results['info']['gap'] = (true_results_upper_bound - true_results_lower_bound) / true_results_upper_bound

    return final_results


def main(group_directory_path, config, config_file_path):

    input_directory_path = group_directory_path.joinpath('input')
    if not input_directory_path.exists():
        raise ValueError(f'Input directory \'{input_directory_path}\' does not exists')
    elif not input_directory_path.is_dir():
        raise ValueError(f'Input \'{input_directory_path}\' is not a directory')

    master_instance_file_path = None
    for file_path in input_directory_path.iterdir():

        if not file_path.is_file() or file_path.suffix != '.json':
            continue

        master_instance_file_path = file_path
        break

    if master_instance_file_path is None:
        print(f'Master instance not found in directory \'{input_directory_path}\'')
        exit(0)

    with open(master_instance_file_path, 'r') as file:
        master_instance = json.load(file)

    if config['check_master_instance']:
        if config['checks_throw_exceptions']:
            check_master_instance(master_instance)
        else:
            try:
                check_master_instance(master_instance)
            except Exception as exception:
                print(exception)

    shutil.rmtree(input_directory_path)
    input_directory_path.mkdir()

    with open(master_instance_file_path, 'w') as file:
        json.dump(master_instance, file, indent=4)

    if config['save_master_results'] or config['save_subproblem_results'] or config['save_final_results']:
        results_directory_path = group_directory_path.joinpath('results')
        if results_directory_path.exists():
            shutil.rmtree(results_directory_path)
        results_directory_path.mkdir()

    if config['use_cores']:
        cores_directory_path = group_directory_path.joinpath('cores')
        if cores_directory_path.exists():
            shutil.rmtree(cores_directory_path)
        cores_directory_path.mkdir()

    if config['master_config']['keep_logs'] or config['subproblem_config']['keep_logs']:
        logs_directory_path = group_directory_path.joinpath('logs')
        if logs_directory_path.exists():
            shutil.rmtree(logs_directory_path)
        logs_directory_path.mkdir()

    if config['analyze_master_instance'] or config['analyze_master_results'] or config['analyze_subproblem_instance'] or config['analyze_subproblem_results'] or config['analyze_final_results']:
        analysis_directory_path = group_directory_path.joinpath('analysis')
        if analysis_directory_path.exists():
            shutil.rmtree(analysis_directory_path)
        analysis_directory_path.mkdir()

    if config['plot_master_results'] or config['plot_subproblem_results'] or config['plot_final_results']:
        plots_directory_path = group_directory_path.joinpath('plots')
        if plots_directory_path.exists():
            shutil.rmtree(plots_directory_path)
        plots_directory_path.mkdir()

    solver_config_file_path = group_directory_path.joinpath('main_config.yaml')
    with open(solver_config_file_path, 'w') as file:
        yaml.dump(config, file, default_flow_style=False, sort_keys=False)

    if config['analyze_master_instance']:
        master_instance_analysis = analyze_master_instance(master_instance, master_instance_file_path)
        master_instance_analysis_file_path = analysis_directory_path.joinpath('master_instance_analysis.json')
        with open(master_instance_analysis_file_path, 'w') as file:
            json.dump(master_instance_analysis, file, indent=4)

    print(f'Solving instance \'{master_instance_file_path}\' with configuration from \'{config_file_path}\'')
    total_start_time = time.perf_counter()

    if config['use_cores']:
        max_possible_master_requests = get_max_possible_master_requests(master_instance)

        if config['expand_core_days']:
            expanded_days = compute_expanded_days(master_instance)
            if config['save_expanded_days']:
                expanded_days_file_path = cores_directory_path.joinpath('expanded_days.json')
                with open(expanded_days_file_path, 'w') as file:
                    json.dump(expanded_days, file, indent=4)

    if config['print_time_taken_by_master_creation']:
        print(f'Start master model creation')
    master_model_creation_start_time = time.perf_counter()

    master_model = get_master_model(master_instance, config['master_config']['additional_info'])

    if config['use_cores']:
        add_cores_constraint_class_to_master_model(master_model)

    master_model_creation_end_time = time.perf_counter()
    if config['print_time_taken_by_master_creation']:
        print(f'End master model creation. Took {master_model_creation_end_time - master_model_creation_start_time} seconds.')

    master_opt = pyo.SolverFactory(config['master_config']['solver'])

    if 'time_limit' in config['master_config']:
        if config['master_config']['solver'] == 'glpk':
            master_opt.options['tmlim'] = config['master_config']['time_limit']
        elif config['master_config']['solver'] == 'gurobi':
            master_opt.options['TimeLimit'] = config['master_config']['time_limit']
    if 'max_memory' in config['master_config']:
        master_opt.options['SoftMemLimit'] = config['master_config']['max_memory']

    iteration_index = 0
    if config['use_cores']:
        max_iteration_number = config['max_iteration_number']
    else:
        max_iteration_number = 1

    all_iterations_cores = []

    while iteration_index < max_iteration_number:

        if config['save_subproblem_instance']:
            iteration_input_directory_path = input_directory_path.joinpath(f'iter_{iteration_index}')
            iteration_input_directory_path.mkdir()

        if config['save_master_results'] or config['save_subproblem_results'] or config['save_final_results']:
            iteration_results_directory_path = results_directory_path.joinpath(f'iter_{iteration_index}')
            iteration_results_directory_path.mkdir()

        if config['use_cores'] and config['save_cores']:
            iteration_cores_directory_path = cores_directory_path.joinpath(f'iter_{iteration_index}')
            iteration_cores_directory_path.mkdir()

        if config['master_config']['keep_logs'] or config['subproblem_config']['keep_logs']:
            iteration_logs_directory_path = logs_directory_path.joinpath(f'iter_{iteration_index}')
            iteration_logs_directory_path.mkdir()

        if config['analyze_master_results'] or config['analyze_subproblem_instance'] or config['analyze_subproblem_results'] or config['analyze_final_results']:
            iteration_analysis_directory_path = analysis_directory_path.joinpath(f'iter_{iteration_index}')
            iteration_analysis_directory_path.mkdir()
        
        if config['plot_master_results'] or config['plot_subproblem_results'] or config['plot_final_results']:
            iteration_plots_directory_path = plots_directory_path.joinpath(f'iter_{iteration_index}')
            iteration_plots_directory_path.mkdir()
        
        if config['print_time_taken_by_master_solver']:
            print(f'[iter {iteration_index}] Start master solving process')
        master_solving_start_time = time.perf_counter()
        
        if config['master_config']['keep_logs']:
            log_file_path = iteration_logs_directory_path.joinpath('master_log.log')
            master_model_results = master_opt.solve(master_model, tee=config['print_master_solver_output'], warmstart=config['warm_start_master'], logfile=log_file_path)
        else:
            master_model_results = master_opt.solve(master_model, tee=config['print_master_solver_output'], warmstart=config['warm_start_master'])
        
        master_solving_end_time = time.perf_counter()
        if config['print_time_taken_by_master_solver']:
            print(f'[iter {iteration_index}] End master solving process. Took {master_solving_end_time - master_solving_start_time} seconds.')

        master_model.solutions.store_to(master_model_results)
        solution = master_model_results.solution[0]
        lower_bound = float(master_model_results['problem'][0]['Lower bound'])
        upper_bound = float(master_model_results['problem'][0]['Upper bound'])
        gap = float(solution['gap'])
        if gap <= 1e-5 and lower_bound != upper_bound:
            gap = (upper_bound - lower_bound) / upper_bound
        value = float(solution['objective']['total_satisfied_service_durations']['Value'])

        master_results = {'info': {
            'timestamp': datetime.now().strftime('%a_%d_%m_%Y_%H_%M_%S'),
            'model_creation_time': master_model_creation_end_time - master_model_creation_start_time,
            'model_solving_time': master_solving_end_time - master_solving_start_time,
            'solver_internal_time': float(master_model_results.solver.time),
            'status': str(master_model_results.solver.status),
            'termination_condition': str(master_model_results.solver.termination_condition),
            'lower_bound': lower_bound,
            'upper_bound': upper_bound if upper_bound <= 1e9 else 'infinity',
            'gap': gap,
            'objective_function_value': value
        }}

        master_results.update(get_results_from_master_model(master_model, config['master_config']['additional_info']))

        if config['save_master_results']:
            master_results_file_path = iteration_results_directory_path.joinpath('master_results.json')
            with open(master_results_file_path, 'w') as file:
                json.dump(master_results, file, indent=4)
        
        if config['check_master_results']:
            if config['checks_throw_exceptions']:
                check_master_results(master_instance, master_results)
            else:
                try:
                    check_master_results(master_instance, master_results)
                except Exception as exception:
                    print(exception)

        if config['analyze_master_results']:
            master_results_analysis = analyze_master_results(master_instance, master_results, master_instance_file_path)
            master_results_analysis_file_name = iteration_analysis_directory_path.joinpath('master_results_analysis.json')
            with open(master_results_analysis_file_name, 'w') as file:
                json.dump(master_results_analysis, file, indent=4)

        if config['plot_master_results']:
            master_plot_file_name = iteration_plots_directory_path.joinpath(f'master_results_plot.png')
            plot_master_results(master_instance, master_results, master_plot_file_name)

        all_subproblem_results = {}
        for day_name in master_results['scheduled'].keys():
            
            subproblem_instance = compute_subproblem_instance_from_master(master_instance, master_results, day_name)
            
            if config['save_subproblem_instance'] or config['analyze_subproblem_results'] or config['analyze_subproblem_instance']:
                subproblem_instance_file_path = iteration_input_directory_path.joinpath(f'subproblem_day_{day_name}.json')
            
            if config['save_subproblem_instance']:
                with open(subproblem_instance_file_path, 'w') as file:
                    json.dump(subproblem_instance, file, indent=4)
            
            if config['check_subproblem_instances']:
                if config['checks_throw_exceptions']:
                    check_subproblem_instance(subproblem_instance)
                else:
                    try:
                        check_subproblem_instance(subproblem_instance)
                    except Exception as exception:
                        print(exception)

            if config['analyze_subproblem_instance']:
                subproblem_instance_analysis = analyze_subproblem_instance(subproblem_instance, subproblem_instance_file_path)
                subproblem_instance_analysis_file_name = iteration_analysis_directory_path.joinpath('subproblem_instance_analysis.json')
                with open(subproblem_instance_analysis_file_name, 'w') as file:
                    json.dump(subproblem_instance_analysis, file, indent=4)

            if config['print_time_taken_by_subproblem_creation']:
                print(f'[iter {iteration_index}] Start subproblem model creation for day \'{day_name}\'')
            subproblem_model_creation_start_time = time.perf_counter()

            subproblem_model = get_subproblem_model(subproblem_instance, config['subproblem_config']['additional_info'])

            subproblem_model_creation_end_time = time.perf_counter()
            if config['print_time_taken_by_subproblem_creation']:
                print(f'[iter {iteration_index}] End subproblem model creation for day \'{day_name}\'. Took {subproblem_model_creation_end_time - subproblem_model_creation_start_time} seconds.')

            subproblem_opt = pyo.SolverFactory(config['subproblem_config']['solver'])

            if 'time_limit' in config['subproblem_config']:
                if config['subproblem_config']['solver'] == 'glpk':
                    subproblem_opt.options['tmlim'] = config['subproblem_config']['time_limit']
                elif config['subproblem_config']['solver'] == 'gurobi':
                    subproblem_opt.options['TimeLimit'] = config['subproblem_config']['time_limit']
            if 'max_memory' in config['subproblem_config']:
                subproblem_opt.options['SoftMemLimit'] = config['subproblem_config']['max_memory']

            if config['print_time_taken_by_subproblem_solver']:
                print(f'[iter {iteration_index}] Start subproblem solving process for day \'{day_name}\'')
            subproblem_solving_start_time = time.perf_counter()
            
            if config['subproblem_config']['keep_logs']:
                log_file_path = iteration_logs_directory_path.joinpath(f'subproblem_day_{day_name}_log.log')
                subproblem_model_results = subproblem_opt.solve(subproblem_model, tee=config['print_subproblem_solver_output'], logfile=log_file_path)
            else:
                subproblem_model_results = subproblem_opt.solve(subproblem_model, tee=config['print_subproblem_solver_output'])
            
            subproblem_solving_end_time = time.perf_counter()
            if config['print_time_taken_by_subproblem_solver']:
                print(f'[iter {iteration_index}] End subproblem solving process for day \'{day_name}\'. Took {subproblem_solving_end_time - subproblem_solving_start_time} seconds.')

            subproblem_model.solutions.store_to(subproblem_model_results)
            solution = subproblem_model_results.solution[0]
            lower_bound = float(subproblem_model_results['problem'][0]['Lower bound'])
            upper_bound = float(subproblem_model_results['problem'][0]['Upper bound'])
            gap = float(solution['gap'])
            if gap <= 1e-5 and lower_bound != upper_bound:
                gap = (upper_bound - lower_bound) / upper_bound
            value = float(solution['objective']['total_satisfied_service_durations']['Value'])

            subproblem_results = {'info': {
                'timestamp': datetime.now().strftime('%a_%d_%m_%Y_%H_%M_%S'),
                'model_creation_time': subproblem_model_creation_end_time - subproblem_model_creation_start_time,
                'model_solving_time': subproblem_solving_end_time - subproblem_solving_start_time,
                'solver_internal_time': float(subproblem_model_results.solver.time),
                'status': str(subproblem_model_results.solver.status),
                'termination_condition': str(subproblem_model_results.solver.termination_condition),
                'lower_bound': lower_bound,
                'upper_bound': upper_bound if upper_bound <= 1e9 else 'infinity',
                'gap': gap,
                'objective_function_value': value
            }}
        
            subproblem_results.update(get_results_from_subproblem_model(subproblem_model, config['subproblem_config']['additional_info']))

            if config['save_subproblem_results']:
                subproblem_results_file_path = iteration_results_directory_path.joinpath(f'subproblem_day_{day_name}_results.json')
                with open(subproblem_results_file_path, 'w') as file:
                    json.dump(subproblem_results, file, indent=4)
            
            if config['check_subproblem_results']:
                if config['checks_throw_exceptions']:
                    check_subproblem_results(subproblem_instance, subproblem_results)
                else:
                    try:
                        check_subproblem_results(subproblem_instance, subproblem_results)
                    except Exception as exception:
                        print(exception)

            if config['analyze_subproblem_results']:
                subproblem_results_analysis = analyze_subproblem_results(subproblem_instance, subproblem_results, subproblem_instance_file_path)
                subproblem_results_analysis_file_name = iteration_analysis_directory_path.joinpath('subproblem_results_analysis.json')
                with open(subproblem_results_analysis_file_name, 'w') as file:
                    json.dump(subproblem_results_analysis, file, indent=4)

            if config['plot_subproblem_results']:
                subproblem_plot_file_name = iteration_plots_directory_path.joinpath(f'subproblem_day_{day_name}_results_plot.png')
                plot_subproblem_results(subproblem_instance, subproblem_results, subproblem_plot_file_name)

            all_subproblem_results[day_name] = subproblem_results
        
        final_results = compose_final_results(master_instance, master_results, all_subproblem_results)

        if config['save_final_results']:
            final_results_file_path = iteration_results_directory_path.joinpath('final_results.json')
            with open(final_results_file_path, 'w') as file:
                json.dump(final_results, file, indent=4)

        if config['check_final_results']:
            if config['checks_throw_exceptions']:
                check_final_results(master_instance, final_results)
            else:
                try:
                    check_final_results(master_instance, final_results)
                except Exception as exception:
                    print(exception)

        if config['analyze_final_results']:
            final_results_analysis = analyze_final_results(master_instance, final_results, master_instance_file_path)
            final_results_analysis_file_name = iteration_analysis_directory_path.joinpath('final_results_analysis.json')
            with open(final_results_analysis_file_name, 'w') as file:
                json.dump(final_results_analysis, file, indent=4)

        if config['plot_final_results']:
            final_results_plot_file_name = iteration_plots_directory_path.joinpath(f'final_results_plot.png')
            plot_master_results(master_instance, final_results, final_results_plot_file_name)

        are_all_days_completely_solved = True
        for day_name, day_results in all_subproblem_results.items():
            if len(day_results['rejected']) > 0:
                are_all_days_completely_solved = False
                print(f'[iter {iteration_index}] Day {day_name} is not completely satisfied.')
        
        if are_all_days_completely_solved:
            print(f'[iter {iteration_index}] All days are solved: exiting iteration cycle.') 
            break

        if config['early_stop_percentage_between_master_and_subproblem'] > 0.0:
            
            master_results_value = get_master_results_value(master_instance, master_results)
            
            subproblems_results_value = 0
            for day_name, day_results in all_subproblem_results.items():
                subproblems_results_value += get_subproblem_results_value(master_instance, final_results, day_name)
            
            min_difference = config['early_stop_percentage_between_master_and_subproblem']
            
            if (master_results_value - subproblems_results_value) / master_results_value <= min_difference:
                print(f'[iter {iteration_index}] Master and subproblems reached the minimum value difference ({min_difference}%): exiting iteration cycle.') 
                break

        if config['use_cores']:
            
            if config['core_type'] == 'dumb':
                current_iteration_cores = compute_dumb_cores(all_subproblem_results)
            elif config['core_type'] == 'basic':
                current_iteration_cores = compute_basic_cores(all_subproblem_results)
            elif config['core_type'] == 'reduced':
                current_iteration_cores = compute_reduced_cores(all_subproblem_results, master_instance)

            if config['print_core_info'] and (config['expand_core_days'] or config['expand_core_patients'] or config['expand_core_services']):
                print(f'[iter {iteration_index}] {len(current_iteration_cores)} new cores are found.')

            if config['expand_core_days']:
                expand_core_days(master_instance, current_iteration_cores, expanded_days)

            if config['expand_core_patients'] or config['expand_core_services']:
                current_iteration_cores.extend(expand_core_patients_services(current_iteration_cores, max_possible_master_requests, master_instance, config['expand_core_patients'], config['expand_core_services'], config['max_expansions_per_core']))
                if config['print_core_info']:
                    print(f'[iter {iteration_index}] {len(current_iteration_cores)} total new cores are present after expansion.')
            
            if config['expand_core_days']:
                current_iteration_cores = remove_core_days_without_exact_requests(current_iteration_cores, max_possible_master_requests)
                if config['print_core_info']:
                    print(f'[iter {iteration_index}] {len(current_iteration_cores)} new cores are remaining after removing impossible ones.')

            current_iteration_cores, all_iterations_cores = aggregate_and_remove_duplicate_cores(current_iteration_cores, all_iterations_cores)
            if config['print_core_info']:
                print(f'[iter {iteration_index}] {len(current_iteration_cores)} cores remaining after removing duplicates.')
                
            if len(current_iteration_cores) > 0:
                add_cores_constraints_to_master_model(master_model, current_iteration_cores)

            if config['save_cores']:
                cores_file_path = iteration_cores_directory_path.joinpath('cores.json')
                with open(cores_file_path, 'w') as file:
                    json.dump(current_iteration_cores, file, indent=4)
            
            if config['print_core_info']:
                print(f'[iter {iteration_index}] Added {len(current_iteration_cores)} new cores to the master problem.')

        print(f'[iter {iteration_index}] Iteration {iteration_index} finished.')
        
        iteration_index += 1

    if config['use_cores']:
        all_iterations_cores_file_path = cores_directory_path.joinpath('all_iterations_cores.json')
        with open(all_iterations_cores_file_path, 'w') as file:
            json.dump(all_iterations_cores, file, indent=4)

    total_end_time = time.perf_counter()
    print(f'End total solving process. Time elapsed: {total_end_time - total_start_time} seconds')


if __name__ == '__main__':

    parser = argparse.ArgumentParser(prog='Main decomposition loop', description='Solve an instance with decomposition')
    parser.add_argument('-i', '--input', type=Path, help='Instance group directory path', required=True)
    parser.add_argument('-c', '--config', type=Path, help='YAML file configuration path', required=True)
    args = parser.parse_args()

    group_directory_path = Path(args.input).resolve()
    config_file_path = Path(args.config).resolve()

    if not group_directory_path.exists():
        raise ValueError(f'Group directory \'{group_directory_path}\' does not exists')
    elif not group_directory_path.is_dir():
        raise ValueError(f'Group \'{group_directory_path}\' is not a directory')

    if not config_file_path.exists():
        raise FileNotFoundError(f'Configuration file \'{config_file_path}\' does not exists.')
    if not config_file_path.is_file() or config_file_path.is_dir():
        raise ValueError(f'Configuration file \'{config_file_path}\' is not a file')
    if config_file_path.suffix != '.yaml':
        raise ValueError(f'Configuration file \'{config_file_path}\' is not a YAML file')

    with open(config_file_path, 'r') as file:
        config = yaml.load(file, yaml.Loader)

    main(group_directory_path, config, config_file_path)