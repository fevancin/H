from checkers.tools import check_services, check_day


def check_patient(patient, patient_name):

    if type(patient) is not dict:
        raise TypeError(f'patient \'{patient_name}\' is not a dict')
    if len(patient) != 2:
        raise ValueError(f'patient \'{patient_name}\' has not the correct form')
    
    if 'priority' in patient and (type(patient['priority']) is not int or patient['priority'] <= 0):
        raise ValueError(f'patient \'{patient_name}\' priority is not a positive integer')

    if 'requests' not in patient:
        raise KeyError(f'patient \'{patient_name}\' has not \'requests\'')
    if type(patient['requests']) is not list:
        raise TypeError(f'patient \'{patient_name}\' \'requests\' is not a list')
    
    if len(patient['requests']) > 0 and type(patient['requests'][0]) is str:
        
        for service_name in patient['requests']:
            if type(service_name) is not str:
                raise TypeError(f'\'{service_name}\' of patient \'{patient_name}\' requests is not a string')

    else:
        for request in patient['requests']:
            
            if type(request) is not dict:
                raise TypeError(f'patient \'{patient_name}\' has wrong requests type')
            if len(request) != 3:
                raise TypeError(f'patient \'{patient_name}\' request has wrong key number')
            for key in ['service', 'care_unit', 'operator']:
                if key not in request:
                    raise KeyError(f'key \'{key}\' is not present in request of patient \'{patient_name}\'')
                if type(request[key]) is not str:
                    raise TypeError(f'key \'{key}\' in patient \'{patient_name}\' request is not a string')


def check_patients(patients):

    if type(patients) is not dict:
        raise TypeError('\'patients\' is not a dict')
    
    for patient_name, patient in patients.items():
        
        if type(patient_name) is not str:
            raise ValueError(f'\'{patient_name}\' is not a string')
        
        check_patient(patient, patient_name)


def check_requests_integrity(instance):
    
    for patient_name, patient in instance['patients'].items():
        for service_name in patient['requests']:

            if type(service_name) is dict:
                request = service_name
                service_name = request['service']
                operator_name = request['operator']
                care_unit_name = request['care_unit']

                if care_unit_name != instance['services'][service_name]['care_unit']:
                    raise ValueError(f'service {service_name} of patient {patient_name} has a different care unit from the one requested')

                if operator_name not in instance['day'][care_unit_name].keys():
                    raise KeyError(f'service {service_name} of patient {patient_name} has operator {operator_name} that does not exists in care unit {care_unit_name}')

            if service_name not in instance['services']:
                raise KeyError(f'service \'{service_name}\' of patient \'{patient_name}\' does not exists')
            
            if instance['services'][service_name]['care_unit'] not in instance['day']:
                raise KeyError(f'service \'{service_name}\' of patient \'{patient_name}\' has an unknow care unit')


def check_subproblem_instance(subproblem_instance):
    
    for key in ['services', 'day', 'patients']:
        if key not in subproblem_instance:
            raise KeyError(f'\'{key}\' is not present in instance')
    
    if len(subproblem_instance) != 3:
        if len(subproblem_instance) == 4 and 'info' not in subproblem_instance:
            raise KeyError('Unknown keys in instance')
        else:
            raise KeyError('Unknown keys in instance')
    
    check_services(subproblem_instance['services'])
    check_day(subproblem_instance['day'], None)
    check_patients(subproblem_instance['patients'])

    check_requests_integrity(subproblem_instance)