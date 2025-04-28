from pathlib import Path
import argparse
import json
import shutil
import yaml

from solve_single_instance import main


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

for config in configs:

    for group_directory_path in groups_input_directory_path.iterdir():
        if not group_directory_path.is_dir():
            continue

        group_name = group_directory_path.name
        group_input_directory_path = group_directory_path.joinpath('input')

        for master_instance_file_path in group_input_directory_path.iterdir():
            
            new_group_directory_path = groups_output_directory_path.joinpath(f'{group_name}_{config['name']}_{master_instance_file_path.stem}')
            if new_group_directory_path.exists():
                shutil.rmtree(new_group_directory_path)
            new_group_directory_path.mkdir()

            new_input_directory_path = new_group_directory_path.joinpath('input')
            new_input_directory_path.mkdir()
            
            with open(master_instance_file_path, 'r') as file:
                master_instance = json.load(file)
            
            new_master_instance_file_path = new_input_directory_path.joinpath(master_instance_file_path.name)
            with open(new_master_instance_file_path, 'w') as file:
                json.dump(master_instance, file, indent=4)
            
            print(f'Start solving instance {master_instance_file_path.name}')
            main(new_group_directory_path, config, config['name'])
