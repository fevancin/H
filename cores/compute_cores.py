import pyomo.environ as pyo


def compute_dumb_cores(all_subproblem_results):
    
    cores = []
    
    for day_name, subproblem_results in all_subproblem_results.items():
        
        if len(subproblem_results['rejected']) == 0:
            continue

        components = []

        for scheduled_request in subproblem_results['scheduled']:
            components.append({
                'patient': scheduled_request['patient'],
                'service': scheduled_request['service']
            })

        for rejected_request in subproblem_results['rejected']:
            components.append({
                'patient': rejected_request['patient'],
                'service': rejected_request['service']
            })
        
        cores.append({
            'components': components,
            'days': [str(day_name)]
        })

    return cores


def compute_basic_cores(all_subproblem_results):
    
    cores = []
    
    for day_name, subproblem_results in all_subproblem_results.items():
        
        if len(subproblem_results['rejected']) == 0:
            continue

        scheduled_components = []

        for scheduled_request in subproblem_results['scheduled']:
            scheduled_components.append({
                'patient': scheduled_request['patient'],
                'service': scheduled_request['service']
            })

        for rejected_request in subproblem_results['rejected']:
            
            components = scheduled_components.copy()
            components.append({
                'patient': rejected_request['patient'],
                'service': rejected_request['service']
            })
            
            cores.append({
                'components': components,
                'days': [str(day_name)]
            })

    return cores


def compute_reduced_cores(all_subproblem_results, master_instance):
    
    cores = []

    for day_name, day_results in all_subproblem_results.items():
        
        if len(day_results['rejected']) == 0:
            continue

        # generate a core for every single not satisfied service
        for rejected_request in day_results['rejected']:

            rejected_patient_name = rejected_request['patient']
            rejected_service_name = rejected_request['service']

            core_components = []

            # perform a visit adding all request that have a care unit or patient involved in the core
            care_units_to_do = set([master_instance['services'][rejected_service_name]['care_unit']])
            patients_to_do = set([rejected_patient_name])
            care_units_done = set()
            patients_done = set()

            while len(care_units_to_do) > 0 or len(patients_to_do) > 0:

                # add all (patient, services) of a specific care unit
                if len(care_units_to_do) > 0:
                    care_unit_to_do = care_units_to_do.pop()

                    # search in all satisfied services
                    for scheduled_service in day_results['scheduled']:

                        patient_name = scheduled_service['patient']
                        service_name = scheduled_service['service']

                        if scheduled_service['care_unit'] == care_unit_to_do:
                            
                            core_components.append({
                                'patient': patient_name,
                                'service': service_name
                            })

                            if patient_name not in patients_done:
                                patients_to_do.add(patient_name)

                    care_units_done.add(care_unit_to_do)

                # add all (patient, service) of a specific patient
                if len(patients_to_do) > 0:
                    patient_to_do = patients_to_do.pop()

                    for scheduled_service in day_results['scheduled']:

                        patient_name = scheduled_service['patient']
                        service_name = scheduled_service['service']
                        care_unit_name = scheduled_service['care_unit']

                        if patient_name == patient_to_do:
                            core_components.append({
                                'patient': patient_to_do,
                                'service': service_name
                                })
                            if care_unit_name not in care_units_done:
                                care_units_to_do.add(care_unit_name)

                    patients_done.add(patient_to_do)

            # remove duplicates from the core
            # for patient_name, services in core_components.items():
            #     core_components[patient_name] = list(set(services))

            cores.append({
                'components': core_components,
                'days': [day_name]
            })

    return cores


def aggregate_and_remove_duplicate_cores(new_cores, prev_cores):

    real_new_cores = []
    for new_core in new_cores:
        
        prev_found_core = None
        for prev_core in prev_cores:

            if len(new_core['components']) != len(prev_core['components']):
                continue
            
            are_components_exactly_the_same = True
            for new_core_component in new_core['components']:
                
                is_component_present_in_prev = False
                for prev_core_component in prev_core['components']:
                    if new_core_component['patient'] == prev_core_component['patient'] and new_core_component['service'] == prev_core_component['service']:
                        is_component_present_in_prev = True
                        break
                
                if not is_component_present_in_prev:
                    are_components_exactly_the_same = False
                    break
            
            if are_components_exactly_the_same:
                prev_found_core = prev_core
                break

        if prev_found_core is None:
            real_new_cores.append(new_core)
            prev_cores.append(new_core)
            continue

        days_not_in_prev_core = []
        for day_name in new_core['days']:
            if day_name not in prev_found_core['days']:
                days_not_in_prev_core.append(day_name)
        
        new_core['days'] = days_not_in_prev_core
        if len(days_not_in_prev_core) > 0:
            prev_found_core['days'].extend(days_not_in_prev_core)
            real_new_cores.append(new_core)
    
    return real_new_cores, prev_cores


def add_cores_constraint_class_to_master_model(master_model):
    
    master_model.cores = pyo.ConstraintList()


def add_cores_constraints_to_master_model(master_model, cores):

    for core in cores:

        if len(core['components']) == 0:
            continue

        for day_name in core['days']:

            core_size = len(core['components'])
            expression = 0
            is_core_valid = True

            for core_component in core['components']:

                patient_name = core_component['patient']
                service_name = core_component['service']
                
                if (patient_name, service_name, int(day_name)) not in master_model.do_index:
                    is_core_valid = False
                    break

                expression += master_model.do[patient_name, service_name, int(day_name)]

            if is_core_valid:
                master_model.cores.add(expr=(expression <= core_size - 1))