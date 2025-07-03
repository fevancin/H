from pathlib import Path
import argparse
import json
import jsbeautifier


def translate_subproblem_instance(instance):
    '''Funzione che traduce un istanza del sottoproblema nel nuovo formato.'''

    patients_object = None
    for p in instance['request_dict'].values():
        patients_object = p
        break

    # Traduzione dei pazienti
    patients = {}
    for patient_name, patient in patients_object.items():
        
        patients[patient_name] = {
            'priority': 1,
            'requests': []
        }
        
        # Dal nome del pacchetto si passa al servizio
        for packet_name in patient['packets']:
            service_names = instance['mashp_input']['abstract_packet'][packet_name]
            patients[patient_name]['requests'].extend(service_names)
        
        patients[patient_name]['requests'] = list(set(patients[patient_name]['requests']))

    # Traduzione del giorno
    day = None
    for d in instance['mashp_input']['daily_capacity'].values():
        day = d
        break

    # Traduzione dei servizi
    services = {}
    for service_name, service in instance['mashp_input']['services'].items():
        services[service_name] = {
            'care_unit': service['careUnit'],
            'duration': service['duration']
        }

    return {
        'patients': patients,
        'day': day,
        'services': services
    }


def translate_master_instance(instance):
    '''Funzione che traduce un istanza del master nel nuovo formato.'''

    # Traduzione dei pazienti
    days = instance['daily_capacity']

    # Limiti dell'orizzonte temporale
    min_day_index = min(int(day_name) for day_name in days.keys())
    max_day_index = max(int(day_name) for day_name in days.keys())
    
    # Traduzione dei pazienti
    patients = {}
    for patient_name, patient in instance['pat_request'].items():
        
        patients[patient_name] = {
            'priority': 1,
            'requests': {}
        }
        
        for protocol_name, protocol in patient.items():
            if protocol_name == 'priority_weight':
                patients[patient_name]['priority'] = protocol
                continue

            for iteration in protocol.values():
                initial_shift = iteration[1]
                
                for protocol_item in iteration[0]:
                    
                    # Ottenimento del servizio relativo al pacchetto richiesto
                    service_name = instance['abstract_packet'][protocol_item['packet_id']][0]
                    tolerance = protocol_item['tolerance']
                    
                    if service_name not in patients[patient_name]['requests']:
                        patients[patient_name]['requests'][service_name] = []
                    
                    # Limiti del protocollo
                    start_day = max(min_day_index, protocol_item['existence'][0] + initial_shift)
                    end_day = min(max_day_index, protocol_item['existence'][1] + initial_shift)
                    
                    # Svolgimento delle finestre di richiesta
                    for central_day_index in range(
                        protocol_item['start_date'] + initial_shift,
                        protocol_item['existence'][1] + initial_shift + 1,
                        protocol_item['freq']):
                        
                        window_start = max(start_day, central_day_index - tolerance)
                        window_end = min(end_day, central_day_index + tolerance)

                        patients[patient_name]['requests'][service_name].append((window_start, window_end))

    # Traduzione dei servizi
    services = {}
    for service_name, service in instance['services'].items():
        services[service_name] = {
            'care_unit': service['careUnit'],
            'duration': service['duration']
        }

    return {
        'patients': patients,
        'days': days,
        'services': services
    }


# Questo programma può essere chiamato solo dalla linea di comando
if __name__ != '__main__':
    exit(0)

# Argomenti da linea di comando
parser = argparse.ArgumentParser(prog='Instance translator', description='Program that translate instance to new format.')
parser.add_argument('-i', '--input', type=Path, required=True, help='Directory with instance groups')
parser.add_argument('-o', '--output', type=Path, required=True, help='Output directory')
args = parser.parse_args()

input_file_path = Path(args.input).resolve()
output_file_path = Path(args.output).resolve()

# Controlli sulla validità degli argomenti da linea di comando
if not input_file_path.exists():
    raise FileNotFoundError(f'Path \'{input_file_path}\' does not exist.')
elif not input_file_path.is_dir():
    raise FileNotFoundError(f'Path \'{input_file_path}\' is not a directory.')

output_file_path.mkdir(exist_ok=True)

instance_number = 0
group_number = 0

# Traduzione di ogni gruppo
for group_directory_path in input_file_path.iterdir():
    if group_directory_path.suffix != '':
        continue

    # Controllo sull'esistenza di almento un'istanza nel gruppo corrente
    has_at_least_one_instance = False
    for instance_file_path in group_directory_path.iterdir():
        if instance_file_path.suffix == '.json':
            has_at_least_one_instance = True
            break
    
    if not has_at_least_one_instance:
        continue

    group_number += 1

    # Eventuale creazione della nuova cartella del gruppo
    translated_group_directory_path = output_file_path.joinpath(group_directory_path.name)
    translated_group_directory_path.mkdir(exist_ok=True)
    
    # Traduzione delle istanze
    for instance_file_path in group_directory_path.iterdir():
        if instance_file_path.suffix != '.json':
            continue

        instance_name = instance_file_path.name
        
        # Lettura del vecchio formato
        with open(instance_file_path, 'r') as file:
            instance = json.load(file)
        
        if 'pat_request' in instance:
            translated_instance = translate_master_instance(instance)
        else:
            translated_instance = translate_subproblem_instance(instance)
        
        # Salvataggio del nuovo formato
        translated_instance_file_path = translated_group_directory_path.joinpath(instance_name)
        with open(translated_instance_file_path, 'w') as file:
            file.write(jsbeautifier.beautify(json.dumps(translated_instance)))
        
        instance_number += 1

print(f'Translated {instance_number} instances in {group_number} groups.')