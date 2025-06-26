from pathlib import Path
import argparse
import json
import time

def check_service(service, service_name):

    if type(service) is not dict:
        raise TypeError(f'service \'{service_name}\' is not a dict')
    if len(service) != 2:
        raise ValueError(f'service \'{service_name}\' has not the correct form')

    if 'care_unit' not in service:
        raise KeyError(f'service \'{service_name}\' has not a care unit')
    if type(service['care_unit']) is not str:
        raise ValueError(f'service \'{service_name}\' care unit is not a string')

    if 'duration' not in service:
        raise KeyError(f'service \'{service_name}\' has not a duration')
    if type(service['duration']) is not int or service['duration'] <= 0:
        raise ValueError(f'service \'{service_name}\' duration is not a positive integer')


def check_services(services):

    if type(services) is not dict:
        raise KeyError('\'services\' is not an dict')
    
    for service_name, service in services.items():
    
        if type(service_name) is not str:
            raise KeyError(f'\'{service_name}\' is not a string')
        
        check_service(service, service_name)
        

def check_operator(operator, operator_name, care_unit_name, day_name):

    if type(operator) is not dict:
        raise TypeError(f'operator \'{operator_name}\' of care unit \'{care_unit_name}\' of day \'{day_name}\' is not a dict')
    if len(operator) != 2:
        raise KeyError(f'operator \'{operator_name}\' of care unit \'{care_unit_name}\' of day \'{day_name}\' has not the correct form')

    if 'start' not in operator:
        raise KeyError(f'operator \'{operator_name}\' of care unit \'{care_unit_name}\' of day \'{day_name}\' has not a care unit')
    if type(operator['start']) is not int or operator['start'] < 0:
        raise ValueError(f'operator \'{operator_name}\' of care unit \'{care_unit_name}\' of day \'{day_name}\' start is not a non-negative integer')

    if 'duration' not in operator:
        raise KeyError(f'operator \'{operator_name}\' of care unit \'{care_unit_name}\' of day \'{day_name}\' has not a duration')
    if type(operator['duration']) is not int or operator['duration'] <= 0:
        raise ValueError(f'operator \'{operator_name}\' of care unit \'{care_unit_name}\' of day \'{day_name}\' duration is not a positive integer')


def check_care_unit(care_unit, care_unit_name, day_name):

    if type(care_unit) is not dict:
        raise TypeError(f'care_unit \'{care_unit_name}\' of day \'{day_name}\' is not a dict')

    for operator_name, operator in care_unit.items():
        
        if type(operator_name) is not str:
            raise KeyError(f'\'{operator_name}\' of care_unit \'{care_unit_name}\' of day \'{day_name}\' is not a string')
        
        check_operator(operator, operator_name, care_unit_name, day_name)


def check_day(day, day_name):

    if type(day) is not dict:
        raise TypeError(f'day {day_name} is not a dict')

    for care_unit_name, care_unit in day.items():
        
        if type(care_unit_name) is not str:
            raise KeyError(f'care unit \'{care_unit_name}\' of day \'{day_name}\' is not a string')
        
        check_care_unit(care_unit, care_unit_name, day_name)


def check_results_general_shape(results):

    for key in ['scheduled', 'rejected']:
        if key not in results:
            raise KeyError(f'\'{key}\' is not present in instance results')

    if len(results) != 3:
        if len(results) == 4 and 'info' not in results:
            raise KeyError('Unknown keys in instance')
        else:
            raise KeyError('Unknown keys in instance')
    

def check_schedule_item_without_window(schedule_item, day_name=None):

    if type(schedule_item) is not dict:
        raise TypeError(f'day \'{day_name}\' schedule item is not a dict')
    if len(schedule_item) != 2:
        raise ValueError(f'day \'{day_name}\' schedule item has not the correct form')

    for key in ['patient', 'service']:
        
        if key not in schedule_item:
            raise KeyError(f'\'{key}\' is not present in schedule_item of day \'{day_name}\'')
        if type(schedule_item[key]) is not str:
            raise ValueError(f'schedule_item of day \'{day_name}\' \'{key}\' is not a string')
        

def check_schedule_without_window(schedule, day_name=None):

    if type(schedule) is not list:
        raise TypeError(f'day \'{day_name}\' schedule is not a list')
    
    for schedule_item in schedule:
        check_schedule_item_without_window(schedule_item, day_name)


def check_schedule_item_with_window(schedule_item):

    if type(schedule_item) is not dict:
        raise TypeError(f'a rejected item is not a dict')
    if len(schedule_item) != 3:
        raise ValueError(f'a rejected item has not the correct form')

    for key in ['patient', 'service']:
        
        if key not in schedule_item:
            raise KeyError(f'\'{key}\' is not present in a rejected item')
        if type(schedule_item[key]) is not str:
            raise ValueError(f'a rejected item \'{key}\' is not a string')
        
    if 'window' not in schedule_item:
        raise KeyError(f'\'window\' is not present in a rejected item')
    if type(schedule_item['window']) is not list or len(schedule_item['window']) != 2:
        raise ValueError(f'a rejected item \'window\' is not a two item list')
    if type(schedule_item['window'][0]) is not int or schedule_item['window'][0] < 0:
        raise ValueError(f'a rejected item \'window\' first item is not a valid integer')
    if type(schedule_item['window'][1]) is not int or schedule_item['window'][1] < schedule_item['window'][0]:
        raise ValueError(f'a rejected item \'window\' second item is not a valid integer')
    

def check_schedules_with_window(schedules):
    
    if type(schedules) is not list:
        raise TypeError(f'\'rejected\' is not a list')

    for schedule_item in schedules:
        check_schedule_item_with_window(schedule_item)


def check_schedule_item_with_time(schedule_item, day_name=None):

    if type(schedule_item) is not dict:
        raise TypeError(f'schedule item of day \'{day_name}\' is not a dict')
    if len(schedule_item) != 5:
        raise ValueError(f'schedule item of day \'{day_name}\' has not the correct form')

    for key in ['patient', 'service', 'care_unit', 'operator']:

        if key not in schedule_item:
            raise KeyError(f'\'{key}\' is not present in schedule item of day \'{day_name}\'')
        if type(schedule_item[key]) is not str:
            raise ValueError(f'schedule item of day \'{day_name}\' \'{key}\' is not a string')
        
    if 'time' not in schedule_item:
        raise KeyError(f'\'time\' is not present in schedule item of day \'{day_name}\'')
    if type(schedule_item['time']) is not int or schedule_item['time'] < 0:
        raise ValueError(f'schedule item of day \'{day_name}\' \'time\' is not a non-negative integer')


def check_schedule_with_time(schedule, day_name=None):
    
    if type(schedule) is not list:
        raise TypeError(f'\'scheduled\' is not a list')

    for schedule_item in schedule:
        check_schedule_item_with_time(schedule_item, day_name)


def check_integrity_schedule_basic(schedule, instance, day_name=None):

    for index, schedule_item in enumerate(schedule):

        patient_name = schedule_item['patient']
        if patient_name not in instance['patients']:
            raise KeyError(f'patient \'{patient_name}\' of schedule {index} of day \'{day_name}\' does not exists')
        
        service_name = schedule_item['service']
        if service_name not in instance['services']:
            raise KeyError(f'service \'{service_name}\' of schedule {index} of day \'{day_name}\' does not exists')


def check_integrity_schedule_with_window(schedule, instance):

    check_integrity_schedule_basic(schedule, instance)


def check_integrity_total_request_durations_per_care_unit(schedule, instance, day_name):

    total_request_durations_per_care_unit = {}

    for index, schedule_item in enumerate(schedule):

        service_name = schedule_item['service']
        service = instance['services'][service_name]
        care_unit_name = service['care_unit']
        duration = service['duration']
    
        if care_unit_name not in total_request_durations_per_care_unit:
            total_request_durations_per_care_unit[care_unit_name] = 0
        total_request_durations_per_care_unit[care_unit_name] += duration

    for care_unit_name, total_request_duration in total_request_durations_per_care_unit.items():
        
        if care_unit_name not in instance['days'][day_name]:
            raise KeyError(f'care unit \'{care_unit_name}\' is not present in day \'{day_name}\'')
        
        total_care_unit_disponibility = 0
        for operator in instance['days'][day_name][care_unit_name].values():
            total_care_unit_disponibility += operator['duration']
        
        if total_request_duration > total_care_unit_disponibility:
            raise ValueError(f'total requests for care unit \'{care_unit_name}\' of day \'{day_name}\' exceed disponibility')


def check_integrity_total_request_durations_per_operator(schedule, instance, day_name, day=None):

    remaining_operator_disponibility = {}

    if day is None:
        day = instance['days'][day_name]

    for care_unit_name, care_unit in day.items():
        remaining_operator_disponibility[care_unit_name] = {}
        for operator_name, operator in care_unit.items():
            remaining_operator_disponibility[care_unit_name][operator_name] = operator['duration']

    for index, schedule_item in enumerate(schedule):

        service_name = schedule_item['service']
        service_duration = instance['services'][service_name]['duration']
        care_unit_name = schedule_item['care_unit']
        operator_name = schedule_item['operator']
        
        remaining_operator_disponibility[care_unit_name][operator_name] -= service_duration
        if remaining_operator_disponibility[care_unit_name][operator_name] < 0:
            raise ValueError(f'operator \'{operator_name}\' of care unit \'{care_unit_name}\' is overloaded')


def check_integrity_schedule_with_time_overlap(schedule, instance, day_name=None):

    if len(schedule) <= 1:
        return
    
    for index in range(len(schedule) - 1):
        schedule_item = schedule[index]
        for other_index in range(index + 1, len(schedule)):
            other_schedule_item = schedule[other_index]
            
            is_same_patient = (schedule_item['patient'] == other_schedule_item['patient'])
            is_same_operator = (schedule_item['care_unit'] == other_schedule_item['care_unit'] and
                                schedule_item['operator'] == other_schedule_item['operator'])
            
            if not is_same_patient and not is_same_operator:
                continue

            service_duration = instance['services'][schedule_item['service']]['duration']
            other_service_duration = instance['services'][other_schedule_item['service']]['duration']

            if ((schedule_item['time'] <= other_schedule_item['time'] and schedule_item['time'] + service_duration > other_schedule_item['time']) or
                (other_schedule_item['time'] <= schedule_item['time'] and other_schedule_item['time'] + other_service_duration > schedule_item['time'])):
                service_name = schedule_item['service']
                patient_name = schedule_item['patient']
                other_service_name = other_schedule_item['service']
                other_patient_name = other_schedule_item['patient']
                raise ValueError(f'schedules {index} ({patient_name}, {service_name}) and {other_index} ({other_patient_name}, {other_service_name}) collide on day \'{day_name}\'')


def check_integrity_schedule_with_time(schedule, instance, day_name=None):

    check_integrity_schedule_basic(schedule, instance, day_name)
    
    day = instance['day'] if day_name is None else instance['days'][day_name]
    check_integrity_total_request_durations_per_operator(schedule, instance, day_name, day)

    for schedule_item in schedule:
        
        patient_name = schedule_item['patient']
        service_name = schedule_item['service']

        care_unit_name = schedule_item['care_unit']
        if care_unit_name not in day:
            raise KeyError(f'care unit \'{care_unit_name}\' requested by patient \'{patient_name}\' and service \'{service_name}\' does not exists')
        
        operator_name = schedule_item['operator']
        if operator_name not in day[care_unit_name]:
            raise KeyError(f'operator \'{operator_name}\' of care unit \'{care_unit_name}\' requested by patient \'{patient_name}\' and service \'{service_name}\' does not exists')
        
        service_care_unit = instance['services'][service_name]['care_unit']
        service_duration = instance['services'][service_name]['duration']

        if service_care_unit != care_unit_name:
            raise ValueError(f'care unit \'{service_care_unit}\' of service \'{service_name}\' of patient \'{patient_name}\' is not coherent with care unit \'{care_unit_name}\'')

        operator = day[care_unit_name][operator_name]
        start = schedule_item['time']
        if start < operator['start'] or start + service_duration > operator['start'] + operator['duration']:
            raise ValueError(f'activity time of operator \'{operator_name}\' of care unit \'{operator_name}\' is incoherent with time {start} of service \'{service_name}\' of patient \'{patient_name}\'')

    check_integrity_schedule_with_time_overlap(schedule, instance, day_name)


def get_protocol_service_windows(protocol_service, max_day_index):

    start = protocol_service['start']
    tolerance = protocol_service['tolerance']
    frequency = protocol_service['frequency']
    times = protocol_service['times']

    if times == 1:
        windows = [{
            'start': start - tolerance,
            'end': start + tolerance
        }]
    else:
        windows = []
        for middle_day in range(start, start + frequency * times, frequency):
            windows.append({
                'start': middle_day - tolerance,
                'end': middle_day + tolerance
            })
    
    for window in windows:
        if window['start'] < 0:
            window['start'] = 0
        if window['end'] > max_day_index:
            window['end'] = max_day_index
    
    return windows


def get_protocol_windows(protocol, max_day_index):

    windows = {}
    for protocol_service in protocol['protocol_services']:
        service_name = protocol_service['service']
        if service_name not in windows:
            windows[service_name] = []
        windows[service_name].extend(get_protocol_service_windows(protocol_service, max_day_index))
    
    return windows


def get_patient_windows(patient, max_day_index):

    patient_windows = {}

    for protocol in patient['protocols'].values():
        
        protocol_windows = get_protocol_windows(protocol, max_day_index)
        for service_name, windows in protocol_windows.items():
            if service_name not in patient_windows:
                patient_windows[service_name] = []
            patient_windows[service_name].extend(windows)

    return patient_windows


def get_patients_windows(patients, max_day_index):

    patients_windows = {}
    for patient_name, patient in patients.items():
        patients_windows[patient_name] = get_patient_windows(patient, max_day_index)
    
    return patients_windows


def check_integrity_protocols_represented(results, instance):

    for day_name, schedule in results['scheduled'].items():
        day_index = int(day_name)
        
        for schedule_item in schedule:
            patient_name = schedule_item['patient']
            service_name = schedule_item['service']
            
            if patient_name not in instance['patients'] or service_name not in instance['patients'][patient_name]['requests']:
                raise ValueError(f'patient \'{patient_name}\' do not request service \'{service_name}\'')
            
            window_found = False
            for window in instance['patients'][patient_name]['requests'][service_name]:
                if window[0] <= day_index and window[1] >= day_index:
                    window_found = True
                    break
            if not window_found:
                print(instance['patients'][patient_name]['requests'][service_name])
                raise ValueError(f'patient \'{patient_name}\' do not request service \'{service_name}\' in day \'{day_name}\'')
            
    # for schedule_item in results['rejected']:

    #     patient_name = schedule_item['patient']
    #     service_name = schedule_item['service']
    #     window = schedule_item['window']

    #     if patient_name not in patients_windows:
    #         raise ValueError(f'patient \'{patient_name}\' already fully satisfied (no service \'{service_name}\' with window [{window[0]}, {window[1]}])')
    #     if service_name not in patients_windows[patient_name]:
    #         raise ValueError(f'patient \'{patient_name}\' do not request service \'{service_name}\' with window [{window[0]}, {window[1]}]')
        
    #     window_found = False
    #     remaining_windows = []
    #     for patient_window in patients_windows[patient_name][service_name]:
    #         if patient_window['start'] == window[0] and patient_window['end'] == window[1]:
    #             window_found = True
    #         else:
    #             remaining_windows.append(patient_window)
    #     if not window_found:
    #         raise ValueError(f'patient \'{patient_name}\' do not request service \'{service_name}\' in window [{window[0]}, {window[1]}]')
        
    #     if len(remaining_windows) == 0:
    #         del patients_windows[patient_name][service_name]
    #     else:
    #         patients_windows[patient_name][service_name] = remaining_windows
        
    #     if len(patients_windows[patient_name]) == 0:
    #         del patients_windows[patient_name]

    # if len(patients_windows) != 0:
    #     raise ValueError(f'some request are not in the results: {patients_windows}')