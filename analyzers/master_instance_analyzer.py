from analyzers.tools import common_main_analyzer


def get_total_window_number(master_instance):
    
    window_number = 0

    for patient in master_instance['patients'].values():
        for protocol in patient['protocols'].values():

            initial_shift = protocol['initial_shift']
            
            for protocol_service in protocol['protocol_services']:

                start = protocol_service['start'] + initial_shift
                tolerance = protocol_service['tolerance']
                frequency = protocol_service['frequency']
                times = protocol_service['times']

                if times == 1:

                    central_day_index = start
                    is_window_inside = False

                    for day_index in range(central_day_index - tolerance, central_day_index + tolerance + 1):

                        day_name = str(day_index)
                        if day_name in master_instance['days']:
                            is_window_inside = True
                            break
                    
                    if is_window_inside:
                        window_number += 1
                    
                    continue

                for central_day_index in range(start, start + frequency * times, frequency):

                    is_window_inside = False

                    for day_index in range(central_day_index - tolerance, central_day_index + tolerance + 1):

                        day_name = str(day_index)
                        if day_name in master_instance['days']:
                            is_window_inside = True
                            break
                    
                    if is_window_inside:
                        window_number += 1
        
    return window_number


def get_average_tolerance(master_instance):

    tolerance_sum = 0
    tolerance_number = 0
    for patient in master_instance['patients'].values():
        for protocol in patient['protocols'].values():
            for protocol_service in protocol['protocol_services']:
                tolerance_sum += protocol_service['tolerance']
                tolerance_number += 1
    
    return tolerance_sum / tolerance_number


def get_demand_vs_disponibility_by_day(master_instance):

    days_disponibility = {}
    for day_name, day in master_instance['days'].items():

        days_disponibility[day_name] = 0
        for care_unit in day.values():
            for operator in care_unit.values():
                days_disponibility[day_name] += operator['duration']

    worst_case_request_scenario = {day_name: 0 for day_name in master_instance['days'].keys()}

    for patient in master_instance['patients'].values():
        for protocol in patient['protocols'].values():

            initial_shift = protocol['initial_shift']
            
            for protocol_service in protocol['protocol_services']:

                service_name = protocol_service['service']
                service_duration = master_instance['services'][service_name]['duration']

                start = protocol_service['start'] + initial_shift
                tolerance = protocol_service['tolerance']
                frequency = protocol_service['frequency']
                times = protocol_service['times']

                if times == 1:

                    central_day_index = start
                    for day_index in range(central_day_index - tolerance, central_day_index + tolerance + 1):

                        day_name = str(day_index)
                        if day_name in master_instance['days']:
                            worst_case_request_scenario[day_name] += service_duration

                    continue

                for central_day_index in range(start, start + frequency * times, frequency):
                    for day_index in range(central_day_index - tolerance, central_day_index + tolerance + 1):

                        day_name = str(day_index)
                        if day_name in master_instance['days']:
                            worst_case_request_scenario[day_name] += service_duration

    requests_vs_disponibility = 0
    for day_name in worst_case_request_scenario:
        if worst_case_request_scenario[day_name] > 0:
            requests_vs_disponibility += worst_case_request_scenario[day_name] / days_disponibility[day_name]

    return requests_vs_disponibility / len(worst_case_request_scenario)


def get_total_time_slots_in_all_days(master_instance):

    time_slots_global_sum = 0

    for day in master_instance['days'].values():
        for care_unit in day.values():
            for operator in care_unit.values():
                time_slots_global_sum += operator['duration']
    
    return time_slots_global_sum


def get_average_time_slots_per_care_unit(master_instance):

    time_slots_global_sum = get_total_time_slots_in_all_days(master_instance)
    
    care_unit_number = 0
    for day in master_instance['days'].values():
        care_unit_number += len(day)
    
    return time_slots_global_sum / care_unit_number


def get_total_service_durations_requested(master_instance):
    
    total_service_durations = 0
    
    for patient in master_instance['patients'].values():
        for protocol in patient['protocols'].values():
            for protocol_service in protocol['protocol_services']:
                service_name = protocol_service['service']
                service_duration = master_instance['services'][service_name]['duration']
                total_service_durations += service_duration * protocol_service['times']

    return total_service_durations


def get_total_aggregate_demand_vs_disponibility(master_instance):

    total_demand = get_total_service_durations_requested(master_instance)
    total_disponibility = get_total_time_slots_in_all_days(master_instance)

    return total_demand / total_disponibility


def get_average_overlapping_windows_per_patient(master_instance):

    day_number = len(master_instance['days'].keys())
    min_day = min([int(day_name) for day_name in master_instance['days'].keys()])

    overlap_windows_number = 0

    for patient in master_instance['patients'].values():

        windows = []

        for protocol in patient['protocols'].values():
            
            initial_shift = protocol['initial_shift']
            
            for protocol_service in protocol['protocol_services']:

                start = protocol_service['start'] + initial_shift
                tolerance = protocol_service['tolerance']
                frequency = protocol_service['frequency']
                times = protocol_service['times']

                if times == 1:

                    central_day_index = start
                    window = {
                        'start': central_day_index - tolerance,
                        'end': central_day_index + tolerance
                    }

                    if window['start'] < min_day:
                        window['start'] = min_day
                    if window['end'] > min_day + day_number - 1:
                        window['end'] = min_day + day_number - 1
                    
                    if window['end'] >= window['start']:
                        windows.append(window)
                    
                    continue

                for central_day_index in range(start, start + frequency * times, frequency):

                    window = {
                        'start': central_day_index - tolerance,
                        'end': central_day_index + tolerance
                    }

                    if window['start'] < min_day:
                        window['start'] = min_day
                    if window['end'] > min_day + day_number - 1:
                        window['end'] = min_day + day_number - 1
                    
                    if window['end'] >= window['start']:
                        windows.append(window)
        
        for index in range(len(windows) - 1):
            for other_index in range(index + 1, len(windows)):
                if ((windows[index]['start'] <= windows[other_index]['start'] and windows[index]['end'] >= windows[other_index]['start']) or
                    (windows[other_index]['start'] <= windows[index]['start'] and windows[other_index]['end'] >= windows[index]['start'])):
                    overlap_windows_number += 1

    return overlap_windows_number / len(master_instance['patients'].keys())


def get_max_requests_in_same_day_per_patient(master_instance):

    day_number = len(master_instance['days'].keys())
    min_day = min([int(day_name) for day_name in master_instance['days'].keys()])

    global_max_overlap_windows = 0

    for patient_name, patient in master_instance['patients'].items():

        overlappings = [0 for _ in range(day_number)]

        for protocol in patient['protocols'].values():
            
            initial_shift = protocol['initial_shift']
            
            for protocol_service in protocol['protocol_services']:

                start = protocol_service['start'] + initial_shift
                tolerance = protocol_service['tolerance']
                frequency = protocol_service['frequency']
                times = protocol_service['times']

                if times == 1:

                    central_day_index = start
                    for day_index in range(central_day_index - tolerance, central_day_index + tolerance + 1):

                        if day_index < min_day or day_index >= day_number + min_day:
                            continue
                        
                        overlappings[day_index - min_day] += 1

                    continue

                for central_day_index in range(start, start + frequency * times, frequency):
                    for day_index in range(central_day_index - tolerance, central_day_index + tolerance + 1):

                        if day_index < min_day or day_index >= day_number + min_day:
                            continue
                        
                        overlappings[day_index - min_day] += 1

        max_overlap_windows = max(overlappings)
        if max_overlap_windows > global_max_overlap_windows:
            global_max_overlap_windows = max_overlap_windows
    
    return global_max_overlap_windows


def analyze_master_instance(master_instance, instance_path):

    data = {}

    window_number = get_total_window_number(master_instance)

    data['group'] = instance_path.parent.name
    data['instance'] = instance_path.name
    data['window_number'] = window_number
    data['average_windows_per_patient'] = window_number / len(master_instance['patients'])
    data['average_tolerance'] = get_average_tolerance(master_instance)
    data['average_time_slots_per_care_unit'] = get_average_time_slots_per_care_unit(master_instance)
    data['average_overlapping_requests_per_patient'] = get_average_overlapping_windows_per_patient(master_instance)
    data['max_requests_in_same_day_per_patient'] = get_max_requests_in_same_day_per_patient(master_instance)
    data['demand_vs_disponibility_by_day'] = get_demand_vs_disponibility_by_day(master_instance)
    data['total_aggregate_demand_vs_disponibility'] = get_total_aggregate_demand_vs_disponibility(master_instance)

    return data


if __name__ == '__main__':

    common_main_analyzer(
        command_name='Master instance analyzer',
        analyzer_function=analyze_master_instance,
        analysis_file_name='master_instance_analysis.csv',
        need_results=False)