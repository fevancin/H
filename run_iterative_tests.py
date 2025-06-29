from pathlib import Path
import argparse
import json
import yaml
import copy

from milp_models.solve_instance import solve_instance


# Questo programma può essere chiamato solo dalla linea di comando
if __name__ != '__main__':
    exit(0)

# Argomenti da linea di comando
parser = argparse.ArgumentParser(prog='Run iterative tests', description='Solve groups of master instances.')
parser.add_argument('-c', '--config', type=Path, help='Solving configuration', required=True)
parser.add_argument('-i', '--input', type=Path, help='Directory with instance groups.', required=True)
parser.add_argument('-o', '--output', type=Path, help='Directory where outputting results.', required=True)
args = parser.parse_args()

config_file_path = Path(args.config).resolve()
input_directory_path = Path(args.input).resolve()
output_directory_path = Path(args.output).resolve()

# Controlli sulla validità degli argomenti da linea di comando
if not config_file_path.exists():
    raise FileNotFoundError(f'Path \'{config_file_path}\' does not exist.')
if config_file_path.suffix != '.yaml':
    raise FileNotFoundError(f'Path \'{config_file_path}\' is not a YAML file.')
if not input_directory_path.exists():
    raise FileNotFoundError(f'Path \'{input_directory_path}\' does not exist.')
elif not input_directory_path.is_dir():
    raise FileNotFoundError(f'Path \'{input_directory_path}\' is not a directory.')
if output_directory_path.suffix != '':
    raise FileNotFoundError(f'Path \'{output_directory_path}\' is not a directory.')

# Eventuale creazione della cartella di output
if not output_directory_path.exists():
    output_directory_path.mkdir()
    print(f'Created output directory {output_directory_path}.')

# Lettura del file di configurazione
with open(config_file_path, 'r') as file:
    configs = yaml.load(file, yaml.Loader)

total_instance_number = 0
total_group_number = 0

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
    
    # Controllo sulla validita fat/slim
    if config['master_model']['model'] in ['fat-master'] and config['subproblem_model']['model'] not in ['slim-subproblem']:
        print(f'WARNING: in \'{config_name}\' the master is fat, the subproblem is not slim. Ignoring this configuration.')
        continue
    if config['master_model']['model'] in ['slim-master'] and config['subproblem_model']['model'] not in ['fat-subproblem']:
        print(f'WARNING: in \'{config_name}\' the master is slim, the subproblem is not fat. Ignoring this configuration.')
        continue

    group_number = 0
    group_names = []
    total_group_instance_number = 0

    for group_input_directory_path in input_directory_path.iterdir():
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
            total_group_instance_number += 1
    
    if group_number == 0:
        print(f'WARNING: the configuration \'{config_name}\' does not have any valid instance groups.')
    else:
        group_names_string = ', '.join(group_names)
        print(f'The configuration \'{config_name}\' will be applied to {group_number} instance groups: [{group_names_string}].')
        print(f'{total_group_instance_number} total instances will be solved by configuration \'{config_name}\'.')

    total_instance_number += total_group_instance_number

print(f'{total_instance_number} total instances will be solved (some may be the same but with different configurations).')

print('---')

# Esecuzione di ogni tipologia di risoluzione presente nella configurazione
for config_name, config_changes in configs['groups'].items():

    # Copia della configurazione di base con sovrascrittura del gruppo corrente
    config = copy.deepcopy(configs['base'])
    for config_changes_key, config_changes_value in config_changes.items():
        if type(config_changes_value) is list:
            config[config_changes_key].extend(config_changes_value)
        else:
            config[config_changes_key] = config_changes_value
    
    # Controllo sulla validita fat/slim
    if config['master_model']['model'] in ['fat-master'] and config['subproblem_model']['model'] not in ['slim-subproblem']:
        continue
    if config['master_model']['model'] in ['slim-master'] and config['subproblem_model']['model'] not in ['fat-subproblem']:
        continue

    # Risolvi i gruppi di istanze
    for group_directory_path in input_directory_path.iterdir():
        if not group_directory_path.is_dir():
            continue

        group_name = group_directory_path.name

        # Eventuale scarto di alcuni gruppi
        if 'groups_to_do' in config and 'all' not in config['groups_to_do'] and group_name not in config['groups_to_do']:
            continue
        if 'groups_to_avoid' in config and group_name in config['groups_to_avoid']:
            continue
        
        # Risoluzione delle istanze
        for master_instance_file_path in group_directory_path.iterdir():

            if master_instance_file_path.suffix != '.json':
                continue
            
            # Cartella dove i risultati verranno salvati
            new_group_directory_path = output_directory_path.joinpath(f'{group_name}_{config_name}_{master_instance_file_path.stem}')
            
            # Input dell'istanza corrente
            with open(master_instance_file_path, 'r') as file:
                master_instance = json.load(file)
            
            print(f'Solving instance \'{master_instance_file_path.stem}\' of group \'{group_directory_path.name}\' with configuration \'{config_name}\'.')

            # Risoluzione
            try:
                solve_instance(master_instance, new_group_directory_path, config)
            except Exception as e:
                print(f'An error occurred: {e}')

            print(f'End of instance \'{master_instance_file_path.stem}\' of group \'{group_directory_path.name}\' with configuration \'{config_name}\'.')