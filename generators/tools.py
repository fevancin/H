from pathlib import Path
import argparse
import shutil
import random
import yaml
import json
import time


def get_value(config):

    if type(config) is int or type(config) is float or type(config) is bool:
        return config
    
    if 'average' not in config:

        if 'mode' in config:
            return random.triangular(config['min'], config['max'], config['mode'])

        return random.randint(config['min'], config['max'])
    
    if 'standard_deviation' not in config:
        std = config['standard_deviation']
    else:
        std = 1.0
    
    value = random.gauss(config['average'], std)
    
    if 'min' in config and value < config['min']:
        value = config['min']
    if 'max' in config and value > config['max']:
        value = config['max']
    
    return value


def get_max_value(config):

    if type(config) is int or type(config) is float:
        return config
    
    if 'max' in config:
        return config['max']
    
    return 1e10


def generate_service(config, service_index):

    care_unit_number = int(get_max_value(config['day']['care_unit_number']))

    if config['service']['care_unit_strategy'] == 'balanced':
        care_unit_name = f'cu{service_index % care_unit_number:02}'
    else:
        care_unit_name = f'cu{random.randint(0, care_unit_number - 1):02}'
    
    return {
        'care_unit': care_unit_name,
        'duration': int(get_value(config['service']['duration']))
    }


def generate_services(config):

    services = {}

    for service_index in range(int(get_max_value(config['service']['pool_size']))):

        if config['service']['care_unit_strategy'] == 'balanced':
            service = generate_service(config, service_index)
        else:
            service = generate_service(config)
        services[f'srv{service_index:02}'] = service
    
    return services


def generate_operator(config, operator_index=None, duration=None):
    
    if config['operator']['strategy'] == 'fill':
        return {
            'start': 0,
            'duration': int(get_max_value(config['operator']['time_slots']))
        }
    
    if config['operator']['strategy'] == 'overlap':
        return {
            'start': int(operator_index * duration * get_value(config['operator']['overlap_percentage'])),
            'duration': duration
        }
    
    max_time_slots = int(get_max_value(config['operator']['time_slots']))
    duration = int(get_value(config['operator']['duration']))
    
    return {
        'start': random.randint(0, max_time_slots - duration),
        'duration': duration
    }


def generate_care_unit(config):

    care_unit = {}

    if config['operator']['strategy'] == 'overlap':
        duration = int(get_value(config['operator']['duration']))
    
    for operator_index in range(int(get_value(config['day']['operators_per_care_unit']))):
    
        if config['operator']['strategy'] == 'overlap':
            operator = generate_operator(config, operator_index, duration)
        else:
            operator = generate_operator(config)
        care_unit[f'op{operator_index:02}'] = operator
    
    return care_unit


def generate_day(config):

    day = {}
    for care_unit_index in range(int(get_value(config['day']['care_unit_number']))):
        day[f'cu{care_unit_index:02}'] = generate_care_unit(config)
    return day


def common_main_generator(command_name, function_to_call):

    parser = argparse.ArgumentParser(prog=command_name, description='Creates grouped random instances')
    parser.add_argument('-c', '--config', type=Path, help='YAML file configuration path', required=True)
    parser.add_argument('-o', '--output', type=Path, help='Output directory path', default=Path('./instances/'))
    parser.add_argument('-d', '--delete-prev', action='store_true', help='Remove all previous data in output directory')
    parser.add_argument('-v', '--verbose', action='store_true', help='Show what is done')
    args = parser.parse_args()

    config_file_path = Path(args.config).resolve()
    output_directory_path = Path(args.output).resolve()
    delete_previous_data = bool(args.delete_prev)
    is_verbose = bool(args.verbose)

    if not config_file_path.exists():
        raise FileNotFoundError(f'Configuration file \'{config_file_path}\' does not exists.')
    if not config_file_path.is_file() or config_file_path.is_dir():
        raise ValueError(f'Configuration file \'{config_file_path}\' is not a file')
    if config_file_path.suffix != '.yaml':
        raise ValueError(f'Configuration file \'{config_file_path}\' is not a YAML file')

    if output_directory_path.exists() and not output_directory_path.is_dir():
        raise ValueError(f'Output directory \'{output_directory_path}\' is not a directory')
    if output_directory_path.exists() and delete_previous_data:
        shutil.rmtree(output_directory_path)
    output_directory_path.mkdir(exist_ok=True)

    with open(config_file_path, 'r') as file:
        config = yaml.load(file, yaml.Loader)

    if is_verbose:
        print(f'Read configuration file \'{config_file_path}\'')
        start_time = time.perf_counter()
        instance_group_number = 0
        instance_number = 0

    for group_config in config['groups']:

        if is_verbose:
            instance_group_number += 1

        group_directory_path = output_directory_path.joinpath(group_config['instance_group_directory_name'])
        group_directory_path.mkdir(exist_ok=True)

        if config['include_info_in_group_directory']:
            with open(group_directory_path.joinpath('generator_config.yaml'), 'w') as file:
                yaml.dump(group_config, file, default_flow_style=False, sort_keys=False)
        
        instance_directory_path = group_directory_path.joinpath('input/')
        instance_directory_path.mkdir(exist_ok=True)

        random.seed(group_config['seed'])

        for instance_index in range(group_config['instance_number']):

            instance_file_path = instance_directory_path.joinpath(f'instance_{instance_index:02}.json')
            instance = function_to_call(group_config)

            if config['include_info_in_instances']:
                temp = {
                    'info': group_config
                }
                temp.update(instance)
                instance = temp

            with open(instance_file_path, 'w') as file:
                json.dump(instance, file, indent=4)
            
            if is_verbose:
                print(f'Created instance \'{instance_file_path}\'')
                instance_number += 1

    if is_verbose:
        end_time = time.perf_counter()
        print(f'End generation process. Time elapsed: {end_time - start_time}s')
        print(f'Created {instance_number} instances in {instance_group_number} groups')