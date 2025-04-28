import random

from tools import get_value, generate_day, generate_services, generate_service, common_main_generator


def generate_patient(config, services=None):

    patient = {}
    if config['patient']['use_priority']:
        patient['priority'] = int(get_value(config['patient']['priority']))
    
    request_service_number = int(get_value(config['patient']['requests_per_patient']))
    
    if config['service']['strategy'] == 'pool':
        
        if request_service_number > len(services):
            request_service_number = len(services)
        
        service_names = random.sample(services.keys(), request_service_number)
        patient['requests'] = sorted(service_names)
    
    else:

        patient['requests'] = []

        for service_index in range(len(services), len(services) + request_service_number):
            service_name = f'srv{service_index:02}'
            
            if config['service']['care_unit_strategy'] == 'balanced':
                services[service_name] = generate_service(config, service_index)
            else:
                services[service_name] = generate_service(config)
            
            patient['requests'].append(service_name)

    return patient


def generate_patients(config, services=None):

    patients = {}

    if config['service']['strategy'] == 'all_different':
        services = {}

    for patient_index in range(int(get_value(config['patient']['number']))):
        patients[f'pat{patient_index:02}'] = generate_patient(config, services)
    
    if config['service']['strategy'] == 'all_different':
        return patients, services
    
    return patients


def generate_subproblem_instance(config):
    
    day = generate_day(config)

    if config['service']['strategy'] == 'pool':
        services = generate_services(config)
        patients = generate_patients(config, services)
    else:
        patients, services = generate_patients(config)

    return {
        'patients': patients,
        'day': day,
        'services': services
    }


if __name__ == '__main__':

    common_main_generator(
        command_name='Subproblem instance generator',
        function_to_call=generate_subproblem_instance)