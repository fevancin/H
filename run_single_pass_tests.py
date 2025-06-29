from datetime import datetime
from pathlib import Path
import json
import time
import yaml
import shutil
import pyomo.environ as pyo
import jsbeautifier
import argparse
import copy

from checkers.master_instance_checker import check_master_instance
from checkers.master_results_checker import check_master_results
from checkers.subproblem_instance_checker import check_subproblem_instance
from checkers.subproblem_results_checker import check_subproblem_results
from checkers.final_results_checker import check_final_results

from milp_models.monolithic_model import get_monolithic_model, get_results_from_monolithic_model
from milp_models.master_model import get_slim_master_model, get_results_from_slim_master_model
from milp_models.master_model import get_fat_master_model, get_results_from_fat_master_model
from milp_models.subproblem_model import get_fat_subproblem_model, get_results_from_fat_subproblem_model
from milp_models.subproblem_model import get_slim_subproblem_model, get_results_from_slim_subproblem_model

from milp_models.solve_instance import get_solver_info


# Questo programma può essere chiamato solo dalla linea di comando
if __name__ != '__main__':
    exit(0)

# Argomenti da linea di comando
parser = argparse.ArgumentParser(prog='Run single-pass tests', description='Solve groups of instances.')
parser.add_argument('-c', '--config', type=Path, help='Solving configuration', required=True)
parser.add_argument('-i', '--input', type=Path, help='Directory with instance groups.', required=True)
parser.add_argument('-o', '--output', type=Path, help='Directory where outputting results.', required=True)
args = parser.parse_args()

configs_file_path = Path(args.config).resolve()
groups_input_directory_path = Path(args.input).resolve()
output_directory_path = Path(args.output).resolve()

# Controlli sulla validità degli argomenti da linea di comando
if not configs_file_path.exists():
    raise FileNotFoundError(f'Path \'{configs_file_path}\' does not exist.')
if configs_file_path.suffix != '.yaml':
    raise FileNotFoundError(f'Path \'{configs_file_path}\' is not a YAML file.')
if not groups_input_directory_path.exists():
    raise FileNotFoundError(f'Path \'{groups_input_directory_path}\' does not exist.')
elif not groups_input_directory_path.is_dir():
    raise FileNotFoundError(f'Path \'{groups_input_directory_path}\' is not a directory.')
if output_directory_path.suffix != '':
    raise FileNotFoundError(f'Path \'{output_directory_path}\' is not a directory.')

# Eventuale creazione della cartella di output
if not output_directory_path.exists():
    output_directory_path.mkdir()
    print(f'Created output directory {output_directory_path}.')

# Lettura del file di configurazione
with open(configs_file_path, 'r') as file:
    configs = yaml.load(file, yaml.Loader)

total_instance_number = 0

print('---')

# Controlli iniziali sul numero di istanze e gruppi coinvolti (aiutano a
# verificare che non ci siano errori nella configurazione)
if len(configs['groups']) == 0:
    print('WARNiNG: the configuration does not have anything in the \'groups\' object.')
for config_name, config_changes in configs['groups'].items():

    # Copia della configurazione di base con sovrascrittura del gruppo corrente
    config = copy.deepcopy(configs['base'])
    for config_changes_key, config_changes_value in config_changes.items():
        if type(config_changes_value) is list:
            config[config_changes_key].extend(config_changes_value)
        else:
            config[config_changes_key] = config_changes_value
    
    group_number = 0
    group_names = []
    total_config_instance_number = 0

    for group_input_directory_path in groups_input_directory_path.iterdir():
        if not group_input_directory_path.is_dir():
            continue

        group_name = group_input_directory_path.name

        # Eventuale scarto di alcuni gruppi
        if 'groups_to_do' in config and 'all' not in config['groups_to_do'] and group_name not in config['groups_to_do']:
            continue
        if 'groups_to_avoid' in config and group_name in config['groups_to_avoid']:
            continue

        group_number += 1
        group_names.append(group_name)

        # Conta del numero di istanze nel gruppo
        for input_instance_file_path in group_input_directory_path.iterdir():
            if input_instance_file_path.suffix != '.json':
                continue
            total_config_instance_number += 1
    
    if group_number == 0:
        print(f'WARNING: the configuration \'{config_name}\' does not have any valid instance groups.')
    else:
        group_names_string = ', '.join(group_names)
        print(f'The configuration \'{config_name}\' will be applied to {group_number} instance groups: [{group_names_string}].')
        print(f'{total_config_instance_number} total instance number will be solved by configuration \'{config_name}\'.')

    total_instance_number += total_config_instance_number

print('---')

instance_index = 0
total_group_number = 0

# Esecuzione di ogni tipologia di risoluzione presente nella configurazione
for config_name, config_changes in configs['groups'].items():

    # Copia della configurazione di base con sovrascrittura del gruppo corrente
    config = copy.deepcopy(configs['base'])
    for config_changes_key, config_changes_value in config_changes.items():
        if type(config_changes_value) is list:
            if config_changes_key not in config:
                config[config_changes_key] = []
            config[config_changes_key].extend(config_changes_value)
        else:
            config[config_changes_key] = config_changes_value

    # Risolvi i gruppi di istanze
    for group_input_directory_path in groups_input_directory_path.iterdir():
        if not group_input_directory_path.is_dir():
            continue

        group_name = group_input_directory_path.name

        # Eventuale scarto di alcuni gruppi
        if 'groups_to_do' in config and 'all' not in config['groups_to_do'] and group_name not in config['groups_to_do']:
            continue
        if 'groups_to_avoid' in config and group_name in config['groups_to_avoid']:
            continue

        # Creazione delle cartelle necessarie alla risoluzione
        group_directory_path = output_directory_path.joinpath(f'{group_name}_{config_name}')
        if group_directory_path.exists():
            shutil.rmtree(group_directory_path)
        group_directory_path.mkdir()

        input_directory_path = group_directory_path.joinpath('input')
        input_directory_path.mkdir()

        results_directory_path = group_directory_path.joinpath('results')
        results_directory_path.mkdir()

        logs_directory_path = group_directory_path.joinpath('logs')
        logs_directory_path.mkdir()
        
        # Copia del file di configurazione corrente
        config_file_path = group_directory_path.joinpath('solver_config.yaml')
        with open(config_file_path, 'w') as file:
            yaml.dump(config, file, default_flow_style=False, sort_keys=False)
        
        total_group_number += 1

        # Risoluzione delle istanze
        for input_instance_file_path in group_input_directory_path.iterdir():
            if input_instance_file_path.suffix != '.json':
                continue

            # Input dell'istanza corrente
            with open(input_instance_file_path, 'r') as file:
                instance = json.load(file)
            
            is_master_instance = 'days' in instance

            # Controllo sulla coerenza dell'istanza con il problema da risolvere
            if config['model'] in ['fat-subproblem', 'slim-subproblem'] and is_master_instance:
                raise ValueError(f'\'{input_instance_file_path}\' is not a subproblem instance')
            if config['model'] not in ['fat-subproblem', 'slim-subproblem'] and not is_master_instance:
                raise ValueError(f'\'{input_instance_file_path}\' is not a master instance')

            # Controlli sulla correttezza dell'input
            if config['checks_throw_exceptions']:
                if is_master_instance:
                    check_master_instance(instance)
                else:
                    check_subproblem_instance(instance)
            else:
                try:
                    if is_master_instance:
                        check_master_instance(instance)
                    else:
                        check_subproblem_instance(instance)
                except Exception as exception:
                    print(exception)

            # Copia dell'istanza di input nella cartella dei risultati
            instance_file_path = input_directory_path.joinpath(input_instance_file_path.name)
            with open(instance_file_path, 'w') as file:
                file.write(jsbeautifier.beautify(json.dumps(instance)))
            
            instance_index += 1

            print(f'Solving instance \'{instance_file_path.stem}\' of group \'{group_input_directory_path.name}\' with config \'{config_name}\' ({instance_index}/{total_instance_number})')
            total_start_time = time.perf_counter()

            print(f'Model creation... ', end='')
            model_creation_start_time = time.perf_counter()

            # Creazione del modello
            if config['model'] == 'monolithic':
                model = get_monolithic_model(instance, config['additional_info'])
            elif config['model'] == 'slim-master':
                model = get_slim_master_model(instance, config['additional_info'])
            elif config['model'] == 'fat-master':
                model = get_fat_master_model(instance, config['additional_info'])
            elif config['model'] == 'fat-subproblem':
                model = get_fat_subproblem_model(instance, config['additional_info'])
            elif config['model'] == 'slim-subproblem':
                model = get_slim_subproblem_model(instance, config['additional_info'])

            model_creation_end_time = time.perf_counter()
            print(f'ended ({round(model_creation_end_time - model_creation_start_time, 4)}s). ', end='')

            opt = pyo.SolverFactory(config['solver_config']['solver'])

            if 'time_limit' in config['solver_config']:
                if config['solver_config']['solver'] == 'glpk':
                    opt.options['tmlim'] = config['solver_config']['time_limit']
                elif config['solver_config']['solver'] == 'gurobi':
                    opt.options['TimeLimit'] = config['solver_config']['time_limit']
            if 'max_memory' in config['solver_config']:
                opt.options['SoftMemLimit'] = config['solver_config']['max_memory']

            log_file_path = logs_directory_path.joinpath(f'{instance_file_path.stem}_log.log')
            
            print(f'Solving... ', end='')
            solving_start_time = time.perf_counter()
            
            # Risoluzione dell'istanza
            model_results = opt.solve(model, tee=False, logfile=log_file_path)
            
            solving_end_time = time.perf_counter()
            print(f'ended ({round(solving_end_time - solving_start_time, 4)}s).')

            # Ottenimento dei dati del solver
            model.solutions.store_to(model_results)
            solver_info = get_solver_info(model_results, config['model'], log_file_path)

            # Salvataggio dei dati del solver su file
            info_file_path = logs_directory_path.joinpath(f'{instance_file_path.stem}_info.json')
            with open(info_file_path, 'w') as file:
                json.dump(solver_info, file, indent=4)

            if config['model'] == 'monolithic':
                results = get_results_from_monolithic_model(model)
            elif config['model'] == 'slim-master':
                results = get_results_from_slim_master_model(model)
            elif config['model'] == 'fat-master':
                results = get_results_from_fat_master_model(model)
            elif config['model'] == 'fat-subproblem':
                results = get_results_from_fat_subproblem_model(model)
            elif config['model'] == 'slim-subproblem':
                results = get_results_from_slim_subproblem_model(model)

            # Salvataggio dei risultati su file
            results_file_path = results_directory_path.joinpath(f'{instance_file_path.stem}_results.json')
            with open(results_file_path, 'w') as file:
                json.dump(results, file, indent=4)
            
            # Controllo sulla correttezza dei risultati
            if config['checks_throw_exceptions']:
                if config['model'] == 'monolithic':
                    check_final_results(instance, results)
                elif config['model'] in ['slim-master', 'fat-master']:
                    check_master_results(instance, results)
                elif config['model'] in ['slim-subproblem', 'fat-subproblem']:
                    check_subproblem_results(instance, results)
            else:
                try:
                    if config['model'] == 'monolithic':
                        check_final_results(instance, results)
                    elif config['model'] in ['slim-master', 'fat-master']:
                        check_master_results(instance, results)
                    elif config['model'] in ['slim-subproblem', 'fat-subproblem']:
                        check_subproblem_results(instance, results)
                except Exception as exception:
                    print(exception)

print(f'End of the testing process. Tested {total_instance_number} instances in {total_group_number} groups.')