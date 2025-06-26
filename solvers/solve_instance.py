from datetime import datetime
from pathlib import Path
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
from solvers.master_solver import add_objective_value_constraints
from solvers.subproblem_solver import get_subproblem_model, get_results_from_subproblem_model

from cores.compute_cores import compute_dumb_cores, compute_basic_cores, compute_reduced_cores, aggregate_and_remove_duplicate_cores
from cores.compute_cores import add_cores_constraint_class_to_master_model, add_cores_constraints_to_master_model
from cores.expand_core_days import compute_expanded_days, expand_core_days, remove_core_days_without_exact_requests
from cores.expand_core_patients_services import get_max_possible_master_requests, expand_core_patients_services

from analyzers.tools import get_master_results_value, get_subproblem_results_value
from analyzers.master_instance_analyzer import analyze_master_instance
from analyzers.master_results_analyzer import analyze_master_results
from analyzers.subproblem_instance_analyzer import analyze_subproblem_instance
from analyzers.subproblem_results_analyzer import analyze_subproblem_results
from analyzers.final_results_analyzer import analyze_final_results, get_final_results_value


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

    all_scheduled_results = {}
    for day_name, subproblem_results in all_subproblem_results.items():
        all_scheduled_results[day_name] = subproblem_results['scheduled']
    
    final_results = {
        'info': master_results['info'],
        'scheduled': all_scheduled_results,
        'rejected': master_results['rejected']
    }

    for day_name, subproblem_results in all_subproblem_results.items():
        day_index = int(day_name)
        for rejected_request in subproblem_results['rejected']:
            
            patient_name = rejected_request['patient']
            service_name = rejected_request['service']

            windows_containing_rejected_request = []
            for window in master_instance['patients'][patient_name]['requests'][service_name]:
                if window[0] <= day_index and window[1] >= day_index:
                    windows_containing_rejected_request.append([window[0], window[1]])
                        
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
    final_results['rejected'] = sorted(unique_rejected, key=lambda r: (r['patient'], r['service'], r['window'][0], r['window'][1]))

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


def solve_instance(master_instance, output_directory_path: Path, config: dict):

    if config['checks_throw_exceptions']:
        check_master_instance(master_instance)
    else:
        try:
            check_master_instance(master_instance)
        except Exception as exception:
            print(exception)
    
    if output_directory_path.exists():
        shutil.rmtree(output_directory_path)
    output_directory_path.mkdir()

    input_directory_path = output_directory_path.joinpath('input')
    input_directory_path.mkdir()

    results_directory_path = output_directory_path.joinpath('results')
    results_directory_path.mkdir(exist_ok=True)

    cores_directory_path = output_directory_path.joinpath('cores')
    cores_directory_path.mkdir(exist_ok=True)

    logs_directory_path = output_directory_path.joinpath('logs')
    logs_directory_path.mkdir(exist_ok=True)

    analysis_directory_path = output_directory_path.joinpath('analysis')
    analysis_directory_path.mkdir(exist_ok=True)

    master_instance_file_path = input_directory_path.joinpath('master_instance.json')
    with open(master_instance_file_path, 'w') as file:
        json.dump(master_instance, file, indent=4)

    solver_config_file_path = output_directory_path.joinpath('solver_config.yaml')
    with open(solver_config_file_path, 'w') as file:
        yaml.dump(config, file, default_flow_style=False, sort_keys=False)

    master_instance_analysis = analyze_master_instance(master_instance, master_instance_file_path)
    master_instance_analysis_file_path = analysis_directory_path.joinpath('master_instance_analysis.json')
    with open(master_instance_analysis_file_path, 'w') as file:
        json.dump(master_instance_analysis, file, indent=4)

    print(f'Solving instance \'{master_instance_file_path}\'')
    total_start_time = time.perf_counter()

    max_possible_master_requests = get_max_possible_master_requests(master_instance)

    if config['expand_core_days']:
        expanded_days = compute_expanded_days(master_instance)
        expanded_days_file_path = cores_directory_path.joinpath('expanded_days.json')
        with open(expanded_days_file_path, 'w') as file:
            json.dump(expanded_days, file, indent=4)

    print(f'Started master model creation... ', end='')
    master_model_creation_start_time = time.perf_counter()

    master_model = get_master_model(master_instance, config['additional_master_info'])

    add_cores_constraint_class_to_master_model(master_model)

    master_model_creation_end_time = time.perf_counter()
    print(f'ended ({round(master_model_creation_end_time - master_model_creation_start_time, 4)}s).')

    master_opt = pyo.SolverFactory(config['master_config']['solver'])

    if 'time_limit' in config['master_config']:
        if config['master_config']['solver'] == 'glpk':
            master_opt.options['tmlim'] = config['master_config']['time_limit']
        elif config['master_config']['solver'] == 'gurobi':
            master_opt.options['TimeLimit'] = config['master_config']['time_limit']
    if 'max_memory' in config['master_config']:
        master_opt.options['SoftMemLimit'] = config['master_config']['max_memory']

    iteration_index = 0
    max_iteration_number = config['max_iteration_number']

    all_iterations_cores = []

    best_final_results_file_path = results_directory_path.joinpath('best_final_results.json')
    best_final_results_value = None

    while iteration_index < max_iteration_number:

        iteration_input_directory_path = input_directory_path.joinpath(f'iter_{iteration_index}')
        iteration_input_directory_path.mkdir()

        iteration_results_directory_path = results_directory_path.joinpath(f'iter_{iteration_index}')
        iteration_results_directory_path.mkdir()

        iteration_cores_directory_path = cores_directory_path.joinpath(f'iter_{iteration_index}')
        iteration_cores_directory_path.mkdir()

        iteration_logs_directory_path = logs_directory_path.joinpath(f'iter_{iteration_index}')
        iteration_logs_directory_path.mkdir()

        iteration_analysis_directory_path = analysis_directory_path.joinpath(f'iter_{iteration_index}')
        iteration_analysis_directory_path.mkdir()
        
        print(f'[iter {iteration_index}] Starting master solving process... ', end='')
        master_solving_start_time = time.perf_counter()
        
        log_file_path = iteration_logs_directory_path.joinpath('master_log.log')
        master_model_results = master_opt.solve(master_model, tee=False, warmstart=config['warm_start_master'], logfile=log_file_path)

        master_solving_end_time = time.perf_counter()
        print(f'ended ({master_solving_end_time - master_solving_start_time}s).')

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

        master_results.update(get_results_from_master_model(master_model))

        master_results_file_path = iteration_results_directory_path.joinpath('master_results.json')
        with open(master_results_file_path, 'w') as file:
            json.dump(master_results, file, indent=4)
        
        if config['checks_throw_exceptions']:
            check_master_results(master_instance, master_results)
        else:
            try:
                check_master_results(master_instance, master_results)
            except Exception as exception:
                print(exception)

        master_results_analysis = analyze_master_results(master_instance, master_results, master_instance_file_path)
        master_results_analysis_file_name = iteration_analysis_directory_path.joinpath('master_results_analysis.json')
        with open(master_results_analysis_file_name, 'w') as file:
            json.dump(master_results_analysis, file, indent=4)

        all_subproblem_results = {}
        for day_name in master_results['scheduled'].keys():
            
            subproblem_instance = compute_subproblem_instance_from_master(master_instance, master_results, day_name)
            
            subproblem_instance_file_path = iteration_input_directory_path.joinpath(f'subproblem_day_{day_name}.json')
            
            with open(subproblem_instance_file_path, 'w') as file:
                json.dump(subproblem_instance, file, indent=4)
            
            if config['checks_throw_exceptions']:
                check_subproblem_instance(subproblem_instance)
            else:
                try:
                    check_subproblem_instance(subproblem_instance)
                except Exception as exception:
                    print(exception)

            subproblem_instance_analysis = analyze_subproblem_instance(subproblem_instance, subproblem_instance_file_path)
            subproblem_instance_analysis_file_name = iteration_analysis_directory_path.joinpath('subproblem_instance_analysis.json')
            with open(subproblem_instance_analysis_file_name, 'w') as file:
                json.dump(subproblem_instance_analysis, file, indent=4)

            print(f'[iter {iteration_index}] Starting subproblem model creation for day \'{day_name}\'... ', end='')
            subproblem_model_creation_start_time = time.perf_counter()

            subproblem_model = get_subproblem_model(subproblem_instance, config['additional_subproblem_info'])

            subproblem_model_creation_end_time = time.perf_counter()
            print(f'ended ({round(subproblem_model_creation_end_time - subproblem_model_creation_start_time, 4)}s).')

            subproblem_opt = pyo.SolverFactory(config['subproblem_config']['solver'])

            if 'time_limit' in config['subproblem_config']:
                if config['subproblem_config']['solver'] == 'glpk':
                    subproblem_opt.options['tmlim'] = config['subproblem_config']['time_limit']
                elif config['subproblem_config']['solver'] == 'gurobi':
                    subproblem_opt.options['TimeLimit'] = config['subproblem_config']['time_limit']
            if 'max_memory' in config['subproblem_config']:
                subproblem_opt.options['SoftMemLimit'] = config['subproblem_config']['max_memory']

            print(f'[iter {iteration_index}] Starting subproblem solving process for day \'{day_name}\'... ', end='')
            subproblem_solving_start_time = time.perf_counter()
            
            log_file_path = iteration_logs_directory_path.joinpath(f'subproblem_day_{day_name}_log.log')
            subproblem_model_results = subproblem_opt.solve(subproblem_model, tee=False, logfile=log_file_path)

            subproblem_solving_end_time = time.perf_counter()
            print(f'ended ({round(subproblem_solving_end_time - subproblem_solving_start_time, 4)}s).')

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
        
            subproblem_results.update(get_results_from_subproblem_model(subproblem_model))

            subproblem_results_file_path = iteration_results_directory_path.joinpath(f'subproblem_day_{day_name}_results.json')
            with open(subproblem_results_file_path, 'w') as file:
                json.dump(subproblem_results, file, indent=4)
        
            if config['checks_throw_exceptions']:
                check_subproblem_results(subproblem_instance, subproblem_results)
            else:
                try:
                    check_subproblem_results(subproblem_instance, subproblem_results)
                except Exception as exception:
                    print(exception)

            subproblem_results_analysis = analyze_subproblem_results(subproblem_instance, subproblem_results, subproblem_instance_file_path)
            subproblem_results_analysis_file_name = iteration_analysis_directory_path.joinpath('subproblem_results_analysis.json')
            with open(subproblem_results_analysis_file_name, 'w') as file:
                json.dump(subproblem_results_analysis, file, indent=4)

            all_subproblem_results[day_name] = subproblem_results
        
        final_results = compose_final_results(master_instance, master_results, all_subproblem_results)

        final_results_file_path = iteration_results_directory_path.joinpath('final_results.json')
        with open(final_results_file_path, 'w') as file:
            json.dump(final_results, file, indent=4)
        
        final_results_value = get_final_results_value(master_instance, final_results)
        if best_final_results_value is None or final_results_value > best_final_results_value:
            best_final_results_value = final_results_value
            with open(best_final_results_file_path, 'w') as file:
                json.dump(final_results, file, indent=4)

        if config['checks_throw_exceptions']:
            check_final_results(master_instance, final_results)
        else:
            try:
                check_final_results(master_instance, final_results)
            except Exception as exception:
                print(exception)

        final_results_analysis = analyze_final_results(master_instance, final_results, master_instance_file_path)
        final_results_analysis_file_name = iteration_analysis_directory_path.joinpath('final_results_analysis.json')
        with open(final_results_analysis_file_name, 'w') as file:
            json.dump(final_results_analysis, file, indent=4)

        days_not_completely_solved = []
        for day_name, day_results in all_subproblem_results.items():
            if len(day_results['rejected']) > 0:
                days_not_completely_solved.append(day_name)
        
        if len(days_not_completely_solved) == 0:
            print(f'[iter {iteration_index}] All days are solved: exiting iteration cycle.') 
            break
        else:
            print(f'[iter {iteration_index}] Days [ ', end='')
            for day_name in days_not_completely_solved:
                print(f'{day_name} ', end='')
            print('] are not completely solved')

        if config['early_stop_percentage_between_master_and_subproblem'] > 0.0:
            
            master_results_value = get_master_results_value(master_instance, master_results)
            
            subproblems_results_value = 0
            for day_name, day_results in all_subproblem_results.items():
                subproblems_results_value += get_subproblem_results_value(master_instance, final_results, day_name)
            
            min_difference = config['early_stop_percentage_between_master_and_subproblem']
            
            if (master_results_value - subproblems_results_value) / master_results_value <= min_difference:
                print(f'[iter {iteration_index}] Master and subproblems reached the minimum value difference ({min_difference}%): exiting iteration cycle.') 
                break

        if 'use_objective_value_constraints' in config['additional_master_info']:
            add_objective_value_constraints(master_model, master_instance, all_subproblem_results, max_possible_master_requests)
            
        cores_analysis = {}

        # Calcola l'elenco di core a partire dalle richieste non schedulate:
        # > Core dumb: tutto quanto è richiesto in un dato giorno,
        # > Core basic: ogni singola richiesta non schedulata più tutte
        #   quelle schedulate,
        # > Core reduced: ogni singola richiesta non schedulata più tutte
        #   quelle schedulate che hanno paziente o unità di cura
        #   influenzate, anche a catena.
        if config['core_type'] == 'dumb':
            current_iteration_cores = compute_dumb_cores(all_subproblem_results)
        elif config['core_type'] == 'basic':
            current_iteration_cores = compute_basic_cores(all_subproblem_results)
        elif config['core_type'] == 'reduced':
            current_iteration_cores = compute_reduced_cores(all_subproblem_results, master_instance)

        if  config['expand_core_days'] or config['expand_core_patients'] or config['expand_core_services']:
            print(f'[iter {iteration_index}] {len(current_iteration_cores)} new cores are found.')
        
        core_number = len(current_iteration_cores)

        # Numero di core prima dell'eventuale espansione
        cores_analysis['core_number_pre_expansion'] = core_number
        
        day_names = set()
        for core in current_iteration_cores:
            day_names.update(core['days'])
        
        # Numero di giorni che hanno almeno un core
        cores_analysis['day_with_cores_pre_expansion'] = len(day_names)

        total_core_components_number = 0
        for core in current_iteration_cores:
            total_core_components_number += len(core['components'])
        
        # Numero medio di componenti dei core
        cores_analysis['average_core_size_pre_expansion'] = total_core_components_number / core_number
    
        # Numero di core le cui componenti sono tutte quelle chieste dal master
        cores_equal_to_master_request = 0
        total_core_component_percentages = 0

        for core in current_iteration_cores:
            
            day_name = core['days'][0]
            daily_results = all_subproblem_results[day_name]
            
            if len(core['components']) == len(daily_results['scheduled']) + len(daily_results['rejected']):
                cores_equal_to_master_request += 1
            
            total_core_component_percentages += len(core['components']) / (len(daily_results['scheduled']) + len(daily_results['rejected']))

        cores_analysis['number_of_core_equal_to_master_request'] = cores_equal_to_master_request
        cores_analysis['percentage_of_core_equal_to_master_request'] = cores_equal_to_master_request / core_number

        cores_analysis['average_percentage_of_core_done_by_subproblem'] = total_core_component_percentages / core_number

        # Se richiesto, aggiorna le liste dei giorni in cui i core sono
        # attivi con tutti quei giorni 'minori o uguali' nelle unità di
        # cura influenzate.
        if config['expand_core_days']:
            expand_core_days(master_instance, current_iteration_cores, expanded_days)

        total_day_number = 0
        for core in current_iteration_cores:
            total_day_number += len(core['days'])
        
        # Numero medio di giorni in cui i core sono attivi,
        # dopo l'espansione dei giorni. Questo valore è uguale al numero
        # dei core se non è richiesta l'espansione dei giorni.
        cores_analysis['average_day_number_per_core'] = total_day_number / len(current_iteration_cores)

        # Se richiesta, effettua l'espansione dei nomi dei pazienti e/o
        # servizi, aggiornando la lista dei core dell'iterazione corrente.
        if config['expand_core_patients'] or config['expand_core_services']:
            current_iteration_cores.extend(expand_core_patients_services(current_iteration_cores, max_possible_master_requests, master_instance, config['expand_core_patients'], config['expand_core_services'], config['max_expansions_per_core']))
            print(f'[iter {iteration_index}] {len(current_iteration_cores)} total new cores are present after expansion.')
        
        # Se sono presenti più giorni, è possibile che alcuni core siano
        # relativi a richieste impossibili.
        if config['expand_core_days']:
            current_iteration_cores = remove_core_days_without_exact_requests(current_iteration_cores, max_possible_master_requests)
            print(f'[iter {iteration_index}] {len(current_iteration_cores)} new cores are remaining after removing impossible ones.')

        # Calcola e aggiorna i core togliendo eventuali duplicati
        current_iteration_cores, all_iterations_cores = aggregate_and_remove_duplicate_cores(current_iteration_cores, all_iterations_cores)
        
        print(f'[iter {iteration_index}] {len(current_iteration_cores)} cores remaining after removing duplicates.')
        
        if len(current_iteration_cores) > 0:
            
            # Numero di core dopo le eventuali espansioni.
            cores_analysis['core_number_post_name_expansion'] = len(current_iteration_cores)

            total_core_components_number = 0
            for core in  current_iteration_cores:
                total_core_components_number += len(core['components'])
            
            # Numero medio di componenti dei core
            cores_analysis['average_core_size_post_name_expansion'] = total_core_components_number / len(current_iteration_cores)
        
            # Se è presente almeno un core, aggiungi i vincoli nel modello MILP
            # del master.
            add_cores_constraints_to_master_model(master_model, current_iteration_cores)

        # Salvataggio su file dei core di questa iterazione.
        cores_file_path = iteration_cores_directory_path.joinpath('cores.json')
        with open(cores_file_path, 'w') as file:
            json.dump(current_iteration_cores, file, indent=4)
        
        print(f'[iter {iteration_index}] Added {len(current_iteration_cores)} new cores to the master problem.')
        
        # Salvataggio su file dell'analisi dei core di questa
        # iterazione.
        cores_analysis_file_path = iteration_analysis_directory_path.joinpath('core_analysis.json')
        with open(cores_analysis_file_path, 'w') as file:
            json.dump(cores_analysis, file, indent=4)

        print(f'[iter {iteration_index}] Iteration {iteration_index} finished.')
        
        iteration_index += 1

    total_end_time = time.perf_counter()
    print(f'End total solving process. Time elapsed: {total_end_time - total_start_time} seconds')