def custom_count(value, maxs):
    """Passing a list of integers, this function returns the next value in the
    counting sequence, treating each element as a digit. The maxs list give the
    maximum value (exclusive) for each digit, after that there is a remainder."""
    index = 0
    while index < len(value):
        value[index] += 1
        if value[index] < maxs[index]:
            return value
        value[index] = 0
        index += 1
    return None


def is_contained(small_day, big_day):
    """Function that search a match between two set of [start-duration] intervals.
    Each one of the first group must be contained in one of the second group without
    intersecting eachother. Some optimization are implemented in order to give
    a better performance when is not necessary to solve the full problem."""

    # trivial cases
    if len(small_day) == 0:
        return True
    if len(big_day) == 0:
        return False
    
    # check if the operators are the same; useful if the schedule is periodic
    if len(small_day) == len(big_day):
        are_days_equal = True
        for operator, other_operator in zip(small_day.values(), big_day.values()):
            if operator["start"] != other_operator["start"] or operator["duration"] != other_operator["duration"]:
                are_days_equal = False
                break
        if are_days_equal:
            return True

    # dictionary that contain all the possible choices for the match
    possible_choices = dict()

    for small_operator_name, small_operator in small_day.items():
        possible_choices[small_operator_name] = list()
        for big_operator_name, big_operator in big_day.items():

            # add to the domain all big_operators that can contain the small one
            if small_operator["start"] >= big_operator["start"] and small_operator["start"] + small_operator["duration"] <= big_operator["start"] + big_operator["duration"]:
                possible_choices[small_operator_name].append(big_operator_name)
        
        # if a domain is empty, no match is possible
        if len(possible_choices[small_operator_name]) == 0:
            return False
        
    # list of all the small_operator that intersect
    incompatibility = list()

    for small_operator_name, small_operator in small_day.items():
        for other_small_operator_name, other_small_operator in small_day.items():

            # no self checks
            if other_small_operator_name == small_operator_name:
                continue

            # add the couple if the two operator intersect
            if small_operator["start"] <= other_small_operator["start"] and small_operator["start"] + small_operator["duration"] > other_small_operator["start"]:
                incompatibility.append((small_operator_name, other_small_operator_name))

    # if there are no conflicts, every match is a good one
    if len(incompatibility) == 0:
        return True
    
    # if a small operator have no conflicts it can be omitted, as every of its choiches is valid
    for small_operator_name in small_day.keys():
        is_present = False
        for couple in incompatibility:
            if small_operator_name == couple[0] or small_operator_name == couple[1]:
                is_present = True
                break
        if not is_present:
            del possible_choices[small_operator_name]
    
    names = list()
    value = list()
    maxs = list()
    for small_operator_name, domain in possible_choices.items():
        names.append(small_operator_name)
        value.append(0)
        maxs.append(len(domain))
    
    # enumerate all the assignable choices
    while value is not None:

        # test for overlaps in small operators that have chosen the same big operator
        is_valid_assignment = True
        for index in range(len(value) - 1):
            name = names[index]

            for other_index in range(index + 1, len(value)):
                other_name = names[other_index]

                if possible_choices[name][value[index]] == possible_choices[other_name][value[other_index]]:
                    if (name, other_name) in incompatibility or (other_name, name) in incompatibility:
                        is_valid_assignment = False
                        break
                if not is_valid_assignment:
                    break
        
        # if no overlaps is found the assignment is valid
        if is_valid_assignment:
            return True

        value = custom_count(value, maxs)

    return False


def compute_expanded_days(instance):

    # compute the total operator duration, grouped by day and care unit
    total_duration = {}
    for day_name, day in instance['days'].items():
        total_duration[day_name] = {}
        for care_unit_name, care_unit in day.items():
            total_duration[day_name][care_unit_name] = sum([operator['duration'] for operator in care_unit.values()])

    # get all care unit names only once
    care_unit_names = set()
    for day in instance['days'].values():
        care_unit_names.update(day.keys())

    subsumptions = {}

    # compute subsumptions for each separate care unit
    for care_unit_name in care_unit_names:
        subsumptions[care_unit_name] = {}

        for day_name, day in instance['days'].items():

            # all days that can be contained in the current one
            smaller_days = set()

            for other_day_name, other_day in instance['days'].items():

                # no reflexive checks (they are implicitly defined)
                if other_day_name == day_name:
                    continue
                # impossible match if total duration is smaller
                if total_duration[day_name][care_unit_name] < total_duration[other_day_name][care_unit_name]:
                    continue
                # jump to next day if current one is already known to be smaller
                if other_day_name in smaller_days:
                    continue

                # add subsumption if other_day is contained in day
                if is_contained(other_day[care_unit_name], day[care_unit_name]):
                    smaller_days.add(other_day_name)

                    # transitivity check for already processed days
                    if other_day_name in subsumptions[care_unit_name]:
                        smaller_days.update(subsumptions[care_unit_name][other_day_name])
            
            if day_name in smaller_days:
                smaller_days.remove(day_name)
                
            # do not add empty lists in the output
            if len(smaller_days) > 0:
                subsumptions[care_unit_name][day_name] = sorted(smaller_days, key=lambda v: int(v))
            

    return subsumptions


def expand_core_days(master_instance, cores, subsumptions):

    for core in cores:

        if len(core['days']) == 0 or len(core['components']) == 0:
            continue

        care_unit_affected = set()
        for component in core['components']:
            service_name = component['service']
            care_unit_affected.add(master_instance['services'][service_name]['care_unit'])

        day_name = core['days'][0]

        first_care_unit_affected = care_unit_affected.pop()
        subsumed_day_names = set(subsumptions[first_care_unit_affected][day_name])
        for care_unit_name in care_unit_affected:
            subsumed_day_names.intersection_update(subsumptions[care_unit_name][day_name])
            if len(subsumed_day_names) == 0:
                break

        if len(subsumed_day_names) == 0:
            continue

        core['days'].extend(subsumed_day_names)
        core['days'] = sorted(set(core['days']))


def remove_core_days_without_exact_requests(cores, max_possible_master_requests):
    
    valid_cores = []
    for core in cores:
    
        valid_days = []
        for day_name in core['days']:
    
            is_core_valid_on_this_day = True
            for core_component in core['components']:
    
                is_request_present = False
                for request in max_possible_master_requests[day_name]:
                    if request['patient'] == core_component['patient'] and request['service'] == core_component['service']:
                        is_request_present = True
                        break
    
                if not is_request_present:
                    is_core_valid_on_this_day = False
                    break
    
            if is_core_valid_on_this_day:
                valid_days.append(day_name)
    
        if len(valid_days) > 0:
            core['days'] = valid_days
            valid_cores.append(core)
    
    return valid_cores