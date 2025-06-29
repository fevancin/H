
# from analyzers.final_results_analyzer import analyze_final_results

# from plotters.aggregate_results_plotter import plot_all_instances_iteration_times
# from plotters.aggregate_results_plotter import plot_results_values_by_group
# from plotters.aggregate_results_plotter import plot_results_values_by_instance
# from plotters.aggregate_results_plotter import plot_subproblem_cumulative_times
# from plotters.aggregate_results_plotter import plot_solving_times
# from plotters.aggregate_results_plotter import plot_cores

# from plotters.aggregate_results_plotter import plot_solving_times_by_day
# from plotters.aggregate_results_plotter import plot_free_slots


# def get_all_master_results_info(results_directory_path):

#     all_master_results_info = []
#     iteration_index = 0
    
#     iteration_results_directory_path = results_directory_path.joinpath(f'iter_{iteration_index}')
#     while iteration_results_directory_path.exists():
        
#         master_results_file_path = iteration_results_directory_path.joinpath('master_results.json')
#         if not master_results_file_path.exists():
#             return all_master_results_info
        
#         with open(master_results_file_path, 'r') as file:
#             master_results = json.load(file)
#         all_master_results_info.append(master_results['info'])

#         iteration_index += 1
#         iteration_results_directory_path = results_directory_path.joinpath(f'iter_{iteration_index}')

#     return all_master_results_info


# def get_all_subproblem_results_info(results_directory_path):

#     all_subproblem_results_info = []
#     iteration_index = 0

#     iteration_results_directory_path = results_directory_path.joinpath(f'iter_{iteration_index}')
#     while iteration_results_directory_path.exists():
    
#         all_subproblem_results_info.append({})
        
#         day_index = 0
#         subproblem_results_file_path = iteration_results_directory_path.joinpath(f'subproblem_day_{day_index}_results.json')
        
#         if not subproblem_results_file_path.exists():
#             all_subproblem_results_info.pop()
#             return all_subproblem_results_info
        
#         while subproblem_results_file_path.exists():
#             with open(subproblem_results_file_path, 'r') as file:
#                 subproblem_results = json.load(file)
        
#             all_subproblem_results_info[-1][str(day_index)] = subproblem_results['info']
#             day_index += 1
        
#             subproblem_results_file_path = iteration_results_directory_path.joinpath(f'subproblem_day_{day_index}_results.json')

#         iteration_index += 1
#         iteration_results_directory_path = results_directory_path.joinpath(f'iter_{iteration_index}')
        
#     return all_subproblem_results_info


# def get_all_final_results_info(results_directory_path):

#     all_final_results_info = []
#     iteration_index = 0

#     iteration_results_directory_path = results_directory_path.joinpath(f'iter_{iteration_index}')
#     while iteration_results_directory_path.exists():

#         final_results_file_path = iteration_results_directory_path.joinpath('final_results.json')
#         if not final_results_file_path.exists():
#             return all_final_results_info
        
#         with open(final_results_file_path, 'r') as file:
#             final_results = json.load(file)
#         all_final_results_info.append(final_results['info'])

#         iteration_index += 1
#         iteration_results_directory_path = results_directory_path.joinpath(f'iter_{iteration_index}')
    
#     return all_final_results_info


# if __name__ != '__main__':
#     exit(0)

# parser = argparse.ArgumentParser(prog='Final analysis', description='Aggregate and plot results')
# parser.add_argument('-i', '--input', type=Path, help='Groups directory path', required=True)
# args = parser.parse_args()

# groups_directory_path = Path(args.input).resolve()

# if not groups_directory_path.exists():
#     raise ValueError(f'Groups directory \'{groups_directory_path}\' does not exists')
# elif not groups_directory_path.is_dir():
#     raise ValueError(f'Groups \'{groups_directory_path}\' is not a directory')

# plot_all_instances_iteration_times(groups_directory_path, 'instance_times.png')

# plot_results_values_by_group(groups_directory_path, 'results_values_groups.png')
# plot_results_values_by_instance(groups_directory_path, 'results_values_instances.png')

# for group_directory_path in groups_directory_path.iterdir():

#     if not group_directory_path.is_dir():
#         continue

#     print(f'Starting group {group_directory_path}')

#     input_directory_path = group_directory_path.joinpath('input')
#     results_directory_path = group_directory_path.joinpath('results')
#     cores_directory_path = group_directory_path.joinpath('cores')

#     if not input_directory_path.exists():
#         raise ValueError(f'Input directory \'{input_directory_path}\' does not exists')
#     elif not input_directory_path.is_dir():
#         raise ValueError(f'Input directory \'{input_directory_path}\' is not a directory')

#     if not results_directory_path.exists():
#         raise ValueError(f'Results directory \'{results_directory_path}\' does not exists')
#     elif not results_directory_path.is_dir():
#         raise ValueError(f'Results directory \'{results_directory_path}\' is not a directory')

#     all_master_results_info = get_all_master_results_info(results_directory_path)
#     all_subproblem_results_info = get_all_subproblem_results_info(results_directory_path)
#     all_final_results_info = get_all_final_results_info(results_directory_path)

#     plot_directory_path = group_directory_path.joinpath('plots')
#     plot_directory_path.mkdir(exist_ok=True)

#     if all_master_results_info is not None and all_subproblem_results_info is not None:
#         plot_file_path = plot_directory_path.joinpath('cumulative_times.png')
#         plot_subproblem_cumulative_times(all_master_results_info, all_subproblem_results_info, plot_file_path)

#     if all_subproblem_results_info is not None:
#         plot_file_path = plot_directory_path.joinpath('solving_times.png')
#         plot_solving_times(all_master_results_info, all_subproblem_results_info, plot_file_path)

#     if all_subproblem_results_info is not None:
#         plot_file_path = plot_directory_path.joinpath('solving_times_by_day.png')
#         plot_solving_times_by_day(all_subproblem_results_info, plot_file_path)

#     plot_file_path = plot_directory_path.joinpath('cores.png')
#     plot_cores(cores_directory_path, plot_file_path)

#     master_instance_file_path = None
#     for input_file_name in input_directory_path.iterdir():
#         if input_file_name.suffix == '.json':
#             master_instance_file_path = input_file_name
#             break

#     if master_instance_file_path is None:
#         raise ValueError(f'Master instance not found')

#     with open(master_instance_file_path, 'r') as file:
#         master_instance = json.load(file)
    
#     plot_file_path = plot_directory_path.joinpath('free_time_slots.png')
    
#     all_final_results = {}
#     results_directory_path = group_directory_path.joinpath('results')
    
#     for iteration_results_path in results_directory_path.iterdir():
    
#         if not iteration_results_path.is_dir():
#             continue
    
#         iteration_index = int(iteration_results_path.name.removeprefix('iter_'))
#         final_results_file_path = iteration_results_path.joinpath('final_results.json')
    
#         with open(final_results_file_path, 'r') as file:
#             all_final_results[iteration_index] = json.load(file)
    
#     plot_free_slots(master_instance, all_final_results, plot_file_path)

#     analysis_directory_path = group_directory_path.joinpath('analysis')
#     analysis_directory_path.mkdir(exist_ok=True)

#     master_instance_analysis_file_path = analysis_directory_path.joinpath('master_instance_analysis.json')
#     if not master_instance_analysis_file_path.exists():
#         master_instance_analysis = analyze_master_instance(master_instance, master_instance_file_path)
#         with open(master_instance_analysis_file_path, 'w') as file:
#             json.dump(master_instance_analysis, file, indent=4)

#     master_results_analysis_rows = []
#     final_results_analysis_rows = []

#     for iteration_results_directory_path in results_directory_path.iterdir():

#         iteration_name = iteration_results_directory_path.name
        
#         iteration_results_directory_path = results_directory_path.joinpath(iteration_name)
#         master_results_file_name = iteration_results_directory_path.joinpath('master_results.json')
#         if master_results_file_name.exists():
#             with open(master_results_file_name, 'r') as file:
#                 master_results = json.load(file)
#         else:
#             master_results = None
#         final_results_file_name = iteration_results_directory_path.joinpath('final_results.json')
#         if final_results_file_name.exists():
#             with open(final_results_file_name, 'r') as file:
#                 final_results = json.load(file)
#         else:
#             final_results = None
        
#         iteration_analysis_directory_path = analysis_directory_path.joinpath(iteration_name)
#         master_results_analysis_file_name = iteration_analysis_directory_path.joinpath('master_results_analysis.json')
#         final_results_analysis_file_name = iteration_analysis_directory_path.joinpath('final_results_analysis.json')
        
#         if master_results is not None:
#             if not master_results_analysis_file_name.exists():
#                 master_results_analysis = analyze_master_results(master_instance, master_results, master_instance_file_path)
#                 master_results_analysis['iteration'] = iteration_name
#                 with open(master_results_analysis_file_name, 'w') as file:
#                     json.dump(master_results_analysis, file, indent=4)
#             else:
#                 with open(master_results_analysis_file_name, 'r') as file:
#                     master_results_analysis = json.load(file)
#                 master_results_analysis['iteration'] = iteration_name

#             master_results_analysis_rows.append(master_results_analysis)

#         if final_results is not None:
#             if not final_results_analysis_file_name.exists():
#                 final_results_analysis = analyze_final_results(master_instance, final_results, master_instance_file_path)
#                 final_results_analysis['iteration'] = iteration_name
#                 with open(final_results_analysis_file_name, 'w') as file:
#                     json.dump(final_results_analysis, file, indent=4)
#             else:
#                 with open(final_results_analysis_file_name, 'r') as file:
#                     final_results_analysis = json.load(file)
#                 final_results_analysis['iteration'] = iteration_name
        
#             final_results_analysis_rows.append(final_results_analysis)

#     if len(master_results_analysis_rows) > 0:
#         with open(analysis_directory_path.joinpath('master_results.csv'), 'w', newline='') as file:
#             fieldnames = list(master_results_analysis_rows[0].keys())
#             writer = csv.DictWriter(file, fieldnames=fieldnames)
#             writer.writeheader()
#             for master_results_analysis_row in master_results_analysis_rows:
#                 writer.writerow(master_results_analysis_row)

#     if len(final_results_analysis_rows) > 0:
#         with open(analysis_directory_path.joinpath('final_results.csv'), 'w', newline='') as file:
#             fieldnames = list(final_results_analysis_rows[0].keys())
#             writer = csv.DictWriter(file, fieldnames=fieldnames)
#             writer.writeheader()
#             for final_results_analysis_row in final_results_analysis_rows:
#                 writer.writerow(final_results_analysis_row)
                
#     print(f'Ending group {group_directory_path}')






from pathlib import Path
import argparse
import json
import yaml
import pandas as pd


def get_total_window_number(master_instance):
    
    window_number = 0
    for patient in master_instance['patients'].values():
        window_number += sum(len(windows) for windows in patient['requests'].values())

    return window_number


def get_average_tolerance(master_instance):

    tolerance_sum = 0
    tolerance_number = 0
    for patient in master_instance['patients'].values():
        for windows in patient['requests'].values():
            for window in windows:
                tolerance_sum += (window[1] - window[0]) * 0.5
                tolerance_number += 1
    
    return tolerance_sum / tolerance_number


def get_demand_vs_disponibility_by_day(master_instance):

    days_disponibility = {int(day_name): sum(o['duration'] for c in d.values() for o in c.values())
        for day_name, d in master_instance['days'].items()}

    worst_scenario = {int(day_name): 0 for day_name in master_instance['days'].keys()}

    for patient in master_instance['patients'].values():
        for service_name, windows in patient['requests'].items():
            service_duration = master_instance['services'][service_name]['duration']
            for window in windows:
                for day_index in range(window[0], window[1] + 1):
                    worst_scenario[day_index] += service_duration

    requests_vs_disponibility = sum(worst_scenario[day_index] / days_disponibility[day_index] for day_index in worst_scenario)

    return requests_vs_disponibility / len(worst_scenario)


def get_total_time_slots_in_all_days(master_instance):

    time_slots_global_sum = 0

    for day in master_instance['days'].values():
        for care_unit in day.values():
            for operator in care_unit.values():
                time_slots_global_sum += operator['duration']
    
    return time_slots_global_sum


def get_average_time_slots_per_care_unit(master_instance):

    time_slots_global_sum = get_total_time_slots_in_all_days(master_instance)
    
    care_unit_number = 0
    for day in master_instance['days'].values():
        care_unit_number += len(day)
    
    return time_slots_global_sum / care_unit_number


def get_total_service_durations_requested(master_instance):
    
    total_service_durations = 0
    
    for patient in master_instance['patients'].values():
        for service_name, windows in patient['requests'].items():
            service_duration = master_instance['services'][service_name]['duration']
            total_service_durations += service_duration * len(windows)

    return total_service_durations


def get_total_aggregate_demand_vs_disponibility(master_instance):

    total_demand = get_total_service_durations_requested(master_instance)
    total_disponibility = get_total_time_slots_in_all_days(master_instance)

    return total_demand / total_disponibility


def get_average_overlapping_windows_per_patient(master_instance):

    overlap_windows_number = 0

    for patient in master_instance['patients'].values():
        
        all_patient_windows = []
        
        for windows in patient['requests'].values():
            all_patient_windows.extend(windows)
        
        if len(all_patient_windows) == 0:
            continue
        
        for i in range(len(all_patient_windows) - 1):
            window = all_patient_windows[i]
            for j in range(i + 1, len(all_patient_windows)):
                other_window = all_patient_windows[j]
                if ((window[0] <= other_window[0] and window[1] >= other_window[0]) or
                    (other_window[0] <= window[0] and other_window[1] >= window[0])):
                    overlap_windows_number += 1

    return overlap_windows_number / len(master_instance['patients'].keys())


def get_max_requests_in_same_day_per_patient(master_instance):

    max_overlap = 0

    for patient in master_instance['patients'].values():

        overlaps = {int(day_name): 0 for day_name in master_instance['days'].keys()}

        for windows in patient['requests'].values():
            for window in windows:
                for day_index in range(window[0], window[1] + 1):
                    overlaps[day_index] += 1
        
        max_patient_overlap = max(overlap for overlap in overlaps.values())
        if max_patient_overlap > max_overlap:
            max_overlap = max_patient_overlap
    
    return max_overlap




def get_satisfied_window_number(master_results):

    satisfied_window_number = 0
    for day in master_results['scheduled'].values():
        satisfied_window_number += len(day)
    
    return satisfied_window_number


def get_requests_per_patient_same_day(master_results):

    total_average = 0
    true_minimum = None
    true_maximum = None

    for day in master_results['scheduled'].values():
        
        patient_names = set()
        for request in day:
            patient_names.add(request['patient'])
    
        services_per_patient = []
        for patient_name in patient_names:

            request_number = 0
            for request in day:
                if request['patient'] == patient_name:
                    request_number += 1
            services_per_patient.append(request_number)
        

        average = sum(services_per_patient) / len(patient_names)
        
        minimum = min(services_per_patient)
        maximum = max(services_per_patient)
        
        if true_minimum is None or minimum < true_minimum:
            true_minimum = minimum
        if true_maximum is None or maximum > true_maximum:
            true_maximum = maximum

        total_average += average
    
    return true_minimum, true_maximum, total_average / len(master_results['scheduled'])


def analyze_master_instance(master_instance):

    data = {}

    window_number = get_total_window_number(master_instance)

    data['window_number'] = window_number
    data['average_windows_per_patient'] = window_number / len(master_instance['patients'])
    data['average_tolerance'] = get_average_tolerance(master_instance)
    data['average_time_slots_per_care_unit'] = get_average_time_slots_per_care_unit(master_instance)
    data['average_overlapping_requests_per_patient'] = get_average_overlapping_windows_per_patient(master_instance)
    data['max_requests_in_same_day_per_patient'] = get_max_requests_in_same_day_per_patient(master_instance)
    data['demand_vs_disponibility_by_day'] = get_demand_vs_disponibility_by_day(master_instance)
    data['total_aggregate_demand_vs_disponibility'] = get_total_aggregate_demand_vs_disponibility(master_instance)

    return data


def analyze_master_results(master_instance, master_results):
    
    data = {}
    
    data['satisfied_window_number'] = get_satisfied_window_number(master_results)
    data['rejected_window_number'] = len(master_results['rejected'])
    # data['solution_value'] = get_master_results_value(master_instance, master_results)

    minimum, maximum, average = get_requests_per_patient_same_day(master_results)
    data['average_requests_per_patient_same_day'] = average
    data['min_requests_per_patient_same_day'] = minimum
    data['max_requests_per_patient_same_day'] = maximum
    
    return data


def analyze_subproblem_instance(instance):

    min_operator_start = min(o['start'] for c in instance['day'].values() for o in c.values())
    max_operator_start = max(o['start'] for c in instance['day'].values() for o in c.values())
    max_operator_duration = max(o['duration'] for c in instance['day'].values() for o in c.values())
    total_operator_duration = sum(o['duration'] for c in instance['day'].values() for o in c.values())
    overlap_percentage = 1.0 - (max_operator_start - min_operator_start) / max_operator_duration    
    
    total_requests_number = sum(len(patient['requests']) for patient in instance['patients'].values())
    total_requests_duration = sum(instance['services'][s]['duration'] for p in instance['patients'].values() for s in p['requests'])
    
    patient_number = len(instance['patients'])
    care_unit_number = len(instance['day'])

    duration_ratios = []
    for cn, c in instance['day'].items():
        total_care_unit_operator_duration = sum(o['duration'] for o in c.values())
        total_care_unit_requests_duration = sum(instance['services'][s]['duration'] for p in instance['patients'].values() for s in p['requests'] if instance['services'][s]['care_unit'] == cn)
        duration_ratios.append(total_care_unit_requests_duration / total_care_unit_operator_duration)

    data = {}
    data['avg_tasks_per_patient'] = round(total_requests_number / patient_number)
    data['machines'] = sum(len(care_unit) for care_unit in instance['day'].values())
    data['care_units'] = care_unit_number
    data['total_resources'] = care_unit_number
    data['overlap'] = f'P{int(overlap_percentage * 100)}%'
    data['total_capacity'] = total_operator_duration
    data['jobs'] = patient_number
    data['total_duration'] = total_requests_duration
    data['avg_total_duration_per_patient'] = total_requests_duration / patient_number
    data['avg_services_per_patient'] = total_requests_number / patient_number
    data['tasks'] = total_requests_number
    data['total_capacity'] = total_operator_duration
    data['total_resources'] = care_unit_number
    data['total_average_duration'] = total_requests_duration / total_requests_number
    data['average_duration_ratio'] = sum(duration_ratios) / len(duration_ratios)

    return data


def analyze_subproblem_results(instance, results):

    requests_total_number = sum(len(p['requests']) for p in instance['patients'].values())
    requests_total_duration = sum(instance['services'][s]['duration'] for p in instance['patients'].values() for s in p['requests'])
    scheduled_requests_total_duration = sum(instance['services'][r['service']]['duration'] for r in results['scheduled'])
    
    data = {}
    data['rejected'] = len(results['rejected'])
    data['served'] = len(results['scheduled'])
    data['served_task_ratio'] = len(results['scheduled']) / requests_total_number
    data['best_obj_ratio_dur'] = scheduled_requests_total_duration / requests_total_duration

    return data


# Questo programma può essere chiamato solo dalla linea di comando
if __name__ != '__main__':
    exit(0)

# Argomenti da linea di comando
parser = argparse.ArgumentParser(prog='Analizer', description='Analyze and plot results.')
parser.add_argument('-c', '--config', type=Path, help='Analyzer configuration', required=True)
parser.add_argument('-r', '--results', type=Path, help='Directory with instance results groups.', required=True)
args = parser.parse_args()

config_file_path = Path(args.config).resolve()
results_directory_path = Path(args.results).resolve()

# Controlli sulla validità degli argomenti da linea di comando
if not config_file_path.exists():
    raise FileNotFoundError(f'Path \'{config_file_path}\' does not exist.')
if config_file_path.suffix != '.yaml':
    raise FileNotFoundError(f'Path \'{config_file_path}\' is not a YAML file.')
if not results_directory_path.exists():
    raise FileNotFoundError(f'Path \'{results_directory_path}\' does not exist.')
elif not results_directory_path.is_dir():
    raise FileNotFoundError(f'Path \'{results_directory_path}\' is not a directory.')

# Lettura del file di configurazione
with open(config_file_path, 'r') as file:
    config = yaml.load(file, yaml.Loader)

# Eventuale creazione della cartella di analisi
analysis_directory_path = results_directory_path.joinpath('analysis')
if not analysis_directory_path.exists():
    analysis_directory_path.mkdir()
    print(f'\'analysis\' does not exist, creating it.')

# iterative_infos = {
#     'master_input_infos': [],
#     'subproblem_input_infos': [],
#     'master_results_infos': [],
#     'subproblem_results_infos': [],
#     'final_results_infos': [],
#     'cores_infos': []
# }

single_pass_master_analysis = {
    'instance': []
}
single_pass_subproblem_analysis = {
    'instance': []
}

multiple_keys = set()
total_instance_number = 0
total_group_number = 0

for group_directory_path in results_directory_path.iterdir():
    if not group_directory_path.is_dir():
        continue
    if group_directory_path.name == 'analysis':
        continue

    group_name = group_directory_path.name

    # Eventuale scarto di alcuni gruppi
    if 'groups_to_do' in config and 'all' not in config['groups_to_do'] and group_name not in config['groups_to_do']:
        continue
    if 'groups_to_avoid' in config and group_name in config['groups_to_avoid']:
        continue

    print(f'Reading results data in directory \'{group_name}\'')
    total_group_number += 1

    # Se sono presenti i core i risultati sono di un test iterativo
    cores_group_directory_path = group_directory_path.joinpath('cores')
    is_iterative_results = cores_group_directory_path.exists()

    # Conrtolli sulle cartelle dei risultati del gruppo corrente
    input_group_directory_path = group_directory_path.joinpath('input')
    if not input_group_directory_path.exists():
        print(f'Directory \'input\' of group \'{group_name}\' does not exists, skipping group.')
        continue
    
    results_group_directory_path = group_directory_path.joinpath('results')
    if not results_group_directory_path.exists():
        print(f'Directory \'results\' of group \'{group_name}\' does not exists, skipping group.')
        continue
    
    logs_group_directory_path = group_directory_path.joinpath('logs')
    if not logs_group_directory_path.exists():
        print(f'Directory \'logs\' of group \'{group_name}\' does not exists, skipping group.')
        continue
    
    if not is_iterative_results:

        for instance_file_path in input_group_directory_path.iterdir():
            if instance_file_path.suffix != '.json':
                continue

            instance_name = instance_file_path.stem
            total_instance_number += 1

            results_file_path = results_group_directory_path.joinpath(f'{instance_name}_results.json')
            info_file_path = logs_group_directory_path.joinpath(f'{instance_name}_info.json')
            
            # Controlli sull'esistenza dei file relativi all'istanza corrente
            if not results_file_path.exists():
                print(f'Results of instance \'{instance_name}\' does not exists, skipping it.')
                continue
            if not info_file_path.exists():
                print(f'Info of instance \'{instance_name}\' does not exists, skipping it.')
                continue
            
            # Lettura dei dati
            with open(instance_file_path, 'r') as file:
                instance = json.load(file)
            with open(results_file_path, 'r') as file:
                results = json.load(file)
            with open(info_file_path, 'r') as file:
                solver_info = json.load(file)
            
            is_master_instance = 'days' in instance

            # Salvataggio sottoforma di singolo oggetto
            if is_master_instance:
                
                single_pass_master_analysis['instance'].append(f'{instance_name}')
                
                input_analysis = analyze_master_instance(instance)
                for k, v in input_analysis.items():
                    if k not in single_pass_master_analysis:
                        single_pass_master_analysis[k] = []
                    if len(single_pass_master_analysis[k]) != total_instance_number - 1:
                        multiple_keys.add(k)
                    else:
                        single_pass_master_analysis[k].append(v)
                
                results_analysis = analyze_master_results(instance, results)
                for k, v in results_analysis.items():
                    if k not in single_pass_master_analysis:
                        single_pass_master_analysis[k] = []
                    if len(single_pass_master_analysis[k]) != total_instance_number - 1:
                        multiple_keys.add(k)
                    else:
                        single_pass_master_analysis[k].append(v)
                
                for k, v in solver_info.items():
                    if k not in single_pass_master_analysis:
                        single_pass_master_analysis[k] = []
                    if len(single_pass_master_analysis[k]) != total_instance_number - 1:
                        multiple_keys.add(k)
                    else:
                        if type(v) is list:
                            single_pass_master_analysis[k].append(v[0])
                        else:
                            single_pass_master_analysis[k].append(v)
            
            else:
                single_pass_subproblem_analysis['instance'].append(f'{instance_name}')
                
                input_analysis = analyze_subproblem_instance(instance)
                for k, v in input_analysis.items():
                    if k not in single_pass_subproblem_analysis:
                        single_pass_subproblem_analysis[k] = []
                    if len(single_pass_subproblem_analysis[k]) != total_instance_number - 1:
                        multiple_keys.add(k)
                    else:
                        single_pass_subproblem_analysis[k].append(v)
                
                results_analysis = analyze_subproblem_results(instance, results)
                for k, v in results_analysis.items():
                    if k not in single_pass_subproblem_analysis:
                        single_pass_subproblem_analysis[k] = []
                    if len(single_pass_subproblem_analysis[k]) != total_instance_number - 1:
                        multiple_keys.add(k)
                    else:
                        single_pass_subproblem_analysis[k].append(v)
                
                for k, v in solver_info.items():
                    if k not in single_pass_subproblem_analysis:
                        single_pass_subproblem_analysis[k] = []
                    if len(single_pass_subproblem_analysis[k]) != total_instance_number - 1:
                        multiple_keys.add(k)
                    else:
                        single_pass_subproblem_analysis[k].append(v)
                
                true_group_name = group_name.split('-')[-1][3:]
                single_pass_subproblem_analysis['instance'][-1] += f'_{true_group_name}'

print(f'Read data from {total_instance_number} instances in {total_group_number} groups.')

if len(multiple_keys) > 0:
    print(f'Multiple keys found: {multiple_keys}.')

# Eventuale salvataggio dei file di analisi ####################################

if len(single_pass_master_analysis) > 1:
    df = pd.DataFrame(single_pass_master_analysis)
    data_file_path = analysis_directory_path.joinpath('single_pass_master_analysis.xlsx')
    df.to_excel(data_file_path)

if len(single_pass_subproblem_analysis) > 1:
    df = pd.DataFrame(single_pass_subproblem_analysis)

    # Riordinamento colonne
    df = df.reindex([
        'instance', 'avg_tasks_per_patient', 'machines', 'care_units',
        'overlap', 'model', 'status', 'time', 'gap_ratio', 'explored_nodes',
        'best_sol_time', 'rejected', 'served', 'served_task_ratio',
        'lower_bound', 'upper_bound', 'gap', 'best_obj_ratio_dur',
        'best_obj_ratio_root_relax', 'root_relax', 'total_average_duration',
        'total_resources', 'total_capacity', 'average_duration_ratio', 'tasks',
        'avg_services_per_patient', 'total_duration',
        'avg_total_duration_per_patient', 'jobs'], axis=1)

    # Scrittura file Excel
    data_file_path = analysis_directory_path.joinpath('single_pass_subproblem_analysis.xlsx')

    writer = pd.ExcelWriter(data_file_path, engine='xlsxwriter') 
    df.to_excel(writer, sheet_name='Instance Data', index=False, na_rep='NaN')

    workbook  = writer.book
    worksheet = writer.sheets['Instance Data']

    header_format = workbook.add_format({'bold': True, 'align': 'center', 'border': True})
    first_part = workbook.add_format({'bg_color': '#fff2cc'})
    second_part = workbook.add_format({'bg_color': '#d9ead3'})
    third_part = workbook.add_format({'bg_color': '#d0e0e3'})
    line1 = workbook.add_format({'bg_color': '#fff2cc', 'right': True})
    line2 = workbook.add_format({'bg_color': '#d9ead3', 'right': True})

    for column in df:
        column_length = max(df[column].astype(str).map(len).max(), len(column))
        col_idx = df.columns.get_loc(column)
        if col_idx == 0:
            writer.sheets['Instance Data'].set_column(col_idx, col_idx, column_length, header_format)
        elif col_idx < 5:
            writer.sheets['Instance Data'].set_column(col_idx, col_idx, column_length, first_part)
        elif col_idx == 5:
            writer.sheets['Instance Data'].set_column(col_idx, col_idx, column_length, line1)
        elif col_idx < 19:
            writer.sheets['Instance Data'].set_column(col_idx, col_idx, column_length, second_part)
        elif col_idx == 19:
            writer.sheets['Instance Data'].set_column(col_idx, col_idx, column_length, line2)
        elif col_idx <= 28:
            writer.sheets['Instance Data'].set_column(col_idx, col_idx, column_length, third_part)
        else:
            writer.sheets['Instance Data'].set_column(col_idx, col_idx, column_length)

    writer.close()