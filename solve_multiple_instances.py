from pathlib import Path
import argparse
import json
import shutil
import yaml
import copy

from solve_single_instance import solve_instance


if __name__ != '__main__':
    exit(0)

parser = argparse.ArgumentParser(prog='Solve multiple instances', description='Divide in their own group and solve master instances')
parser.add_argument('-i', '--input', type=Path, help='Groups input directory path', required=True)
parser.add_argument('-o', '--output', type=Path, help='Groups output directory path', required=True)
parser.add_argument('-c', '--configs', type=Path, help='Main configurations', required=True)
args = parser.parse_args()

groups_input_directory_path = Path(args.input).resolve()
groups_output_directory_path = Path(args.output).resolve()
configs_file_path = Path(args.configs).resolve()

with open(configs_file_path, 'r') as file:
    configs = yaml.load(file, yaml.Loader)

for config_name, config_changes in configs['groups'].items():

    config = copy.deepcopy(configs['base'])
    for config_changes_key, config_changes_value in config_changes.items():
        if type(config_changes_value) is list:
            config[config_changes_key].extend(config_changes_value)
        else:
            config[config_changes_key] = config_changes_value

    for group_directory_path in groups_input_directory_path.iterdir():
        if not group_directory_path.is_dir():
            continue

        group_name = group_directory_path.name

        if 'groups_to_do' in config and config['groups_to_do'] != 'all' and group_name not in config['groups_to_do']:
            continue

        if 'groups_to_avoid' in config and group_name in config['groups_to_avoid']:
            continue
        
        for master_instance_file_path in group_directory_path.iterdir():

            if master_instance_file_path.suffix != '.json':
                continue
            
            new_group_directory_path = groups_output_directory_path.joinpath(f'{group_name}_{config_name}_{master_instance_file_path.stem}')
            
            with open(master_instance_file_path, 'r') as file:
                master_instance = json.load(file)
            
            solve_instance(master_instance, new_group_directory_path, config)