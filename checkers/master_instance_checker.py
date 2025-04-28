from checkers.tools import check_services, check_day, common_main_checker


def check_days(days):

    if type(days) is not dict:
        raise TypeError('\'days\' is not a dict')
    
    for day_name, day in days.items():
        
        if type(day_name) is not str:
            raise KeyError(f'day \'{day_name}\' is not a string')
        if int(day_name) < 0:
            raise KeyError(f'day \'{day_name}\' is not a non-negative integer')
        
        check_day(day, day_name)
    
    day_values = [int(day_name) for day_name in days]
    if 0 not in day_values:
        raise KeyError('\'days\' do not contain \'0\'')
    if max(day_values) != len(day_values) - 1:
        raise KeyError('day names does not represent a continuos numerical succession')


def check_protocol_service(protocol_service, protocol_name, patient_name):
    
    if type(protocol_service) is not dict:
        raise TypeError(f'protocol_service of protocol \'{protocol_name}\' of patient \'{patient_name}\' is not a dict')
    if len(protocol_service) != 5:
        raise ValueError(f'protocol_service of protocol \'{protocol_name}\' of patient \'{patient_name}\' has not the correct form')
    
    if 'service' not in protocol_service:
        raise KeyError(f'protocol_service of protocol \'{protocol_name}\' of patient \'{patient_name}\' has not \'service\'')
    if type(protocol_service['service']) is not str:
        raise ValueError(f'protocol_service of protocol \'{protocol_name}\' of patient \'{patient_name}\' service is not a string')
    
    service_name = protocol_service['service']
    for key in ['start', 'tolerance', 'frequency']:
        
        if key not in protocol_service:
            raise KeyError(f'\'{key}\' is not present in protocol_service with service \'{service_name}\' of protocol \'{protocol_name}\' of patient \'{patient_name}\'')
        if type(protocol_service[key]) is not int or protocol_service[key] < 0:
            raise ValueError(f'protocol_service with service \'{service_name}\' of protocol \'{protocol_name}\' of patient \'{patient_name}\' \'{key}\' is not a positive integer')

    if 'times' not in protocol_service:
        raise KeyError(f'\'times\' is not present in protocol_service with service \'{service_name}\' of protocol \'{protocol_name}\' of patient \'{patient_name}\'')
    if type(protocol_service['times']) != int or protocol_service['times'] <= 0:
        raise ValueError(f'protocol_service with service \'{service_name}\' of protocol \'{protocol_name}\' of patient \'{patient_name}\' times is not a non-negative integer')


def check_protocol(protocol, protocol_name, patient_name):
    
    if type(protocol) is not dict:
        raise TypeError(f'protocol \'{protocol_name}\' of patient \'{patient_name}\' is not a dict')
    if len(protocol) != 2:
        raise ValueError(f'protocol \'{protocol_name}\' of patient \'{patient_name}\' has not the correct form')
    
    if 'initial_shift' not in protocol:
        raise KeyError(f'protocol \'{protocol_name}\' of patient \'{patient_name}\' has not \'initial_shift\'')
    if type(protocol['initial_shift']) is not int or protocol['initial_shift'] < 0:
        raise ValueError(f'protocol \'{protocol_name}\' of patient \'{patient_name}\' initial_shift is not a non-negative integer')

    if 'protocol_services' not in protocol:
        raise KeyError(f'protocol \'{protocol_name}\' of patient \'{patient_name}\' has not \'protocol_services\'')
    if type(protocol['protocol_services']) is not list:
        raise TypeError(f'protocol \'{protocol_name}\' of patient \'{patient_name}\' \'protocol_services\' is not a list')
    
    for protocol_service in protocol['protocol_services']:
        check_protocol_service(protocol_service, protocol_name, patient_name)


def check_patient(patient, patient_name):

    if type(patient) is not dict:
        raise TypeError(f'patient \'{patient_name}\' is not a dict')
    if len(patient) != 2:
        raise ValueError(f'patient \'{patient_name}\' has not the correct form')
    
    if 'priority' in patient and (type(patient['priority']) is not int or patient['priority'] <= 0):
        raise ValueError(f'patient \'{patient_name}\' priority is not a positive integer')

    if 'protocols' not in patient:
        raise KeyError(f'patient \'{patient_name}\' has not \'protocols\'')
    if type(patient['protocols']) is not dict:
        raise TypeError(f'patient \'{patient_name}\' \'protocols\' is not a dict')
    
    for protocol_name, protocol in patient['protocols'].items():
        
        if type(protocol_name) is not str:
            raise TypeError(f'\'{protocol_name}\' of patient \'{patient_name}\' is not a string')
        
        check_protocol(protocol, protocol_name, patient_name)


def check_patients(patients):

    if type(patients) is not dict:
        raise TypeError('\'patients\' is not a dict')
    
    for patient_name, patient in patients.items():
        
        if type(patient_name) is not str:
            raise ValueError(f'\'{patient_name}\' is not a string')
        
        check_patient(patient, patient_name)


def check_protocol_windows_integrity(instance):
    
    min_day = min([int(day_name) for day_name in instance['days']])
    max_day = max([int(day_name) for day_name in instance['days']])
    
    for patient_name, patient in instance['patients'].items():
        for protocol_name, protocol in patient['protocols'].items():
            
            initial_shift = protocol['initial_shift']
            
            for protocol_service in protocol['protocol_services']:

                service_name = protocol_service['service']
                if service_name not in instance['services']:
                    raise KeyError(f'service \'{service_name}\' of protocol_service of protocol \'{protocol_name}\' of patient \'{patient_name}\' does not exists')
                
                start = protocol_service['start']
                tolerance = protocol_service['tolerance']
                frequency = protocol_service['frequency']
                times = protocol_service['times']

                if frequency != 0 and frequency < 2 * tolerance + 1:
                    raise ValueError(f'protocol_service of service \'{service_name}\' of protocol \'{protocol_name}\' of patient \'{patient_name}\' has overlapping windows')
                
                if times == 1 and frequency != 0:
                    raise ValueError(f'protocol_service of service \'{service_name}\' of protocol \'{protocol_name}\' of patient \'{patient_name}\' has \'times\' = 1 but \'frequency\' != 0')
                
                if start + initial_shift + tolerance < min_day:
                    raise ValueError(f'protocol_service of service \'{service_name}\' of protocol \'{protocol_name}\' of patient \'{patient_name}\' starts too early')
                if start + initial_shift + frequency * (times - 1) - tolerance > max_day:
                    raise ValueError(f'protocol_service of service \'{service_name}\' of protocol \'{protocol_name}\' of patient \'{patient_name}\' ends too late')


def check_master_instance(master_instance):
    
    for key in ['services', 'days', 'patients']:
        if key not in master_instance:
            raise KeyError(f'\'{key}\' is not present in instance')
    
    if len(master_instance) != 3:
        if len(master_instance) == 4 and 'info' not in master_instance:
            raise KeyError('Unknown keys in instance')
        else:
            raise KeyError('Unknown keys in instance')
    
    check_services(master_instance['services'])
    check_days(master_instance['days'])
    check_patients(master_instance['patients'])

    check_protocol_windows_integrity(master_instance)
    

if __name__ == '__main__':

    common_main_checker(
        command_name='Master instance checker',
        function_to_call=check_master_instance,
        needs_results=False)