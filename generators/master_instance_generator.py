import random

from tools import get_value, generate_day, generate_services, generate_service, common_main_generator


def generate_week(config):

    week = []
    for _ in range(int(get_value(config['day']['week_size']))):
        week.append(generate_day(config))
    return week


def generate_days(config, week=None):

    days = {}

    if config['day']['strategy'] == 'repeat_week':
        week = generate_week(config)
    elif config['day']['strategy'] == 'all_same':
        only_day = generate_day(config)

    for day_index in range(int(get_value(config['day']['number']))):
        
        if config['day']['strategy'] == 'repeat_week':
            day = week[day_index % len(week)]
        elif config['day']['strategy'] == 'all_same':
            day = only_day
        else:
            day = generate_day(config)
        days[f'{day_index}'] = day
    
    return days


def generate_protocol_service(config, day_number, initial_shift, services):
    
    if config['service']['strategy'] == 'all_different':
        
        service_index = len(services)
        service_name = f'srv{service_index:02}'
        if config['service']['care_unit_strategy'] == 'balanced':
            services[service_name] = generate_service(config, service_index)
        else:
            services[service_name] = generate_service(config)
    
    else:
        service_index = random.randint(0, len(services) - 1)
        service_name = f'srv{service_index:02}'
    
    spread_percentage = get_value(config['protocol']['service']['start_spread_percentage'])
    start = random.randint(0, int(spread_percentage * day_number))
    tolerance = int(get_value(config['protocol']['service']['tolerance']))

    if initial_shift + start - tolerance >= day_number:
        return None

    frequency = int(get_value(config['protocol']['service']['frequency']))
    times = int(get_value(config['protocol']['service']['times']))

    if frequency < tolerance * 2 + 1:
        frequency = tolerance * 2 + 1
    
    max_times = int((day_number - start - initial_shift) / frequency) + 1
    if start + initial_shift + (max_times - 1) * frequency - tolerance >= day_number:
        max_times -= 1
    if max_times <= 0:
        max_times = 1
    if times > max_times:
        times = max_times

    if times == 1:
        frequency = 0

    return {
        'service': service_name,
        'start': start,
        'tolerance': tolerance,
        'frequency': frequency,
        'times': times
    }


def generate_protocol(config, day_number, services):
    
    spread_percentage = get_value(config['protocol']['initial_shift_spread_percentage'])
    initial_shift = random.randint(0, int(spread_percentage * day_number))
    
    protocol_services = []

    for _ in range(int(get_value(config['protocol']['services_per_protocol']))):
        protocol_service = generate_protocol_service(config, day_number, initial_shift, services)
        if protocol_service is not None:
            protocol_services.append(protocol_service)

    if len(protocol_services) == 0:
        return None
    
    return {
        'initial_shift': initial_shift,
        'protocol_services': protocol_services
    }


def generate_patient(config, day_number, services, protocols=None):
    
    patient = {}
    if config['patient']['use_priority']:
        patient['priority'] = int(get_value(config['patient']['priority']))

    patient['protocols'] = {}
    for protocol_index in range(int(get_value(config['patient']['protocols_per_patient']))):
        
        if config['protocol']['strategy'] == 'pool':
            protocol = protocols[random.randint(0, len(protocols) - 1)]
        else:
            protocol = generate_protocol(config, day_number, services)
        
        if protocol is not None:
            patient['protocols'][f'prot{protocol_index}'] = protocol
    
    return patient


def generate_patients(config, day_number, services=None):
    
    patients = {}

    if config['service']['strategy'] == 'all_different':
        services = {}
    
    if config['protocol']['strategy'] == 'pool':
        protocols = []
        for _ in range(int(get_value(config['protocol']['pool_size']))):
            protocols.append(generate_protocol(config, day_number, services))
    
    for patient_index in range(int(get_value(config['patient']['number']))):
        if config['protocol']['strategy'] == 'pool':
            patient = generate_patient(config, day_number, services, protocols)
        else:
            patient = generate_patient(config, day_number, services)
        patients[f'pat{patient_index:02}'] = patient
    
    if config['service']['strategy'] == 'all_different':
        return patients, services
    
    return patients


def generate_master_instance(config):
    
    days = generate_days(config)

    if config['service']['strategy'] == 'pool':
        services = generate_services(config)
        patients = generate_patients(config, len(days), services)
    else:
        patients, services = generate_patients(config, len(days))

    return {
        'patients': patients,
        'days': days,
        'services': services
    }


if __name__ == '__main__':

    common_main_generator(
        command_name='Master instance generator',
        function_to_call=generate_master_instance)