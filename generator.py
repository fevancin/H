import pathlib
import argparse
import yaml
import copy
import random
import json
import jsbeautifier


def get_config_value(value) -> float:
    '''Funzione che ritorna un valore float con distribuzione che varia a
    seconda del tipo di configurazione fornita: se si passa un oggetto
    {min, max} è uniforme, se è {min, max, mode} è triangolare, se è
    {min, max, mu, sigma} è gaussiana. Infine se il valore è direttamente un
    numero si ritorna quel valore.'''

    if type(value) is float:
        return value

    if type(value) is int:
        return float(value)
    
    if type(value) is not dict:
        raise TypeError(f'Value {value} is not int, float nor a dict.')
    
    low = 0.0 if 'min' not in value else value['min']
    high = 1.0 if 'max' not in value else value['max']
    
    if 'mode' in value:
        return random.triangular(low=low, high=high, mode=value['mode'])
    
    if 'mu' in value:
        sigma = 1.0 if 'sigma' not in value else value['sigma']
        v = random.gauss(mu=config['mu'], sigma=sigma)
        
        # clamping
        if v < low: v = low
        if v > high: v = high
        
        return v
    
    return random.uniform(low, high)


def get_int_config_value(value) -> int:
    '''Funzione che effettua il casting ad intero per tutti quei valori di
    configurazione che devono essere per forza interi.'''

    return int(get_config_value(value))


def generate_day(config) -> dict:
    '''Funzione che ritorna gli operatori di un giorno divisi per unità di
    cura'''

    care_unit_number = get_int_config_value(config['care_unit_number'])
    operator_number = get_int_config_value(config['operator_number'])
    time_slots = get_int_config_value(config['time_slots'])

    day = {}
    for care_unit_index in range(care_unit_number):
        
        care_unit = {}
        for operator_index in range(operator_number):
            
            operator = {
                'start': 0,
                'duration': time_slots
            }
            
            operator_name = f'op{operator_index:02}'
            care_unit[operator_name] = operator
        
        care_unit_name = f'cu{care_unit_index:02}'
        day[care_unit_name] = care_unit
    
    return day


def generate_days(config) -> dict:
    '''Funzione che ritorna un elenco di giorni tutti uguali.'''

    day_number = get_int_config_value(config['day_number'])

    days = {}
    for day_index in range(day_number):
        
        day = generate_day(config)
        
        day_name = str(day_index)
        days[day_name] = day
    
    return days


def generate_empty_patients(config) -> dict:
    '''Funzione che ritorna l'insieme dei pazienti senza nessuna richiesta.'''

    patient_number = get_int_config_value(config['patient_number'])

    patients = {}
    for patient_index in range(patient_number):

        requests = {} if 'day_number' in config else []
        
        patient = {
            'priority': 1,
            'requests': requests
        }
        
        patient_name = f'pat{patient_index:03}'
        patients[patient_name] = patient
    
    return patients


def generate_master_instance(config) -> dict:
    '''Funzione che ritorna un'istanza del problema master.'''

    day_number = get_int_config_value(config['day_number'])
    time_slots = get_int_config_value(config['time_slots'])
    request_window_max_size = get_int_config_value(config['request_window_max_size'])
    service_number = get_int_config_value(config['service_number'])
    request_per_disponibility_ratio = get_config_value(config['request_per_disponibility_ratio'])
    requests_likeness_percentage = get_config_value(config['requests_likeness_percentage'])

    # Generazione dei giorni days[day][cu][op] = {start, duration}
    days = generate_days(config)

    # Elenco dei nomi delle unità di cura che compaiono almeno in un giorno
    care_unit_names = sorted(set(care_unit_name for day in days.values() for care_unit_name in day))

    # Dizionario indicizzato per unità di cura che contiene l'elenco dei nomi di
    # servizi di quella unità di cura
    services_of_care_unit = {care_unit_name: [] for care_unit_name in care_unit_names}
    
    # Generazione dei servizi
    services = {}
    for service_index in range(service_number):
        
        # Le unità di cura vengono scelte ciclicamente
        care_unit_name = care_unit_names[service_index % len(care_unit_names)]
        service_name = f'srv{len(services):03}'

        duration = get_int_config_value(config['service_duration'])
        if duration > time_slots:
            duration = time_slots
        
        service = {
            'care_unit': care_unit_name,
            'duration': duration
        }

        services[service_name] = service
        services_of_care_unit[care_unit_name].append(service_name)
    
    # Per ogni unità di cura tieni il conto della durata totale dei servizi
    # inseriti
    care_unit_total_durations = [0 for _ in care_unit_names]

    # Ammontare totale delle durate dei servizi da inserire come richieste
    total_slots_to_fill = int(
        sum(operator['duration']
        for day in days.values()
        for care_unit in day.values()
        for operator in care_unit.values())
        * request_per_disponibility_ratio)

    # Generazione delle richieste dei pazienti indicizzate per nome del servizio
    # in cui ognuno di questi elementi è una lista di finestre giornaliere
    patients = generate_empty_patients(config)
    
    # Elenco dei nomi di pazienti
    patient_names = list(patients.keys())

    while total_slots_to_fill > 0:

        # Si sceglie un servizio dell'unità di cura meno carica per ora
        min_total_duration = min(care_unit_total_durations)
        least_full_care_unit_name = care_unit_names[care_unit_total_durations.index(min_total_duration)]
    
        service_name = random.choice(services_of_care_unit[least_full_care_unit_name])
        service_duration = services[service_name]['duration']

        # Si sceglie casualmente un paziente
        patient_name = random.choice(patient_names)
        patient_requests = patients[patient_name]['requests']

        # Copia di una finestra delle richieste già inserite con probabilità
        # uguale a 'requests_likeness_percentage' 
        if len(patient_requests) > 0 and random.random() < requests_likeness_percentage:
            other_service_name = random.choice(list(patient_requests.keys()))
            window = random.choice(patient_requests[other_service_name])

        # Generazione di una nuova finestra con probabilità
        # 1.0 - 'requests_likeness_percentage'
        else:
            window_size = random.randint(1, request_window_max_size)
            start_day = random.randint(0, day_number - window_size - 1)
            window = (start_day, start_day + window_size - 1)

        # Inserimento della finestra
        if service_name not in patient_requests:
            patient_requests[service_name] = []
        patient_requests[service_name].append(window)

        # Aggiornamento dei contatori
        total_slots_to_fill -= service_duration
        care_unit_total_durations[care_unit_names.index(least_full_care_unit_name)] += service_duration

    # Eliminazione dei pazienti senza nessuna richiesta
    patients = dict(filter(lambda p: len(p[1]['requests']) > 0, patients.items()))

    return {
        'patients': patients,
        'days': days,
        'services': services
    }


def generate_subproblem_instance(config) -> dict:
    '''Funzione che ritorna un'istanza del sottoproblema.'''

    # Generazione del giorno
    day = generate_day(config)

    # Generazione delle richieste dei pazienti nella forma di lista di servizi
    patients = generate_empty_patients(config)
    
    # Massimo tempo in cui almeno un operatore è attivo
    max_time_slot = max(o['start'] + o['duration'] for c in day.values() for o in c.values())


    # Elenco dei nomi degli operatori
    operator_names = [(cn, on) for cn, c in day.items() for on in c.keys()]

    # Durata totale assegnata ad ogni operatore 
    remaining_operator_time_slots = {(cn, on): day[cn][on]['duration'] for cn, on in operator_names}
    
    # Elenco dei nomi dei pazienti
    patient_names = list(patients.keys())

    # Durata totale assegnata ad ogni paziente
    remaining_patient_time_slots = {pn: max_time_slot for pn in patient_names}
    
    # Genera richieste finchè tutti gli operatori non sono pieni
    services = {}
    while len(operator_names) > 0:

        # Seleziona operatore e paziente a cui assegnare la richiesta
        cn, on = random.choice(operator_names)
        pn = random.choice(patient_names)

        # Calcolo delle proprietà del servizio
        service_name = f'srv{len(services):02}'
        service_duration = get_int_config_value(config['service_duration'])

        # Se l'operatore o il paziente oltrepasserebbe il proprio limite,
        # riduci la durata del servizio
        if remaining_operator_time_slots[(cn, on)] < service_duration:
            service_duration = remaining_operator_time_slots[(cn, on)]
        if remaining_patient_time_slots[pn] < service_duration:
            service_duration = remaining_patient_time_slots[pn]
        
        # Riduci i contatori ed eventualmente togli i nomi di operatori e
        # pazienti delle liste delle possibili scelte quando sono pieni
        remaining_operator_time_slots[(cn, on)] -= service_duration
        if remaining_operator_time_slots[(cn, on)] == 0:
            operator_names.remove((cn, on))

        remaining_patient_time_slots[pn] -= service_duration
        if remaining_patient_time_slots[pn] == 0:
            patient_names.remove(pn)

        # Cerazione del servizio relativo alla richiesta corrente
        service = {
            'care_unit': cn,
            'duration': service_duration
        }
        
        # Aggiunta della richiesta corrente
        services[service_name] = service
        patients[pn]['requests'].append(service_name)

    # Eliminazione dei pazienti senza nessuna richiesta
    patients = dict(filter(lambda p: len(p[1]['requests']) > 0, patients.items()))

    return {
        'patients': patients,
        'day': day,
        'services': services
    }


# Argomenti da linea di comando
parser = argparse.ArgumentParser(
    prog='Instance generator',
    description='Program that generates master or subproblem instances.')

parser.add_argument('-v', '--verbose', action='store_true')
parser.add_argument('-c', '--config', required=True, type=pathlib.Path,
    help='Location of a YAML generator configuration file.')
parser.add_argument('-o', '--output', required=True, type=pathlib.Path,
    help='Location where instance groups will be written.')

args = parser.parse_args()

is_verbose = bool(args.verbose)
config_file_path = pathlib.Path(args.config)
output_directory_path = pathlib.Path(args.output)

# Controlli sulla validità degli argomenti da linea di comando
if not config_file_path.exists():
    raise FileNotFoundError(f'Path \'{config_file_path}\' does not exist.')
if config_file_path.suffix != '.yaml':
    raise FileNotFoundError(f'Path \'{config_file_path}\' is not a YAML file.')
if output_directory_path.suffix != '':
    raise FileNotFoundError(f'Path \'{output_directory_path}\' is not a directory.')

# eventuale creazione della cartella di output
if not output_directory_path.exists():
    output_directory_path.mkdir()
    
    if is_verbose:
        print(f'Created output directory.')

# Lettura del file di configurazione
with open(config_file_path) as file:
    config = yaml.load(file, yaml.Loader)

if is_verbose:
    print('Succesfully read the configuration file.')

# Generazione dei gruppo
for group_name, group_changes in config['groups'].items():

    # Creazione della cartella del gruppo corrente
    group_directory_path = output_directory_path.joinpath(group_name)

    if is_verbose and not output_directory_path.exists():
        print(f'Group directory \'{group_name}\' does not exist, creating it.')
    
    group_directory_path.mkdir(exist_ok=True)

    # Sovrascrittura delle configurazioni di base per ottenere la configurazione
    # del gruppo corrente
    group_config = copy.deepcopy(config['base'])
    for group_change_key, group_change_value in group_changes.items():
        group_config[group_change_key] = group_change_value
    
    # Salva uan copia della configurazione corrente
    group_config_file_path = group_directory_path.joinpath('config.yaml')
    with open(group_config_file_path, 'w') as file:
        json.dump(group_config, file, indent=4)
    
    random.seed(get_config_value(group_config['seed']))
    
    # Generazione del gruppo corrente
    instance_number = get_int_config_value(group_config['instance_number'])
    for instance_index in range(instance_number):

        instance_name = f'inst_{instance_index:02}.json'
        instance_file_path = group_directory_path.joinpath(instance_name)

        if 'day_number' in group_config:
            instance = generate_master_instance(group_config)
        else:
            instance = generate_subproblem_instance(group_config)

        # Scrittura su file dell'istanza corrente
        with open(instance_file_path, 'w') as file:
           file.write(jsbeautifier.beautify(json.dumps(instance)))
        
    if is_verbose:
        print(f'Generated {instance_number} instances in group \'{group_name}\'.')