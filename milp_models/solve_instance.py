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

from milp_models.master_model import get_fat_master_model, get_results_from_fat_master_model
from milp_models.master_model import get_slim_master_model, get_results_from_slim_master_model
from milp_models.subproblem_model import get_fat_subproblem_model, get_results_from_fat_subproblem_model
from milp_models.subproblem_model import get_slim_subproblem_model, get_results_from_slim_subproblem_model
from milp_models.master_model import add_optimality_constraints
from milp_models.sol_perm_model import get_sol_perm_model, get_results_from_sol_perm_model, get_fixed_final_results

from cores.compute_cores import compute_generalist_cores, compute_basic_cores, compute_reduced_cores, aggregate_and_remove_duplicate_cores
from cores.compute_cores import add_cores_constraint_class_to_master_model, add_cores_constraints_to_master_model
from cores.expand_core_days import compute_expanded_days, expand_core_days, remove_core_days_without_exact_requests
from cores.expand_core_patients_services import get_max_possible_master_requests, expand_core_patients_services


def get_subproblem_results_value(master_instance, master_results, day_name):

    value = 0
    for schedule_item in master_results['scheduled'][day_name]:
        
        service_name = schedule_item['service']
        service_duration = master_instance['services'][service_name]['duration']
        
        patient_name = schedule_item['patient']
        patient_priority = master_instance['patients'][patient_name]['priority']
        
        value += service_duration * patient_priority
    
    return value


def get_master_results_value(master_instance, master_results):

    value = 0
    for day_name in master_results['scheduled']:
        value += get_subproblem_results_value(master_instance, master_results, day_name)
    
    return value


def get_final_results_value(master_instance, final_results):
    return get_master_results_value(master_instance, final_results)


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

    return final_results


def get_solver_info(model_results, model_name, log_file_path):

    solution = model_results.solution[0]
    lower_bound = float(model_results['problem'][0]['Lower bound'])
    upper_bound = float(model_results['problem'][0]['Upper bound'])
    gap = float(solution['gap'])
    if gap <= 1e-5 and lower_bound != upper_bound:
        gap = (upper_bound - lower_bound) / upper_bound
    objective_value = float(solution['objective']['objective_function']['Value'])

    solver_info = {}

    # Parsing del file di log
    with open(log_file_path, 'r') as file:
        last_h_line = None
        for line in file.readlines():
            if line.startswith('Explored'):
                tokens = line.split()
                solver_info['explored_nodes'] = int(tokens[1])
            elif line.startswith('Root relaxation'):
                tokens = line.split()
                if tokens[2].startswith('cutoff'):
                    solver_info['root_relax'] = tokens[2][:-1]
                else:
                    solver_info['root_relax'] = float(tokens[3][:-1])
            elif line.startswith('H'):
                last_h_line = line
            elif line.startswith('Optimize a model with'):
                tokens = line.split()
                solver_info['initial_constraints'] = int(tokens[4])
                solver_info['initial_variables'] = int(tokens[6])
            elif line.startswith('Presolved:'):
                tokens = line.split()
                solver_info['presolved_constraints'] = int(tokens[1])
                solver_info['presolved_variables'] = int(tokens[3])
        if last_h_line is not None:
            tokens = last_h_line.split('%')
            solver_info['best_sol_time'] = float(tokens[1].split()[-1][:-1])

    solver_info['objective_function_value'] = objective_value,
    solver_info['solver_status'] = str(model_results.solver.status),
    solver_info['status'] = str(model_results.solver.termination_condition),
    solver_info['time'] = float(model_results.solver.time),
    solver_info['gap_ratio'] = gap,
    solver_info['lower_bound'] = lower_bound,
    solver_info['upper_bound'] = upper_bound if upper_bound <= 1e9 else 'infinity',
    solver_info['gap'] = upper_bound - lower_bound,
    solver_info['model'] = model_name

    if 'root_relax' not in solver_info or solver_info['root_relax'] == 'cutoff':
        solver_info['root_relax'] = solver_info['objective_function_value']
    
    if 'best_sol_time' not in solver_info:
        solver_info['best_sol_time'] = -1

    if type(solver_info['time']) is not float:
        solver_info['time'] = float(solver_info['time'][0])
    if type(solver_info['gap_ratio']) is not float:
        solver_info['gap_ratio'] = float(solver_info['gap_ratio'][0])
    if type(solver_info['lower_bound']) is not float:
        solver_info['lower_bound'] = float(solver_info['lower_bound'][0])
    if type(solver_info['upper_bound']) is not float:
        solver_info['upper_bound'] = float(solver_info['upper_bound'][0])
    if type(solver_info['gap']) is not float:
        solver_info['gap'] = float(solver_info['gap'][0])
    if type(solver_info['status']) is not str:
        solver_info['status'] = str(solver_info['status'][0])
    if type(solver_info['root_relax']) in [list, tuple]:
        solver_info['root_relax'] = float(solver_info['root_relax'][0])
    if type(solver_info['objective_function_value']) in [list, tuple]:
        solver_info['objective_function_value'] = float(solver_info['objective_function_value'][0])
    if type(solver_info['solver_status']) in [list, tuple]:
        solver_info['solver_status'] = str(solver_info['solver_status'][0])
    
    solver_info['best_obj_ratio_root_relax'] = solver_info['lower_bound'] / solver_info['root_relax']

    return solver_info 


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
    results_directory_path.mkdir()

    cores_directory_path = output_directory_path.joinpath('cores')
    cores_directory_path.mkdir()

    logs_directory_path = output_directory_path.joinpath('logs')
    logs_directory_path.mkdir()

    master_instance_file_path = input_directory_path.joinpath('master_instance.json')
    with open(master_instance_file_path, 'w') as file:
        json.dump(master_instance, file, indent=4)

    config_file_path = output_directory_path.joinpath('solver_config.yaml')
    with open(config_file_path, 'w') as file:
        yaml.dump(config, file, default_flow_style=False, sort_keys=False)

    total_start_time = time.perf_counter()

    max_possible_master_requests = get_max_possible_master_requests(master_instance)

    # Matrice di caching delle soluzioni dei sottoproblemi passate. Indicizzata
    # sulle righe da (patient, service) e sulle colonne da (day, iteration)
    if 'use_solution_permutation' in config and config['use_solution_permutation']:
        prev_solution_matrix = {}

    if config['expand_core_days']:
        expanded_days = compute_expanded_days(master_instance)
        expanded_days_file_path = cores_directory_path.joinpath('expanded_days.json')
        with open(expanded_days_file_path, 'w') as file:
            json.dump(expanded_days, file, indent=4)

    print(f'Master model creation... ', end='')
    master_model_creation_start_time = time.perf_counter()

    if config['master_config']['model'] == 'fat-master':
        master_model = get_fat_master_model(master_instance, config['additional_master_info'])
    elif config['master_config']['model'] == 'slim-master':
        master_model = get_slim_master_model(master_instance, config['additional_master_info'])

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

        iteration_logs_directory_path = logs_directory_path.joinpath(f'iter_{iteration_index}')
        iteration_logs_directory_path.mkdir()
        
        master_log_file_path = iteration_logs_directory_path.joinpath('master_log.log')

        print(f'[iter {iteration_index}] Solving master... ', end='')
        master_solving_start_time = time.perf_counter()
        
        master_model_results = master_opt.solve(master_model, tee=False, warmstart=config['warm_start_master'], logfile=master_log_file_path)

        master_solving_end_time = time.perf_counter()
        print(f'ended ({master_solving_end_time - master_solving_start_time}s).')

        # Ottenimento dei dati del solver
        master_model.solutions.store_to(master_model_results)
        master_info = get_solver_info(master_model_results, config['master_config']['model'], master_log_file_path)

        master_info['master_external_solving_time'] = master_solving_end_time - master_solving_start_time

        master_info_file_path = iteration_logs_directory_path.joinpath(f'master_info.json')
        with open(master_info_file_path, 'w') as file:
            json.dump(master_info, file, indent=4)

        if config['master_config']['model'] == 'fat-master':
            master_results = get_results_from_fat_master_model(master_model)
        elif config['master_config']['model'] == 'slim-master':
            master_results = get_results_from_slim_master_model(master_model)

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

        # Controllo della presenza di una combinazione di soluzioni precedenti
        # che soddisfi delle richieste di valore pari al master
        if 'use_solution_permutation' in config and config['use_solution_permutation'] and iteration_index > 1:
            
            print(f'[iter {iteration_index}] Searching for a permutation of previous solutions')

            master_results_value = get_master_results_value(master_instance, master_results)
            
            sol_perm_model = get_sol_perm_model(master_instance, prev_solution_matrix)
            
            opt = pyo.SolverFactory(config['master_config']['solver'])
            sol_perm_start_time = time.perf_counter()
            opt.solve(sol_perm_model, tee=False)
            sol_perm_end_time = time.perf_counter()

            sol_perm_solution_value = pyo.value(sol_perm_model.objective_function)
            sol_perm_info = {
                'sol_perm_external_solving_time': sol_perm_end_time - sol_perm_start_time,
                'sol_perm_objective_function_value': sol_perm_solution_value,
                'sol_perm_difference_between_master': master_results_value - sol_perm_solution_value,
                'best_solution_value_so_far': best_final_results_value
            }

            with open(iteration_logs_directory_path.joinpath('sol_perm_info.json'), 'w') as file:
                json.dump(sol_perm_info, file, indent=4)

            # Per avere la soluzione ottima è necessario che il valore sia
            # uguale a quello del master
            if sol_perm_solution_value < master_results_value:
                print(f'[iter {iteration_index}] Permutation not found ({sol_perm_solution_value} value, {master_results_value - sol_perm_solution_value} slots less than master, {best_final_results_value} is best subproblems so far).')
            else:
                print(f'[iter {iteration_index}] [STOP] Found a possible permutation of previous solution. Stopping the iterations.')
                
                sol_perm_results = get_results_from_sol_perm_model(sol_perm_model)

                # Leggi i risultati dei sottoproblemi dei giorni selezionati
                all_subproblem_results = {}
                for day_name, i in sol_perm_results.items():
                    subproblem_results_file_path = results_directory_path.joinpath(f'iter_{i}').joinpath(f'subproblem_day_{day_name}_results.json')
                    with open(subproblem_results_file_path, 'r') as file:
                        all_subproblem_results[day_name] = json.load(file)
                
                # Componi assieme le soluzioni dei sottoproblemi
                # Rimozione di eventuali schedulazioni doppie e finestre risolte
                final_results = get_fixed_final_results(master_instance, all_subproblem_results)

                # Salvataggio file con i risultati
                final_results_file_path = iteration_results_directory_path.joinpath('final_results.json')
                with open(final_results_file_path, 'w') as file:
                    json.dump(final_results, file, indent=4)
                with open(best_final_results_file_path, 'w') as file:
                    json.dump(final_results, file, indent=4)
                
                if config['checks_throw_exceptions']:
                    check_final_results(master_instance, final_results)
                else:
                    try:
                        check_final_results(master_instance, final_results)
                    except Exception as exception:
                        print(exception)

                # Soluzione ottima raggiunta
                break

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

            print(f'[iter {iteration_index}] Model creation for day \'{day_name}\'... ', end='')
            subproblem_model_creation_start_time = time.perf_counter()

            if config['subproblem_config']['model'] == 'fat-subproblem':
                subproblem_model = get_fat_subproblem_model(subproblem_instance, config['additional_subproblem_info'])
            elif config['subproblem_config']['model'] == 'slim-subproblem':
                subproblem_model = get_slim_subproblem_model(subproblem_instance, config['additional_subproblem_info'])

            subproblem_model_creation_end_time = time.perf_counter()
            print(f'ended ({round(subproblem_model_creation_end_time - subproblem_model_creation_start_time, 4)}s). ', end='')

            subproblem_opt = pyo.SolverFactory(config['subproblem_config']['solver'])

            if 'time_limit' in config['subproblem_config']:
                if config['subproblem_config']['solver'] == 'glpk':
                    subproblem_opt.options['tmlim'] = config['subproblem_config']['time_limit']
                elif config['subproblem_config']['solver'] == 'gurobi':
                    subproblem_opt.options['TimeLimit'] = config['subproblem_config']['time_limit']
            if 'max_memory' in config['subproblem_config']:
                subproblem_opt.options['SoftMemLimit'] = config['subproblem_config']['max_memory']

            subproblem_log_file_path = iteration_logs_directory_path.joinpath(f'subproblem_day_{day_name}_log.log')

            print(f'Solving... ', end='')
            subproblem_solving_start_time = time.perf_counter()
            
            subproblem_model_results = subproblem_opt.solve(subproblem_model, tee=False, logfile=subproblem_log_file_path)

            subproblem_solving_end_time = time.perf_counter()
            print(f'ended ({round(subproblem_solving_end_time - subproblem_solving_start_time, 4)}s).')

            # Ottenimento dei dati del solver
            subproblem_model.solutions.store_to(subproblem_model_results)
            subproblem_info = get_solver_info(subproblem_model_results, config['subproblem_config']['model'], subproblem_log_file_path)

            subproblem_info['subproblem_model_creation_time'] = subproblem_model_creation_end_time - subproblem_model_creation_start_time
            subproblem_info['subproblem_external_solving_time'] = subproblem_solving_end_time - subproblem_solving_start_time

            subproblem_info_file_path = iteration_logs_directory_path.joinpath(f'subproblem_info_day_{day_name}.json')
            with open(subproblem_info_file_path, 'w') as file:
                json.dump(subproblem_info, file, indent=4)

            if config['subproblem_config']['model'] == 'fat-subproblem':
                subproblem_results = get_results_from_fat_subproblem_model(subproblem_model)
            elif config['subproblem_config']['model'] == 'slim-subproblem':
                subproblem_results = get_results_from_slim_subproblem_model(subproblem_model)

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

        # Ogni giorno risolto può diventare una nuova colonna della matrice di
        # cache
        if 'use_solution_permutation' in config and config['use_solution_permutation']:
            for day_name, day_results in all_subproblem_results.items():

                # Se i servizi accettati della soluzione del giorno corrente
                # sono uguali a quelli di soluzioni passate (dello stesso giorno
                # in iterazioni 0..iteration_index) allora si può evitare di
                # aggiungere questa nuova soluzione
                is_exactly_equal = True
                for other_iteration_index in range(iteration_index):
                    column_to_check = (day_name, other_iteration_index)
                    
                    # Controllo sull'esistenza di una soluzione identica a
                    # quella corrente
                    for schedule in day_results['scheduled']:
                        
                        p = schedule['patient']
                        s = schedule['service']

                        if (p, s) not in prev_solution_matrix:
                            is_exactly_equal = False
                            break
                        
                        if column_to_check not in prev_solution_matrix[p, s]:
                            is_exactly_equal = False
                            break
                    if is_exactly_equal:
                        break
                if is_exactly_equal:
                    continue
                
                # Se la soluzione non è già presente, aggiungila come colonna
                # della matrice
                for schedule in day_results['scheduled']:
                    p = schedule['patient']
                    s = schedule['service']
                    if (p, s) not in prev_solution_matrix:
                        prev_solution_matrix[p, s] = []
                    prev_solution_matrix[p, s].append((int(day_name), iteration_index))

        # Elenco dei giorni con almeno una richiesta non soddisfatta
        days_not_completely_solved = []
        for day_name, day_results in all_subproblem_results.items():
            if len(day_results['rejected']) > 0:
                days_not_completely_solved.append(day_name)
        
        # Se tutti i giorni sono completamente risolti termina le iterazioni
        if len(days_not_completely_solved) == 0:
            print(f'[iter {iteration_index}] [STOP] All days are solved: exiting iteration cycle.') 
            break
        else:
            days_str = ', '.join(days_not_completely_solved)
            print(f'[iter {iteration_index}] Days [{days_str}] are not completely solved')

        if config['early_stop_percentage_between_master_and_subproblem'] > 0.0:
            
            master_results_value = get_master_results_value(master_instance, master_results)
            
            subproblems_results_value = 0
            for day_name, day_results in all_subproblem_results.items():
                subproblems_results_value += get_subproblem_results_value(master_instance, final_results, day_name)
            
            min_difference = config['early_stop_percentage_between_master_and_subproblem']
            
            if (master_results_value - subproblems_results_value) / master_results_value <= min_difference:
                print(f'[iter {iteration_index}] [STOP] Master and subproblems reached the minimum value difference ({min_difference}%): exiting iteration cycle.') 
                break

        if 'use_optimality_constraints' in config['additional_master_info']:
            add_optimality_constraints(master_model, master_instance, all_subproblem_results, max_possible_master_requests)
            
        cores_info = {}

        core_creation_start_time = time.perf_counter()

        # Calcola l'elenco di core a partire dalle richieste non schedulate:
        # > Core generalist: tutto quanto è richiesto in un dato giorno,
        # > Core basic: ogni singola richiesta non schedulata più tutte
        #   quelle schedulate,
        # > Core reduced: ogni singola richiesta non schedulata più tutte
        #   quelle schedulate che hanno paziente o unità di cura
        #   influenzate, anche a catena.
        if config['core_type'] == 'generalist':
            current_iteration_cores = compute_generalist_cores(all_subproblem_results)
        elif config['core_type'] == 'basic':
            current_iteration_cores = compute_basic_cores(all_subproblem_results)
        elif config['core_type'] == 'reduced':
            current_iteration_cores = compute_reduced_cores(all_subproblem_results, master_instance)

        core_creation_end_time = time.perf_counter()
        cores_info['core_creation_time'] = core_creation_end_time - core_creation_start_time

        if  config['expand_core_days'] or config['expand_core_patients'] or config['expand_core_services']:
            print(f'[iter {iteration_index}] {len(current_iteration_cores)} new cores are found.')
        
        core_number = len(current_iteration_cores)

        # Numero di core prima dell'eventuale espansione
        cores_info['core_number_pre_expansion'] = core_number
        
        day_names = set()
        for core in current_iteration_cores:
            day_names.update(core['days'])
        
        # Numero di giorni che hanno almeno un core
        cores_info['day_with_cores_pre_expansion'] = len(day_names)

        total_core_components_number = 0
        for core in current_iteration_cores:
            total_core_components_number += len(core['components'])
        
        # Numero medio di componenti dei core
        cores_info['average_core_size_pre_expansion'] = total_core_components_number / core_number
    
        # Numero di core le cui componenti sono tutte quelle chieste dal master
        cores_equal_to_master_request = 0
        total_core_component_percentages = 0

        for core in current_iteration_cores:
            
            day_name = core['days'][0]
            daily_results = all_subproblem_results[day_name]
            
            if len(core['components']) == len(daily_results['scheduled']) + len(daily_results['rejected']):
                cores_equal_to_master_request += 1
            
            total_core_component_percentages += len(core['components']) / (len(daily_results['scheduled']) + len(daily_results['rejected']))

        cores_info['number_of_core_equal_to_master_request'] = cores_equal_to_master_request
        cores_info['percentage_of_core_equal_to_master_request'] = cores_equal_to_master_request / core_number
        cores_info['average_percentage_of_core_done_by_subproblem'] = total_core_component_percentages / core_number

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
        cores_info['average_day_number_per_core'] = total_day_number / len(current_iteration_cores)

        # Se richiesta, effettua l'espansione dei nomi dei pazienti e/o
        # servizi, aggiornando la lista dei core dell'iterazione corrente.
        if config['expand_core_patients'] or config['expand_core_services']:
            
            core_expansion_start_time = time.perf_counter()
            
            current_iteration_cores.extend(expand_core_patients_services(current_iteration_cores, max_possible_master_requests, master_instance, config['expand_core_patients'], config['expand_core_services'], config['max_expansions_per_core']))
            
            core_expansion_end_time = time.perf_counter()
            cores_info['expansion_time'] = core_expansion_end_time - core_expansion_start_time
            
            print(f'[iter {iteration_index}] {len(current_iteration_cores)} total new cores are present after expansion.')
        
        core_postproc_start_time = time.perf_counter()

        # Se sono presenti più giorni, è possibile che alcuni core siano
        # relativi a richieste impossibili.
        if config['expand_core_days']:
            current_iteration_cores = remove_core_days_without_exact_requests(current_iteration_cores, max_possible_master_requests)
            print(f'[iter {iteration_index}] {len(current_iteration_cores)} new cores are remaining after removing impossible ones.')

        # Calcola e aggiorna i core togliendo eventuali duplicati
        current_iteration_cores, all_iterations_cores = aggregate_and_remove_duplicate_cores(current_iteration_cores, all_iterations_cores)
        
        core_postproc_end_time = time.perf_counter()
        cores_info['postproc_time'] = core_postproc_end_time - core_postproc_start_time

        print(f'[iter {iteration_index}] {len(current_iteration_cores)} cores remaining after removing duplicates.')
        
        # Numero di core dopo le eventuali espansioni.
        cores_info['core_number_post_name_expansion'] = len(current_iteration_cores)

        if len(current_iteration_cores) > 0:
            
            total_core_components_number = 0
            for core in  current_iteration_cores:
                total_core_components_number += len(core['components'])
            
            # Numero medio di componenti dei core
            cores_info['average_core_size_post_name_expansion'] = total_core_components_number / len(current_iteration_cores)
        
            # Se è presente almeno un core, aggiungi i vincoli nel modello MILP
            # del master.
            add_cores_constraints_to_master_model(master_model, current_iteration_cores)

        # Salvataggio su file dei core di questa iterazione.
        cores_file_path = cores_directory_path.joinpath(f'iter_{iteration_index}_cores.json')
        with open(cores_file_path, 'w') as file:
            json.dump(current_iteration_cores, file, indent=4)
        
        print(f'[iter {iteration_index}] Added {len(current_iteration_cores)} new cores to the master problem.')
        
        # Salvataggio su file dell'analisi dei core di questa
        # iterazione.
        cores_analysis_file_path = iteration_logs_directory_path.joinpath('core_info.json')
        with open(cores_analysis_file_path, 'w') as file:
            json.dump(cores_info, file, indent=4)

        iteration_index += 1

        if iteration_index < max_iteration_number:
            print(f'[iter {iteration_index}] Iteration {iteration_index} finished.')
        else:
            print(f'[iter {iteration_index}] [STOP] Iteration maximum {iteration_index} reached.')

    total_end_time = time.perf_counter()
    print(f'End total solving process. Time elapsed: {total_end_time - total_start_time} seconds.')