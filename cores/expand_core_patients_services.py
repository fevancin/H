import subprocess
from pathlib import Path


def get_max_possible_master_requests(master_instance):

    max_requests = {}
    for patient_name, patient in master_instance['patients'].items():
        for protocol in patient['protocols'].values():
            for protocol_service in protocol['protocol_services']:

                service_name = protocol_service['service']
                start = protocol_service['start'] + protocol['initial_shift']
                tolerance = protocol_service['tolerance']
                frequency = protocol_service['frequency']
                times = protocol_service['times']

                if times == 1:
                    for day_index in range(start - tolerance, start + tolerance):
                        
                        day_name = str(day_index)
                        
                        if day_name not in master_instance['days']:
                            continue

                        if day_name not in max_requests:
                            max_requests[day_name] = []
                        
                        max_requests[day_name].append({
                            'patient': patient_name,
                            'service': service_name
                        })
                    continue

                for central_day in range(start, start + times * frequency, frequency):
                    for day_index in range(central_day - tolerance, central_day + tolerance):
                        
                        day_name = str(day_index)
                        
                        if day_name not in master_instance['days']:
                            continue

                        if day_name not in max_requests:
                            max_requests[day_name] = []
                        
                        max_requests[day_name].append({
                            'patient': patient_name,
                            'service': service_name
                        })

    for day_name, day_max_requests in max_requests.items():
        
        unique_requests = []
        
        for request in day_max_requests:
        
            already_present = False
            for unique_request in unique_requests:
                if request['patient'] == unique_request['patient'] and request['service'] == unique_request['service']:
                    already_present = True
                    break
        
            if not already_present:
                unique_requests.append(request)
        
        max_requests[day_name] = unique_requests
    
    return max_requests


def remove_unfeasible_cores(master_instance, cores):
    
    max_capacities = {}
    for day_name, day in master_instance['days'].items():
        max_capacities[day_name] = {}
        for care_unit_name, care_unit in day.items():
            max_capacities[day_name][care_unit_name] = 0
            for operator in care_unit.values():
                max_capacities[day_name][care_unit_name] += operator['duration']
    
    valid_cores = []
    for core in cores:
        
        valid_days = []
        for day_name in core['days']:
            
            is_day_valid = True
            core_capacities = {}
            
            for component in core['components']:
                
                service_name = component['service']
                service_duration = master_instance['services'][service_name]['duration']
                care_unit_name = master_instance['services'][service_name]['care_unit']

                if care_unit_name not in core_capacities:
                    core_capacities[care_unit_name] = 0
                core_capacities[care_unit_name] += service_duration

                if core_capacities[care_unit_name] > max_capacities[day_name][care_unit_name]:
                    is_day_valid = False
                    break
            
            if is_day_valid:
                valid_days.append(day_name)
        
        if len(valid_days) > 0:
            valid_cores.append({
                'components': core['components'],
                'days': valid_days
            })
    
    return valid_cores


def expand_core_patients_services(cores, max_possible_master_requests, master_instance, expand_patients, expand_services, max_expansions_per_core):

    asp_input_file_path = Path('asp_input.lp')
    asp_program_file_path = Path('cores/match.lp')
    asp_output_file_path = Path('asp_output.txt')

    expanded_cores = []
    for core in cores:

        for day_name in core['days']:

            asp_input = []

            for core_component in core['components']:
                core_patient_name = core_component['patient']
                core_service_name = core_component['service']
                
                for request in max_possible_master_requests[day_name]:
                    request_patient_name = request['patient']
                    request_service_name = request['service']

                    is_valid_expansion = True

                    if not expand_patients and core_patient_name != request_patient_name:
                        is_valid_expansion = False
                    if not expand_services and core_service_name != request_service_name:
                        is_valid_expansion = False
                    
                    if expand_services:
                        
                        core_care_unit = master_instance['services'][core_service_name]['care_unit']
                        core_duration = master_instance['services'][core_service_name]['duration']
                        
                        request_care_unit = master_instance['services'][request_service_name]['care_unit']
                        request_duration = master_instance['services'][request_service_name]['duration']
                        
                        if core_care_unit != request_care_unit or core_duration > request_duration:
                            is_valid_expansion = False

                    if is_valid_expansion:
                        asp_input.append(f'arc({core_patient_name}, {core_service_name}, {request_patient_name}, {request_service_name}).\n')

            with open(asp_input_file_path, 'w') as file:
                file.writelines(asp_input)
            
            with open(asp_output_file_path, 'w') as file:
                subprocess.run([
                    'clingo', '-n', str(max_expansions_per_core), '--verbose=0',
                    asp_input_file_path, asp_program_file_path],
                    stdout=file)
            
            with open(asp_output_file_path, 'r') as file:
                lines = file.readlines()
            
            if lines[-1] == 'UNSATISFIABLE':
                continue

            for line in lines[:-1]:
                splitted_line = line.split('take(')
                
                expanded_components = []

                for token in splitted_line[1:]:
                    token = token.removesuffix('\n')
                    token = token.removesuffix(' ')
                    token = token.removesuffix(')')
                    patient_service_names = token.split(',')
                    expanded_components.append({
                        'patient': patient_service_names[2],
                        'service': patient_service_names[3]
                    })

                expanded_cores.append({
                    'components': expanded_components,
                    'days': day_name
                })
    
    asp_input_file_path.unlink()
    asp_output_file_path.unlink()

    if expand_services:
        expanded_cores = remove_unfeasible_cores(master_instance, expanded_cores)
    
    return expanded_cores