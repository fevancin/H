from checkers.tools import check_services, check_day


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


def check_window(window, service_name, patient_name):
    
    if type(window) is not list:
        raise TypeError(f'window of service \'{service_name}\' of patient \'{patient_name}\' is not a list')
    if len(window) != 2:
        raise ValueError(f'window of service \'{service_name}\' of patient \'{patient_name}\' is not a couple')
    
    if type(window[0]) != int or window[0] < 0:
        raise ValueError(f'window start of service \'{service_name}\' of patient \'{patient_name}\' is a negative integer')
    if type(window[1]) != int or window[1] < 0 or window[1] < window[0]:
        raise ValueError(f'window end of service \'{service_name}\' of patient \'{patient_name}\' is a negative integer')


def check_windows(windows, service_name, patient_name):
    
    if type(windows) is not list:
        raise TypeError(f'windows of \'{service_name}\' of patient \'{patient_name}\' is not a list')
    if len(windows) == 0:
        raise ValueError(f'Patient {patient_name} has empty windows for service {service_name}')
    
    for window in windows:
        check_window(window, service_name, patient_name)


def check_patient(patient, patient_name):

    if type(patient) is not dict:
        raise TypeError(f'patient \'{patient_name}\' is not a dict')
    if len(patient) != 2:
        raise ValueError(f'patient \'{patient_name}\' has not the correct form')
    
    if 'priority' in patient and (type(patient['priority']) is not int or patient['priority'] <= 0):
        raise ValueError(f'patient \'{patient_name}\' priority is not a positive integer')

    if 'requests' not in patient:
        raise KeyError(f'patient \'{patient_name}\' has not \'requests\'')
    if type(patient['requests']) is not dict:
        raise TypeError(f'patient \'{patient_name}\' \'requests\' is not a dict')
    
    for service_name, windows in patient['requests'].items():
        
        if type(service_name) is not str:
            raise TypeError(f'\'{service_name}\' of patient \'{patient_name}\' is not a string')
        
        check_windows(windows, service_name, patient_name)


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
        for service_name, windows in patient['requests'].items():
            
            if service_name not in instance['services']:
                raise KeyError(f'service \'{service_name}\' of windows of patient \'{patient_name}\' does not exists')
                
            for window in windows:
                if window[0] < min_day:
                    raise ValueError(f'window of service \'{service_name}\' of patient \'{patient_name}\' starts too early ({window[0]})')
                if window[1] > max_day:
                    raise ValueError(f'window of service \'{service_name}\' of patient \'{patient_name}\' ends too late ({window[1]})')


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