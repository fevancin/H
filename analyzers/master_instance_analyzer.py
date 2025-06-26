def get_total_window_number(master_instance):
    
    window_number = 0
    for patient in master_instance['patients'].values():
        window_number += sum(len(windows) for windows in patient['requests'].values())

    return window_number


def get_average_tolerance(master_instance):

    tolerance_sum = 0
    tolerance_number = 0
    for patient in master_instance['patients'].values():
        for windows in patient['requests'].values():
            for window in windows:
                tolerance_sum += (window[1] - window[0]) * 0.5
                tolerance_number += 1
    
    return tolerance_sum / tolerance_number


def get_demand_vs_disponibility_by_day(master_instance):

    days_disponibility = {int(day_name): sum(o['duration'] for c in d.values() for o in c.values())
        for day_name, d in master_instance['days'].items()}

    worst_scenario = {int(day_name): 0 for day_name in master_instance['days'].keys()}

    for patient in master_instance['patients'].values():
        for service_name, windows in patient['requests'].items():
            service_duration = master_instance['services'][service_name]['duration']
            for window in windows:
                for day_index in range(window[0], window[1] + 1):
                    worst_scenario[day_index] += service_duration

    requests_vs_disponibility = sum(worst_scenario[day_index] / days_disponibility[day_index] for day_index in worst_scenario)

    return requests_vs_disponibility / len(worst_scenario)


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
        for service_name, windows in patient['requests'].items():
            service_duration = master_instance['services'][service_name]['duration']
            total_service_durations += service_duration * len(windows)

    return total_service_durations


def get_total_aggregate_demand_vs_disponibility(master_instance):

    total_demand = get_total_service_durations_requested(master_instance)
    total_disponibility = get_total_time_slots_in_all_days(master_instance)

    return total_demand / total_disponibility


def get_average_overlapping_windows_per_patient(master_instance):

    overlap_windows_number = 0

    for patient in master_instance['patients'].values():
        
        all_patient_windows = []
        
        for windows in patient['requests'].values():
            all_patient_windows.extend(windows)
        
        if len(all_patient_windows) == 0:
            continue
        
        for i in range(len(all_patient_windows) - 1):
            window = all_patient_windows[i]
            for j in range(i + 1, len(all_patient_windows)):
                other_window = all_patient_windows[j]
                if ((window[0] <= other_window[0] and window[1] >= other_window[0]) or
                    (other_window[0] <= window[0] and other_window[1] >= window[0])):
                    overlap_windows_number += 1

    return overlap_windows_number / len(master_instance['patients'].keys())


def get_max_requests_in_same_day_per_patient(master_instance):

    max_overlap = 0

    for patient in master_instance['patients'].values():

        overlaps = {int(day_name): 0 for day_name in master_instance['days'].keys()}

        for windows in patient['requests'].values():
            for window in windows:
                for day_index in range(window[0], window[1] + 1):
                    overlaps[day_index] += 1
        
        max_patient_overlap = max(overlap for overlap in overlaps.values())
        if max_patient_overlap > max_overlap:
            max_overlap = max_patient_overlap
    
    return max_overlap


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