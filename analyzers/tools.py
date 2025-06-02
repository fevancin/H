def get_subproblem_results_value(master_instance, master_results, day_name):

    is_priority = True
    for patient in master_instance['patients'].values():
        if 'priority' not in patient:
            is_priority = False
            break

    value = 0
    for schedule_item in master_results['scheduled'][day_name]:
        
        service_name = schedule_item['service']
        service_duration = master_instance['services'][service_name]['duration']
        
        if is_priority:
            
            patient_name = schedule_item['patient']
            patient_priority = master_instance['patients'][patient_name]['priority']
            
            value += service_duration * patient_priority
        
        else:
            value += service_duration
    
    return value


def get_master_results_value(master_instance, master_results):

    value = 0
    for day_name in master_results['scheduled']:
        value += get_subproblem_results_value(master_instance, master_results, day_name)
    
    return value


def get_satisfied_window_number(master_results):

    satisfied_window_number = 0
    for day in master_results['scheduled'].values():
        satisfied_window_number += len(day)
    
    return satisfied_window_number


def get_requests_per_patient_same_day(master_results):

    total_average = 0
    true_minimum = None
    true_maximum = None

    for day in master_results['scheduled'].values():
        
        patient_names = set()
        for request in day:
            patient_names.add(request['patient'])
    
        services_per_patient = []
        for patient_name in patient_names:

            request_number = 0
            for request in day:
                if request['patient'] == patient_name:
                    request_number += 1
            services_per_patient.append(request_number)
        

        average = sum(services_per_patient) / len(patient_names)
        
        minimum = min(services_per_patient)
        maximum = max(services_per_patient)
        
        if true_minimum is None or minimum < true_minimum:
            true_minimum = minimum
        if true_maximum is None or maximum > true_maximum:
            true_maximum = maximum

        total_average += average
    
    return true_minimum, true_maximum, total_average / len(master_results['scheduled'])


def analyze_master_results(master_instance, master_results, instance_path):
    
    data = {}
    data['group'] = instance_path.parent.name
    data['instance'] = instance_path.stem
    data = master_results['info']
    data['satisfied_window_number'] = get_satisfied_window_number(master_results)
    data['rejected_window_number'] = len(master_results['rejected'])
    data['solution_value'] = get_master_results_value(master_instance, master_results)

    minimum, maximum, average = get_requests_per_patient_same_day(master_results)
    data['average_requests_per_patient_same_day'] = average
    data['min_requests_per_patient_same_day'] = minimum
    data['max_requests_per_patient_same_day'] = maximum
    
    return data