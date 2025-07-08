from pathlib import Path
import argparse
import json
import yaml
import pandas as pd
import matplotlib.pyplot as plt


def analyze_master_instance(instance):
    '''Ritorna un oggetto con dei parametri relativi all'istanza del master'''

    patient_number = len(instance['patients'])
    day_number = len(instance['days'])
    total_window_number = 0
    total_service_durations = 0
    avg_windows_per_patient = 0
    min_windows_per_patient = 1000
    max_windows_per_patient = 0
    avg_window_size = 0
    min_window_size = 1000
    max_window_size = 0
    avg_overlapping_windows_per_patient = 0
    min_overlapping_windows_per_patient = 1000
    max_overlapping_windows_per_patient = 0

    # Analisi dei pazienti e richieste
    for patient in instance['patients'].values():
        window_number = 0
        overlapping_windows = 0
        
        for service_name, windows in patient['requests'].items():
            window_number += len(windows)

            total_service_durations += instance['services'][service_name]['duration']

            for window in windows:
                window_size = window[1] - window[0] + 1
                
                avg_window_size += window_size
                if window_size < min_window_size: min_window_size = window_size
                if window_size > max_window_size: max_window_size = window_size

                for other_windows in patient['requests'].values():
                    for other_window in other_windows:
                        if (window[0] <= other_window[0] and window[1] >= other_window[0]) or (other_window[0] <= window[0] and other_window[1] >= window[0]):
                            overlapping_windows += 1
        
        avg_overlapping_windows_per_patient += overlapping_windows / 2
        if overlapping_windows < min_overlapping_windows_per_patient: min_overlapping_windows_per_patient = overlapping_windows
        if overlapping_windows > max_overlapping_windows_per_patient: max_overlapping_windows_per_patient = overlapping_windows

        total_window_number += window_number
        avg_windows_per_patient += window_number
        if window_number < min_windows_per_patient: min_windows_per_patient = window_number
        if window_number > max_windows_per_patient: max_windows_per_patient = window_number

    avg_windows_per_patient /= len(instance['patients'])
    avg_window_size /= total_window_number

    total_time_slots = 0
    total_care_unit_number = 0
    min_time_slots_per_care_unit = 1000
    max_time_slots_per_care_unit = 0
    care_unit_names = set()

    # Analisi dei giorni e operatori
    for day in instance['days'].values():

        total_care_unit_number += len(day.keys())

        for care_unit_name, care_unit in day.items():
            care_unit_names.add(care_unit_name)
            care_unit_time_slots = sum(operator['duration'] for operator in care_unit.values())
            total_time_slots += care_unit_time_slots
            if care_unit_time_slots < min_time_slots_per_care_unit: min_time_slots_per_care_unit = care_unit_time_slots
            if care_unit_time_slots > max_time_slots_per_care_unit: max_time_slots_per_care_unit = care_unit_time_slots

    avg_time_slots_per_care_unit = total_time_slots / total_care_unit_number
    
    # Dizionario indicizzato per giorno che contiene la durata totale degli
    # operatori attivi quel giorno
    total_capacity_per_day = {}
    for day_name, day in instance['days'].items():
        total_capacity_per_day[int(day_name)] = sum(operator['duration'] for care_unit in day.values() for operator in care_unit.values())

    avg_requests_in_same_day_per_patient = 0
    min_requests_in_same_day_per_patient = 1000
    max_requests_in_same_day_per_patient = 0

    # Dizionario indicizzato per giorno che contiene la somma delle durate dei
    # servizi che potenzialmente potrebbero essere insteriti quel giorno
    worst_possible_requests_per_day = {i: 0 for i in total_capacity_per_day.keys()}

    for patient in instance['patients'].values():

        # Dizionario indicizzato per giorno che contiene il numero di servizi
        # che il paziente corrente potenzialmente potrebbe richiedere quel
        # giorno
        worst_possible_request_number_per_day = {i: 0 for i in total_capacity_per_day.keys()}
        
        for service_name, windows in patient['requests'].items():
            service_duration = instance['services'][service_name]['duration']
            for window in windows:
                for day_index in range(window[0], window[1] + 1):
                    worst_possible_requests_per_day[day_index] += service_duration
                    worst_possible_request_number_per_day[day_index] += 1
        
        min_value = min(v for v in worst_possible_request_number_per_day.values() if v > 0)
        if min_value < min_requests_in_same_day_per_patient: min_requests_in_same_day_per_patient = min_value
        max_value = max(worst_possible_request_number_per_day.values())
        if max_value > max_requests_in_same_day_per_patient: max_requests_in_same_day_per_patient = max_value
        avg_requests_in_same_day_per_patient += sum(worst_possible_request_number_per_day.values())

    avg_requests_in_same_day_per_patient /= len(instance['patients'].keys())

    request_capacity_ratios = {d: worst_possible_requests_per_day[d] / total_capacity_per_day[d] for d in total_capacity_per_day.keys()}

    return {
        'patient_number': patient_number,
        'day_number': day_number,
        'total_window_number': total_window_number,
        'total_time_slots': total_time_slots,
        'total_demand_vs_disponibility': total_service_durations / total_time_slots,
        'avg_windows_per_patient': avg_windows_per_patient,
        'min_windows_per_patient': min_windows_per_patient,
        'max_windows_per_patient': max_windows_per_patient,
        'avg_window_size': avg_window_size,
        'min_window_size': min_window_size,
        'max_window_size': max_window_size,
        'avg_time_slots_per_care_unit': avg_time_slots_per_care_unit,
        'min_time_slots_per_care_unit': min_time_slots_per_care_unit,
        'max_time_slots_per_care_unit': max_time_slots_per_care_unit,
        'avg_overlapping_windows_per_patient': avg_overlapping_windows_per_patient,
        'min_overlapping_windows_per_patient': min_overlapping_windows_per_patient,
        'max_overlapping_windows_per_patient': max_overlapping_windows_per_patient,
        'avg_demand_vs_disponibility_by_day': sum(request_capacity_ratios.values()) / len(request_capacity_ratios),
        'min_demand_vs_disponibility_by_day': min(request_capacity_ratios.values()),
        'max_demand_vs_disponibility_by_day': max(request_capacity_ratios.values()),
        'avg_requests_in_same_day_per_patient': avg_requests_in_same_day_per_patient,
        'min_requests_in_same_day_per_patient': min_requests_in_same_day_per_patient,
        'max_requests_in_same_day_per_patient': max_requests_in_same_day_per_patient
    }


def analyze_master_results(instance, results):
    '''Ritorna un oggetto con dei parametri relativi ai risultati del master'''

    total_scheduled_service_duration = 0
    avg_scheduled_requests_per_patient_per_day = 0
    min_scheduled_requests_per_patient_per_day = 1000
    max_scheduled_requests_per_patient_per_day = 0

    patient_names = set()
    days_used_by_patients = {}

    for day_name, day_results in results['scheduled'].items():

        patients_request_number = {}

        for request in day_results:

            patient_name = request['patient']
            service_name = request['service']

            patient_names.add(patient_name)
            if patient_name not in days_used_by_patients:
                days_used_by_patients[patient_name] = set()
            days_used_by_patients[patient_name].add(day_name)

            total_scheduled_service_duration += instance['services'][service_name]['duration']

            if patient_name not in patients_request_number:
                patients_request_number[patient_name] = 0
            patients_request_number[patient_name] += 1
        
        avg_scheduled_requests_per_patient_per_day += sum(patients_request_number.values())
        min_patient_request_number = min(patients_request_number.values())
        if min_patient_request_number < min_scheduled_requests_per_patient_per_day: min_scheduled_requests_per_patient_per_day = min_patient_request_number
        max_patient_request_number = max(patients_request_number.values())
        if max_patient_request_number > max_scheduled_requests_per_patient_per_day: max_scheduled_requests_per_patient_per_day = max_patient_request_number
    
    avg_scheduled_requests_per_patient_per_day /= len(patient_names)

    avg_days_used_per_patient = sum(len(d) for d in days_used_by_patients.values()) / len(patient_names)
    min_days_used_per_patient = min(len(d) for d in days_used_by_patients.values())
    max_days_used_per_patient = max(len(d) for d in days_used_by_patients.values())

    total_rejected_service_duration = 0
    for request in results['rejected']:
        service_name = request['service']
        service_duration = instance['services'][service_name]['duration']
        total_rejected_service_duration += service_duration

    return {
        'satisfied_window_number': sum(len(d) for d in results['scheduled'].values()),
        'rejected_window_number': len(results['rejected']),
        'total_scheduled_service_duration': total_scheduled_service_duration,
        'total_rejected_service_duration': total_rejected_service_duration,
        'avg_scheduled_requests_per_patient_per_day': avg_scheduled_requests_per_patient_per_day,
        'min_scheduled_requests_per_patient_per_day': min_scheduled_requests_per_patient_per_day,
        'max_scheduled_requests_per_patient_per_day': max_scheduled_requests_per_patient_per_day,
        'avg_days_used_per_patient': avg_days_used_per_patient,
        'min_days_used_per_patient': min_days_used_per_patient,
        'max_days_used_per_patient': max_days_used_per_patient
    }


def analyze_cores(instance, results, cores):
    '''Ritorna un oggetto con dei parametri relativi ai core'''
    
    return {}


def analyze_adjacent_results(instance, results, prev_results):
    '''Ritorna un oggetto con dei parametri relativi ai risultati del master di
    iterazioni contigue'''

    equal_requests = 0

    for day_name, daily_requests in results['scheduled'].items():
        for request in daily_requests:

            for other_request in prev_results['scheduled'][day_name]:
                if request['patient'] == other_request['patient'] and request['service'] == other_request['service']:
                    equal_requests += 1
    
    return {
        'equal_requests_with_prev_results': equal_requests
    }


def analyze_final_results(instance, results):
    '''Ritorna un oggetto con dei parametri relativi ai risultati finali'''

    analysis = analyze_master_results(instance, results)

    final_analysis = {}
    for key, value in analysis.items():
        final_analysis[f'final_{key}'] = value
    
    return final_analysis


def analyze_subproblem_instance(instance):
    '''Ritorna un oggetto con dei parametri relativi all'istanza del
    sottoproblema'''

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

    return {
        'avg_tasks_per_patient': round(total_requests_number / patient_number),
        'machines': sum(len(care_unit) for care_unit in instance['day'].values()),
        'care_units': care_unit_number,
        'total_resources': care_unit_number,
        'overlap': f'P{int(overlap_percentage * 100)}%',
        'total_capacity': total_operator_duration,
        'jobs': patient_number,
        'total_duration': total_requests_duration,
        'avg_total_duration_per_patient': total_requests_duration / patient_number,
        'avg_services_per_patient': total_requests_number / patient_number,
        'tasks': total_requests_number,
        'total_capacity': total_operator_duration,
        'total_resources': care_unit_number,
        'total_average_duration': total_requests_duration / total_requests_number,
        'average_duration_ratio': sum(duration_ratios) / len(duration_ratios)
    }


def analyze_subproblem_results(instance, results):
    '''Ritorna un oggetto con dei parametri relativi ai risultati del
    sottoproblema'''

    requests_total_number = sum(len(p['requests']) for p in instance['patients'].values())
    requests_total_duration = sum(instance['services'][s]['duration'] for p in instance['patients'].values() for s in p['requests'])
    scheduled_requests_total_duration = sum(instance['services'][r['service']]['duration'] for r in results['scheduled'])
    
    return {
        'rejected': len(results['rejected']),
        'served': len(results['scheduled']),
        'served_task_ratio': len(results['scheduled']) / requests_total_number,
        'best_obj_ratio_dur': scheduled_requests_total_duration / requests_total_duration
    }


def write_excel_sheet(df: pd.DataFrame, writer:pd.ExcelWriter, sheet_name: str, labels_order: list[str]=None):
    '''Funzione che aggiunge un foglio Excel con i dati forniti'''

    # Riordinamento delle colonne
    if labels_order is not None:
        df = df.reindex(labels_order, axis=1)
    
    df.to_excel(writer, sheet_name=sheet_name, index=False, na_rep='NaN')

    # Sistema la larghezza delle colonne
    for column_name, column in df.items():
        column_length = max(column.astype(str).map(len).max(), len(column_name))
        col_idx = df.columns.get_loc(column_name)
        writer.sheets[sheet_name].set_column(col_idx, col_idx, column_length)


# Questo programma può essere chiamato solo dalla linea di comando
if __name__ != '__main__':
    exit(0)

# Argomenti da linea di comando
parser = argparse.ArgumentParser(prog='Iterative analyzer', description='Analyze and plot iterative results.')
parser.add_argument('-c', '--config', type=Path, help='Analyzer configuration', required=True)
parser.add_argument('-r', '--results', type=Path, help='Directory with instance results groups.', required=True)
args = parser.parse_args()

config_file_path = Path(args.config).resolve()
group_directory = Path(args.results).resolve()

# Controlli sulla validità degli argomenti da linea di comando
if not config_file_path.exists():
    raise FileNotFoundError(f'Path \'{config_file_path}\' does not exist.')
if config_file_path.suffix != '.yaml':
    raise FileNotFoundError(f'Path \'{config_file_path}\' is not a YAML file.')
if not group_directory.exists():
    raise FileNotFoundError(f'\'{group_directory}\' does not exist.')
elif not group_directory.is_dir():
    raise FileNotFoundError(f'\'{group_directory}\' is not a directory.')

# Lettura del file di configurazione
with open(config_file_path, 'r') as file:
    config = yaml.load(file, yaml.Loader)

# Liste di oggetti che conterranno una entry per ogni istanza e iterazione
# analizzata
iterative_analysis = []
iterative_subproblem_analysis = []

for solving_directory in group_directory.iterdir():
    group_name = solving_directory.name
    
    if not solving_directory.is_dir() or group_name == 'analysis' or group_name == 'plots':
        continue

    # Eventuale scarto di alcuni gruppi
    if 'groups_to_do' in config and 'all' not in config['groups_to_do'] and group_name not in config['groups_to_do']:
        continue
    if 'groups_to_avoid' in config and group_name in config['groups_to_avoid']:
        continue

    input_directory = solving_directory.joinpath('input')
    results_directory = solving_directory.joinpath('results')
    logs_directory = solving_directory.joinpath('logs')
    cores_directory = solving_directory.joinpath('cores')

    # Considera come istanza master il primo file JSON che si incontra
    master_instance_file = None
    for file_path in input_directory.iterdir():
        if file_path.suffix == '.json':
            master_instance_file = file_path
            break
    with open(master_instance_file, 'r') as file:
        master_instance = json.load(file)

    instance_name = '_'.join(group_name.split('_')[-2:])

    # Analizza tutte le iterazioni
    for iteration_input_directory in input_directory.iterdir():
        if not iteration_input_directory.is_dir():
            continue

        iteration_directory_name = iteration_input_directory.name
        iteration_index = int(iteration_directory_name.removeprefix('iter_'))
        prev_iteration_directory_name = f'iter_{iteration_index - 1}'

        file_names = {
            'master_results': results_directory.joinpath(iteration_directory_name).joinpath('master_results.json'),
            'final_results': results_directory.joinpath(iteration_directory_name).joinpath('final_results.json'),
            'cores': cores_directory.joinpath(f'iter_{iteration_index}_cores.json'),
            'master_solver_info': logs_directory.joinpath(iteration_directory_name).joinpath('master_info.json'),
            'core_info': logs_directory.joinpath(iteration_directory_name).joinpath('core_info.json'),
            'sol_perm_info': logs_directory.joinpath(iteration_directory_name).joinpath('sol_perm_info.json'),
            'prev_master_results': results_directory.joinpath(prev_iteration_directory_name).joinpath('master_results.json')
        }

        # Leggi le informazioni grezze da tutti i file necessari
        raw_data = {}
        for name, path in file_names.items():
            
            if name == 'prev_master_results' and iteration_index == 0:
                continue

            if not path.exists():
                print(f'\'{name}\' does not exists in group \'{group_name}\' and iteration {iteration_index}')
                continue

            with open(path, 'r') as file:
                raw_data[name] = json.load(file)
        
        # Costruisci l'oggetto con tutte le informazioni dell'iterazione
        # corrente
        analysis_row = {}
        analysis_row['instance'] = instance_name
        analysis_row['group'] = group_name
        analysis_row['iteration'] = iteration_index

        for k, v in analyze_master_instance(master_instance).items():
            analysis_row[k] = v

        if 'master_results' in raw_data:
            for k, v in analyze_master_results(master_instance, raw_data['master_results']).items():
                analysis_row[k] = v

        if 'final_results' in raw_data:
            for k, v in analyze_final_results(master_instance, raw_data['final_results']).items():
                analysis_row[k] = v
        
        if 'master_results' in raw_data and 'cores' in raw_data:
            for k, v in analyze_cores(master_instance, raw_data['master_results'], raw_data['cores']).items():
                analysis_row[k] = v
        
        if 'master_results' in raw_data and 'prev_master_results' in raw_data:
            for k, v in analyze_adjacent_results(master_instance, raw_data['master_results'], raw_data['prev_master_results']).items():
                analysis_row[k] = v

        for name in ['master_solver_info', 'core_info', 'sol_perm_info']:
            if name in raw_data:
                for k, v in raw_data[name].items():
                    analysis_row[k] = v
        
        iterative_analysis.append(analysis_row)
        
        # Analizza tutti i sottoproblemi dell'iterazione corrente
        for subproblem_instance_file in iteration_input_directory.iterdir():
            if subproblem_instance_file.suffix != '.json':
                continue

            day_name = subproblem_instance_file.stem.removeprefix('subproblem_day_')

            file_names = {
                'subproblem_instance': subproblem_instance_file,
                'subproblem_results': results_directory.joinpath(iteration_directory_name).joinpath(f'subproblem_day_{day_name}_results.json'),
                'subproblem_solver_info': logs_directory.joinpath(iteration_directory_name).joinpath(f'subproblem_info_day_{day_name}.json'),
            }

            # Leggi le informazioni grezze da tutti i file necessari
            raw_data = {}
            for name, path in file_names.items():
                
                if not path.exists():
                    print(f'\'{name}\' does not exists in group \'{group_name}\' and iteration {iteration_index}')
                    continue

                with open(path, 'r') as file:
                    raw_data[name] = json.load(file)
            
            # Costruisci l'oggetto con tutte le informazioni dell'iterazione
            # corrente
            analysis_row = {}
            analysis_row['instance'] = instance_name
            analysis_row['group'] = group_name
            analysis_row['iteration'] = iteration_index
            analysis_row['day'] = int(day_name)

            if 'subproblem_instance' in raw_data:
                for k, v in analyze_subproblem_instance(raw_data['subproblem_instance']).items():
                    analysis_row[k] = v

            if 'subproblem_results' in raw_data and 'subproblem_instance' in raw_data:
                for k, v in analyze_subproblem_results(raw_data['subproblem_instance'], raw_data['subproblem_results']).items():
                    analysis_row[k] = v
        
            if 'subproblem_solver_info' in raw_data:
                for k, v in raw_data['subproblem_solver_info'].items():
                    analysis_row[k] = v
            
            iterative_subproblem_analysis.append(analysis_row)

if len(iterative_analysis) == 0 and len(iterative_subproblem_analysis) == 0:
    raise ValueError('No data found to analyze.')
print(f'Analyzed {len(iterative_analysis)} master entries, {len(iterative_subproblem_analysis)} subproblem entries.')

df = pd.DataFrame(iterative_analysis)
subproblem_df = pd.DataFrame(iterative_subproblem_analysis)

# Assegna None per ogni chiave mancante in qualche riga
key_names = set(key for row in iterative_analysis for key in row.keys())
for row in iterative_analysis:
    for key_name in key_names:
        if key_name not in row:
            row[key_name] = None

# Assegna None per ogni chiave mancante in qualche riga
key_names = set(key for row in iterative_subproblem_analysis for key in row.keys())
for row in iterative_subproblem_analysis:
    for key_name in key_names:
        if key_name not in row:
            row[key_name] = None

# SALVATAGGIO EXCEL ############################################################

if 'save_excel' in config and config['save_excel']:

    # Eventuale creazione della cartella di analisi
    analysis_directory_path = group_directory.joinpath('analysis')
    if not analysis_directory_path.exists():
        analysis_directory_path.mkdir()
        print('\'analysis\' directory does not exist, created it.')

    # Scrittura su file del documento Excel
    data_file_path = analysis_directory_path.joinpath('iterative_analysis.xlsx')
    with pd.ExcelWriter(data_file_path, engine='xlsxwriter') as writer:

        if len(iterative_analysis) > 0:
            write_excel_sheet(df, writer, 'Master Data')
        
        if len(iterative_subproblem_analysis) > 0:
            write_excel_sheet(subproblem_df, writer, 'Subproblem Data')

# PLOTTING #####################################################################

# Eventuale creazione della cartella di plot
plots_directory_path = group_directory.joinpath('plots')
if not plots_directory_path.exists():
    plots_directory_path.mkdir()
    print('\'plots\' directory does not exist, created it.')




if 'plots' in config and ('all' in config['plots'] or 'average_requests_per_patient' in config['plots']):
    print('Making average_requests_per_patient...')
    gfig, gax = plt.subplots()
    for group, data in df.groupby('group'):
        fig, ax = plt.subplots()

        if len(data) > 100:
            lw = 0.5
            ms = 0.5
            ax.set_xticks([])
            gax.set_xticks([])
        else:
            lw = 1
            ms = 2
        
        ax.plot(data['iteration'], data['satisfied_window_number'] / data['patient_number'], 'o', linewidth=lw, markersize=ms, label='master')
        ax.plot(data['iteration'], data['final_satisfied_window_number'] / data['patient_number'], 'x', linewidth=lw, markersize=ms, label='final')
        gax.plot(data['iteration'], data['satisfied_window_number'] / data['patient_number'], 'o', linewidth=lw, markersize=ms, label=f'{group}_master')
        gax.plot(data['iteration'], data['final_satisfied_window_number'] / data['patient_number'], 'x', linewidth=lw, markersize=ms, label=f'{group}_final')
        
        ax.set_xlabel('Iteration')
        ax.set_ylabel('Requests per patient')
        ax.set_title('Average requests per patient by iteration')
        ax.legend()

        fig.tight_layout()
        fig.savefig(plots_directory_path.joinpath(f'{group}_average_requests_per_patient.png'))

    gax.set_xlabel('Iteration')
    gax.set_ylabel('Requests per patient')
    gax.set_title('Average requests per patient by iteration')
    gax.legend()

    gfig.tight_layout()
    gfig.savefig(plots_directory_path.joinpath(f'average_requests_per_patient.png'))
    plt.close('all')



if 'plots' in config and ('all' in config['plots'] or 'core_number_by_day' in config['plots']):
    print('Making core_number_by_day...')
    gfig, gaxs = plt.subplots(2)
    for group, data in df.groupby('group'):
        fig, axs = plt.subplots(2)

        if len(data) > 100:
            lw = 0.5
            ms = 0.5
            axs[0].set_xticks([])
            axs[1].set_xticks([])
            gaxs[0].set_xticks([])
            gaxs[1].set_xticks([])
        else:
            lw = 1
            ms = 2
        
        axs[0].plot(data['iteration'], data['percentage_of_core_equal_to_master_request'], 'o', linewidth=lw, markersize=ms)
        axs[1].plot(data['iteration'], data['average_percentage_of_core_done_by_subproblem'], 'o', linewidth=lw, markersize=ms)
        gaxs[0].plot(data['iteration'], data['percentage_of_core_equal_to_master_request'], 'o', linewidth=lw, markersize=ms, label=group)
        gaxs[1].plot(data['iteration'], data['average_percentage_of_core_done_by_subproblem'], 'o', linewidth=lw, markersize=ms, label=group)
        
        axs[0].set_ylabel('Percentage')
        axs[0].set_title('When core is equal to master request')
        axs[1].set_xlabel('Iteration')
        axs[1].set_ylabel('Percentage')
        axs[1].set_title('Average ratio of core size in respect to full MP request')

        fig.tight_layout()
        fig.savefig(plots_directory_path.joinpath(f'{group}_core_number_by_day.png'))

    gaxs[0].set_ylabel('Percentage')
    gaxs[0].set_title('When core is equal to master request')
    gaxs[0].legend()
    gaxs[1].set_xlabel('Iteration')
    gaxs[1].set_ylabel('Percentage')
    gaxs[1].set_title('Average ratio of core size in respect to full MP request')
    gaxs[1].legend()

    gfig.tight_layout()
    gfig.savefig(plots_directory_path.joinpath(f'core_number_by_day.png'))
    plt.close('all')



if 'plots' in config and ('all' in config['plots'] or 'core_expansion' in config['plots']):
    print('Making core_expansion...')
    gfig, gaxs = plt.subplots(2)
    for group, data in df.groupby('group'):
        fig, axs = plt.subplots(2)

        if len(data) > 100:
            lw = 0.5
            ms = 0.5
            axs[0].set_xticks([])
            axs[1].set_xticks([])
            gaxs[0].set_xticks([])
            gaxs[1].set_xticks([])
        else:
            lw = 1
            ms = 2
        
        axs[0].plot(data['iteration'], data['core_number_pre_expansion'], 'o', linewidth=lw, markersize=ms, label='pre expansion')
        axs[0].plot(data['iteration'], data['core_number_post_name_expansion'], 'x', linewidth=lw, markersize=ms, label='post expansion')
        axs[1].plot(data['iteration'], data['average_core_size_pre_expansion'], 'o', linewidth=lw, markersize=ms, label='pre expansion')
        axs[1].plot(data['iteration'], data['average_core_size_post_name_expansion'], 'x', linewidth=lw, markersize=ms, label='post expansion')
        gaxs[0].plot(data['iteration'], data['core_number_pre_expansion'], 'o', linewidth=lw, markersize=ms, label=f'{group}_pre expansion')
        gaxs[0].plot(data['iteration'], data['core_number_post_name_expansion'], 'x', linewidth=lw, markersize=ms, label=f'{group}_post expansion')
        gaxs[1].plot(data['iteration'], data['average_core_size_pre_expansion'], 'o', linewidth=lw, markersize=ms, label=f'{group}_pre expansion')
        gaxs[1].plot(data['iteration'], data['average_core_size_post_name_expansion'], 'x', linewidth=lw, markersize=ms, label=f'{group}_post expansion')

        axs[0].set_ylabel('Average core number')
        axs[0].set_title('Cores pre and post expansion')
        axs[0].legend()
        axs[1].set_xlabel('Iteration')
        axs[1].set_ylabel('Average core size')
        axs[1].legend()

        fig.tight_layout()
        fig.savefig(plots_directory_path.joinpath(f'{group}_core_expansion.png'))

    gaxs[0].set_ylabel('Average core number')
    gaxs[0].set_title('Cores pre and post expansion')
    gaxs[0].legend()
    gaxs[1].set_xlabel('Iteration')
    gaxs[1].set_ylabel('Average core size')
    gaxs[1].legend()

    gfig.tight_layout()
    gfig.savefig(plots_directory_path.joinpath(f'core_expansion.png'))
    plt.close('all')






if 'plots' in config and ('all' in config['plots'] or 'fully_scheduled_days' in config['plots']):
    print('Making fully_scheduled_days...')
    max_data_len = 0
    max_day_number = 0

    gfig, gaxs = plt.subplots(2)
    for group, data in df.groupby('group'):
        fig, axs = plt.subplots(2)

        if len(data) > max_data_len:
            max_data_len = len(data)

        if len(data) > 100:
            lw = 0.5
            ms = 0.5
            axs[0].set_xticks([])
            axs[1].set_xticks([])
            gaxs[0].set_xticks([])
            gaxs[1].set_xticks([])
        else:
            lw = 1
            ms = 2
        
        day_number = data['day_number'].max()
        if day_number > max_day_number:
            max_day_number = day_number
        
        subproblems_completely_solved = subproblem_df[(subproblem_df['group'] == group) & (subproblem_df['rejected'] == 0)].groupby('iteration').count()[['rejected']]

        axs[0].plot(data['iteration'], data['satisfied_window_number'] - data['final_satisfied_window_number'], 'o', linewidth=lw, markersize=ms)
        axs[0].plot([0, len(data) - 1], [day_number + 1, day_number + 1], 'r--')
        axs[0].text(0, day_number - 2, 'Day number', color='r')
        axs[1].plot(subproblems_completely_solved.index, subproblems_completely_solved['rejected'] / day_number, 'o', linewidth=lw, markersize=ms)
        gaxs[0].plot(data['iteration'], data['satisfied_window_number'] - data['final_satisfied_window_number'], 'o', linewidth=lw, markersize=ms, label=group)
        gaxs[1].plot(subproblems_completely_solved.index, subproblems_completely_solved['rejected'] / day_number, 'o', linewidth=lw, markersize=ms, label=group)
        
        axs[0].set_xlabel('Iteration')
        axs[0].set_ylabel('Rejected request number')
        axs[0].set_title('Number of rejected requests per iteration')
        axs[1].set_xlabel('Iteration')
        axs[1].set_ylabel('Percentage')
        axs[1].set_title('Percentage of days fully satisfied per iteration')
        axs[1].set_ylim([0, 1])

        fig.tight_layout()
        fig.savefig(plots_directory_path.joinpath(f'{group}_fully_scheduled_days.png'))

    gaxs[0].plot([0, max_data_len - 1], [max_day_number + 1, max_day_number + 1], 'r--')
    gaxs[0].text(0, max_day_number - 2, 'Day number', color='r')

    gaxs[0].set_xlabel('Iteration')
    gaxs[0].set_ylabel('Rejected request number')
    gaxs[0].set_title('Number of rejected requests per iteration')
    gaxs[1].set_xlabel('Iteration')
    gaxs[1].set_ylabel('Percentage')
    gaxs[1].set_title('Percentage of days fully satisfied per iteration')
    gaxs[1].set_ylim([0, 1])
    gaxs[1].legend()

    gfig.tight_layout()
    gfig.savefig(plots_directory_path.joinpath(f'fully_scheduled_days.png'))
    plt.close('all')





if 'plots' in config and ('all' in config['plots'] or 'likeness_between_iterations' in config['plots']):
    print('Making likeness_between_iterations...')
    gfig, gaxs = plt.subplots(2)
    for group, data in df.groupby('group'):
        fig, axs = plt.subplots(2)

        if len(data) > 100:
            lw = 0.5
            ms = 0.5
            axs[0].set_xticks([])
            axs[1].set_xticks([])
            gaxs[0].set_xticks([])
            gaxs[1].set_xticks([])
        else:
            lw = 1
            ms = 2
        
        axs[0].plot(data['iteration'], data['equal_requests_with_prev_results'] / data['satisfied_window_number'], 'o', linewidth=lw, markersize=ms, label='equal requests')
        axs[1].plot(data['iteration'], data['satisfied_window_number'], 'o', linewidth=lw, markersize=ms, label='total master requests')
        axs[1].plot(data['iteration'], data['equal_requests_with_prev_results'], 'o', linewidth=lw, markersize=ms, label='equal requests')
        gaxs[0].plot(data['iteration'], data['equal_requests_with_prev_results'] / data['satisfied_window_number'], 'o', linewidth=lw, markersize=ms, label=f'{group}_equal requests')
        gaxs[1].plot(data['iteration'], data['satisfied_window_number'], 'o', linewidth=lw, markersize=ms, label=f'{group}_total master requests')
        gaxs[1].plot(data['iteration'], data['equal_requests_with_prev_results'], 'o', linewidth=lw, markersize=ms, label=f'{group}_equal requests')

        axs[0].set_ylabel('Percentage of equal requests')
        axs[0].set_title('Equal requests between consecutive iterations')
        axs[0].legend()
        axs[0].set_xlim((0, None))
        axs[1].set_xlabel('Iteration')
        axs[1].set_ylabel('Number of equal requests')
        axs[1].legend()

        fig.tight_layout()
        fig.savefig(plots_directory_path.joinpath(f'{group}_likeness_between_iterations.png'))

    gaxs[0].set_ylabel('Percentage of equal requests')
    gaxs[0].set_title('Equal requests between consecutive iterations')
    gaxs[0].legend()
    gaxs[1].set_xlabel('Iteration')
    gaxs[1].set_ylabel('Number of equal requests')
    gaxs[1].legend()

    gfig.tight_layout()
    gfig.savefig(plots_directory_path.joinpath(f'likeness_between_iterations.png'))
    plt.close('all')





if 'plots' in config and ('all' in config['plots'] or 'model_components' in config['plots']):
    print('Making model_components...')
    gfig, gax = plt.subplots()
    for group, data in df.groupby('group'):
        fig, ax = plt.subplots()

        if len(data) > 100:
            lw = 0.5
            ms = 0.5
            ax.set_xticks([])
            gax.set_xticks([])
        else:
            lw = 1
            ms = 2
        
        ax.plot(data['iteration'], data['initial_constraints'], 'o-', linewidth=lw, markersize=ms, label='constraints')
        ax.plot(data['iteration'], data['initial_variables'], 'x-', linewidth=lw, markersize=ms, label='variables')
        ax.plot(data['iteration'], data['presolved_constraints'], 'o-', linewidth=lw, markersize=ms, label='presolved constraints')
        ax.plot(data['iteration'], data['presolved_variables'], 'x-', linewidth=lw, markersize=ms, label='presolved variables')
        gax.plot(data['iteration'], data['initial_constraints'], 'o-', linewidth=lw, markersize=ms, label=f'{group}_constraints')
        gax.plot(data['iteration'], data['initial_variables'], 'x-', linewidth=lw, markersize=ms, label=f'{group}_variables')
        gax.plot(data['iteration'], data['presolved_constraints'], 'o-', linewidth=lw, markersize=ms, label=f'{group}_presolved constraints')
        gax.plot(data['iteration'], data['presolved_variables'], 'x-', linewidth=lw, markersize=ms, label=f'{group}_presolved variables')
        
        ax.set_xlabel('Iteration')
        ax.set_ylabel('Number of components')
        ax.set_title('Variable and constraint number of the master model')
        ax.legend()

        fig.tight_layout()
        fig.savefig(plots_directory_path.joinpath(f'{group}_model_components.png'))

    gax.set_xlabel('Iteration')
    gax.set_ylabel('Number of components')
    gax.set_title('Variable and constraint number of the master model')
    gax.legend()

    gfig.tight_layout()
    gfig.savefig(plots_directory_path.joinpath(f'model_components.png'))
    plt.close('all')




if 'plots' in config and ('all' in config['plots'] or 'patient_accesses' in config['plots']):
    print('Making patient_accesses...')
    max_data_len = 0
    max_day_number = 0

    gfig, gax = plt.subplots()
    for group, data in df.groupby('group'):
        fig, ax = plt.subplots()

        if len(data) > max_data_len:
            max_data_len = len(data)

        if len(data) > 100:
            lw = 0.5
            ms = 0.5
            ax.set_xticks([])
            gax.set_xticks([])
        else:
            lw = 1
            ms = 2
        
        day_number = data['day_number'].max()
        if day_number > max_day_number:
            max_day_number = day_number
        
        ax.plot(data['iteration'], data['avg_days_used_per_patient'], 'o-', linewidth=lw, markersize=ms, label='avg')
        ax.plot(data['iteration'], data['min_days_used_per_patient'], 'o-', linewidth=lw, markersize=ms, label='min')
        ax.plot(data['iteration'], data['max_days_used_per_patient'], 'o-', linewidth=lw, markersize=ms, label='max')
        ax.plot([0, len(data) - 1], [day_number + 1, day_number + 1], 'r--')
        ax.text(0, day_number - 2, 'Day number', color='r')
        gax.plot(data['iteration'], data['avg_days_used_per_patient'], 'o-', linewidth=lw, markersize=ms, label=f'{group}_avg')
        gax.plot(data['iteration'], data['min_days_used_per_patient'], 'o-', linewidth=lw, markersize=ms, label=f'{group}_min')
        gax.plot(data['iteration'], data['max_days_used_per_patient'], 'o-', linewidth=lw, markersize=ms, label=f'{group}_max')
        
        ax.set_xlabel('Iteration')
        ax.set_ylabel('Days used')
        ax.set_title('Average days used per patient per iteration')
        ax.legend()

        fig.tight_layout()
        fig.savefig(plots_directory_path.joinpath(f'{group}_patient_accesses.png'))

    gax.plot([0, max_data_len - 1], [max_day_number + 1, max_day_number + 1], 'r--')
    gax.text(0, max_day_number - 2, 'Day number', color='r')

    gax.set_xlabel('Iteration')
    gax.set_ylabel('Days used')
    gax.set_title('Average days used per patient per iteration')
    gax.legend()

    gfig.tight_layout()
    gfig.savefig(plots_directory_path.joinpath(f'patient_accesses.png'))
    plt.close('all')




if 'plots' in config and ('all' in config['plots'] or 'time_slots' in config['plots']):
    print('Making time_slots...')
    gfig, gaxs = plt.subplots(2)
    for group, data in df.groupby('group'):
        fig, axs = plt.subplots(2)

        if len(data) > 100:
            lw = 0.5
            ms = 0.5
            axs[0].set_xticks([])
            axs[1].set_xticks([])
            gaxs[0].set_xticks([])
            gaxs[1].set_xticks([])
        else:
            lw = 1
            ms = 2
        
        axs[0].plot(data['iteration'], data['total_scheduled_service_duration'], 'go-', linewidth=lw, markersize=ms, label='scheduled')
        axs[0].plot(data['iteration'], data['total_time_slots'], '-', linewidth=lw, markersize=ms, label='total capacity')
        axs[1].plot(data['iteration'], data['total_rejected_service_duration'], 'rx-', linewidth=lw, markersize=ms)
        gaxs[0].plot(data['iteration'], data['total_scheduled_service_duration'], 'go-', linewidth=lw, markersize=ms, label=f'{group}_scheduled')
        gaxs[0].plot(data['iteration'], data['total_time_slots'], '-', linewidth=lw, markersize=ms, label=f'{group}_total capacity')
        gaxs[1].plot(data['iteration'], data['total_rejected_service_duration'], 'rx-', linewidth=lw, markersize=ms, label=group)

        axs[0].set_ylabel('Time slots')
        axs[0].set_title('Time slots requested')
        axs[0].legend()
        axs[1].set_xlabel('Iteration')
        axs[1].set_ylabel('Time slots')
        axs[1].set_title('Time slots rejected')

        fig.tight_layout()
        fig.savefig(plots_directory_path.joinpath(f'{group}_time_slots.png'))

    gaxs[0].set_ylabel('Time slots')
    gaxs[0].set_title('Time slots requested')
    gaxs[0].legend()
    gaxs[1].set_xlabel('Iteration')
    gaxs[1].set_ylabel('Time slots')
    gaxs[1].set_title('Time slots rejected')

    gfig.tight_layout()
    gfig.savefig(plots_directory_path.joinpath(f'time_slots.png'))
    plt.close('all')



if 'plots' in config and ('all' in config['plots'] or 'solving_times' in config['plots']):
    print('Making solving_times...')
def plot_subproblem_cumulative_times(all_master_results_info, all_subproblem_results_info, plot_file_path):

    time = 0
    xmas = []
    ymas = []
    xsub = []
    ysub = []

    for iteration_index, master_results_info in enumerate(all_master_results_info):

        time += master_results_info['model_solving_time']
        xmas.append(time)
        ymas.append(master_results_info['objective_function_value'])

        if iteration_index >= len(all_subproblem_results_info):
            continue

        objective_function_value_sum = 0
        for subproblem_results_info in all_subproblem_results_info[iteration_index].values():
            time += subproblem_results_info['model_solving_time']
            objective_function_value_sum += subproblem_results_info['objective_function_value']
        
        xsub.append(time)
        ysub.append(objective_function_value_sum)

    _, ax = plt.subplots()
    
    ax.plot(xmas, ymas, 'o-', label='master')
    if len(xsub) > 0:
        ax.plot(xsub, ysub, 'x-', label='subproblem')
        ax.set_xlim(xmin=0, xmax=(xsub[-1] + 0.5))
    ax.legend()

    plt.title(f'Cumulated objective function value')
    plt.xlabel('Time (s)')
    plt.ylabel('Objective function value')

    plt.savefig('solving_times.png')
    plt.close('all')