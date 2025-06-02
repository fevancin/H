import pyomo.environ as pyo

from solvers.tools import clamp


def get_master_model(instance, additional_info):

    max_day_number = max([int(d) for d in instance['days'].keys()])

    # priorities are used if present in all the patients and are not all the same value
    if 'use_patient_priority' not in additional_info:
        use_priorities = False
    else:
        are_priorities_always_present = True
        are_all_priorities_the_same = True
        priority_value = None

        for patient in instance['patients'].values():
        
            if 'priority' not in patient:
                are_priorities_always_present = False
                break
        
            if priority_value is None:
                priority_value = patient['priority']
            if priority_value is not None and priority_value != patient['priority']:
                are_all_priorities_the_same = False
                break

        use_priorities = are_priorities_always_present and not are_all_priorities_the_same
        del are_all_priorities_the_same, priority_value, are_priorities_always_present

    model = pyo.ConcreteModel()

    ############################ MODEL SETS AND INDEXES ############################

    # all service names
    model.services = pyo.Set(initialize=sorted(instance['services'].keys()))

    # all days (casted to int)
    model.days = pyo.Set(initialize=sorted([int(d) for d in instance['days'].keys()]), domain=pyo.NonNegativeIntegers)

    # all (days, care_units) couples
    model.care_units = pyo.Set(initialize=sorted([(int(d), c) for d, day in instance['days'].items() for c in day.keys()]))

    # all patient names
    model.patients = pyo.Set(initialize=sorted(instance['patients'].keys()))

    # triplets (day, care_unit, operator) for each operator available
    model.operators = pyo.Set(initialize=[(int(d), c, o)
                                        for d, day in instance['days'].items()
                                        for c, cu in day.items()
                                        for o in cu.keys()])

    ############################### MODEL PARAMETERS ###############################

    @model.Param(model.services, domain=pyo.Any, mutable=False)
    def service_care_unit(model, s):
        return instance['services'][s]['care_unit']

    @model.Param(model.services, domain=pyo.PositiveIntegers, mutable=False)
    def service_duration(model, s):
        return instance['services'][s]['duration']

    # capacity[d, c] is the duration sum of each operator
    @model.Param(model.care_units, domain=pyo.NonNegativeIntegers, mutable=False)
    def capacity(model, d, c):
        return sum([o['duration'] for o in instance['days'][str(d)][c].values()])

    if use_priorities:
        @model.Param(model.patients, domain=pyo.PositiveIntegers, mutable=False)
        def patient_priority(model, p):
            return instance['patients'][p]['priority']

    # this variable stores a set of quadruples (patient, service, start, end) for
    # each interval requested by some protocol
    windows = set()

    # unravel each protocol service
    for patient_name, patient in instance['patients'].items():
        for protocol_name, protocol in patient['protocols'].items():
            for protocol_service in protocol['protocol_services']:

                day = protocol_service['start'] + protocol['initial_shift']
                service_name = protocol_service['service']
                tolerance = protocol_service['tolerance']
                frequency = protocol_service['frequency']

                # generate times interval
                for time in range(protocol_service['times']):

                    window_start, window_end = clamp(day - tolerance, day + tolerance, 0, max_day_number)
                    
                    if window_start is not None and window_end is not None:
                        windows.add((patient_name, service_name, window_start, window_end))
                    
                    day += frequency

    # this set contains all (patient, service, day) tuples for
    # each possible protocol assignment. Those will be the indexes of actual
    # decision variables in the problem definition.
    schedulable_tuples = set()

    # for each window...
    for patient_name, service_name, window_start, window_end in windows:

        # for each day in the window interval...
        for day in range(window_start, window_end + 1):

            # ...add a possible schedulable tuple
            schedulable_tuples.add((patient_name, service_name, day))

    model.window_index = pyo.Set(initialize=sorted(windows))
    model.do_index = pyo.Set(initialize=sorted(schedulable_tuples))
    del windows, schedulable_tuples

    # set of all windows of the same patient and service that intersect eachother.
    # (patient, service1, service2, start1, end1, start2, end2)
    window_overlaps = set()

    for patient_name_1, service_name_1, window_start_1, window_end_1 in model.window_index:
        for patient_name_2, service_name_2, window_start_2, window_end_2 in model.window_index:

            # valid only windows of the same patient and service
            if patient_name_1 != patient_name_2 or service_name_1 != service_name_2:
                continue

            # not the same window of course
            if window_start_1 == window_start_2 and window_end_1 == window_end_2:
                continue

            # symmetry check
            if window_start_1 > window_start_2:
                continue

            if ((window_end_1 >= window_start_2 and window_end_1 <= window_end_2) or
                (window_end_2 >= window_start_1 and window_end_2 <= window_end_1)):
                window_overlaps.add((patient_name_1, service_name_1, window_start_1, window_end_1, window_start_2, window_end_2))

    model.window_overlap_index = pyo.Set(initialize=sorted(window_overlaps))
    del window_overlaps

    ############################# VARIABLES DEFINITION #############################

    # decision variables that describe if a request window is satisfied.
    # Its index is (patient, service, window_start, window_end)
    model.window = pyo.Var(model.window_index, domain=pyo.Binary)

    # decision variables that describe what request is satisfied in which day
    # Its index is (patient, service, day)
    model.do = pyo.Var(model.do_index, domain=pyo.Binary)

    # variables that are equal to zero if two requests that overlap in their
    # intervals are satisfied efficiently only one time.
    model.window_overlap = pyo.Var(model.window_overlap_index, domain=pyo.Binary)

    ############################ CONSTRAINTS DEFINITION ############################

    # if a 'window' variable is 1 then exactly one 'do' variables inside its days
    # window must be equal to 1 (if a window is satisfied then it's satisfied by
    # only one day; if a window is not satisfied then all its daily occurrences are
    # equal to 0).
    @model.Constraint(model.window_index)
    def link_window_to_do_variables(model, p, s, ws, we):
        return pyo.quicksum([model.do[pp, ss, d] for pp, ss, d in model.do_index if p == pp and s == ss and d >= ws and d <= we]) == model.window[p, s, ws, we]

    # The total duration of services assigned to one care unit must
    # not be greater than its total capacity.
    @model.Constraint(model.care_units)
    def respect_care_unit_capacity(model, d, c):
        tuples_affected = [(p, s) for p, s, dd in model.do_index if d == dd and c == model.service_care_unit[s]]
        if len(tuples_affected) == 0:
            return pyo.Constraint.Feasible
        return pyo.quicksum(model.do[p, s, d] * model.service_duration[s] for p, s in tuples_affected) <= model.capacity[d, c]

    # constraint that links service satisfacion with 'window_overlap' variables.
    # if services of overlapping windows are satisfied not efficiently, the variable
    # value in the right side of the disequation is forced to 1.
    @model.Constraint(model.window_overlap_index)
    def window_overlap_constraint(model, p, s, ws, we, wws, wwe):
        min_ws = min(ws, wws)
        max_we = max(we, wwe)
        tuples_affected = [(p, s, d) for d in range(min_ws, max_we + 1) for pp, ss, dd in model.do_index if p == pp and s == ss and d == dd]
        return pyo.quicksum(model.do[p, s, d] for p, s, d in tuples_affected) <= 1 + model.window_overlap[p, s, ws, we, wws, wwe]

    if 'add_optimization' in additional_info:
        add_optimization_to_master_model(model, instance)

    ############################## OBJECTIVE FUNCTION ##############################

    # the solution value depends linearly by the total service duration of the
    # satisfied request, scaled by the requesting patient priority.
    # A more important second objective is added with a big constant that makes
    # the solver prefer solutions that group toghether same-service windows of
    # the same patient if they overlap.

    model.function_value_component = pyo.Var(model.days, domain=pyo.NonNegativeIntegers)

    if use_priorities:
        @model.Constraint(model.days)
        def compose_function_value(model, d):
            return model.function_value_component[d] == pyo.quicksum(model.do[p, s, dd] * model.service_duration[s] * model.patient_priority[p] for p, s, dd in model.do_index if d == dd)
        
    else:
        @model.Constraint(model.days)
        def compose_function_value(model, d):
            return model.function_value_component[d] == pyo.quicksum(model.do[p, s, dd] * model.service_duration[s] for p, s, dd in model.do_index if d == dd)
    
    return model


def add_bin_packing_cuts_to_master_model(model):

    @model.Objective(sense=pyo.maximize)
    def total_satisfied_service_durations(model):
        return pyo.quicksum(model.function_value_component[d] for d in model.days) - 1e6 * pyo.quicksum(model.window_overlap[p, s, ws, we, wws, wwe] for p, s, ws, we, wws, wwe in model.window_overlap_index)
    
    @model.Constraint(model.care_units)
    def case_two(model, d, c):
        day_name = str(d)
        operator_number = len(instance['days'][day_name][c])
        operator_duration = instance['days'][day_name][c]['op00']['duration']
        tuple_list = [(p, s) for p, s, dd in model.do_index if d == dd and model.service_care_unit[s] == c and model.service_duration[s] >= (operator_duration * 0.5 + 1)]
        if len(tuple_list) == 0:
            return pyo.Constraint.Skip
        return pyo.quicksum([model.do[p, s, d] for p, s in tuple_list]) <= operator_number

    @model.Constraint(model.care_units)
    def case_three(model, d, c):
        day_name = str(d)
        operator_number = len(instance['days'][day_name][c])
        operator_duration = instance['days'][day_name][c]['op00']['duration']
        tuple_list = [(p, s) for p, s, dd in model.do_index if d == dd and model.service_care_unit[s] == c and model.service_duration[s] == int(operator_duration * 0.5)]
        greater_tuple_list = [(p, s) for p, s, dd in model.do_index if d == dd and model.service_care_unit[s] == c and model.service_duration[s] >= int(operator_duration * 0.5 + 1)]
        if len(tuple_list) == 0 or len(greater_tuple_list) == 0:
            return pyo.Constraint.Skip
        return pyo.quicksum([model.do[p, s, d] for p, s in tuple_list]) <= operator_number * 2.0 - 2.0 * pyo.quicksum([model.do[p, s, d] for p, s in greater_tuple_list])
    
    @model.Constraint(model.care_units)
    def case_four_a(model, d, c):
        day_name = str(d)
        operator_number = len(instance['days'][day_name][c])
        operator_duration = instance['days'][day_name][c]['op00']['duration']
        tuple_list = [(p, s) for p, s, dd in model.do_index if d == dd and model.service_care_unit[s] == c and model.service_duration[s] == int(operator_duration * 0.5 - 1)]
        greater_tuple_list = [(p, s) for p, s, dd in model.do_index if d == dd and model.service_care_unit[s] == c and model.service_duration[s] == int(operator_duration * 0.5 + 1)]
        if len(tuple_list) == 0 or len(greater_tuple_list) == 0:
            return pyo.Constraint.Skip
        return pyo.quicksum([model.do[p, s, d] for p, s in tuple_list]) <= operator_number * 2.0 - pyo.quicksum([model.do[p, s, d] for p, s in greater_tuple_list])
    
    @model.Constraint(model.care_units)
    def case_four_b(model, d, c):
        day_name = str(d)
        operator_number = len(instance['days'][day_name][c])
        operator_duration = instance['days'][day_name][c]['op00']['duration']
        tuple_list = [(p, s) for p, s, dd in model.do_index if d == dd and model.service_care_unit[s] == c and model.service_duration[s] == int(operator_duration * 0.5 - 1)]
        greater_tuple_list = [(p, s) for p, s, dd in model.do_index if d == dd and model.service_care_unit[s] == c and model.service_duration[s] == int(operator_duration * 0.5 + 2)]
        if len(tuple_list) == 0 or len(greater_tuple_list) == 0:
            return pyo.Constraint.Skip
        return pyo.quicksum([model.do[p, s, d] for p, s in tuple_list]) <= operator_number * 2.0 - 2.0 * pyo.quicksum([model.do[p, s, d] for p, s in greater_tuple_list])
    
    @model.Constraint(model.care_units)
    def case_five_a(model, d, c):
        day_name = str(d)
        operator_number = len(instance['days'][day_name][c])
        operator_duration = instance['days'][day_name][c]['op00']['duration']
        tuple_list = [(p, s) for p, s, dd in model.do_index if d == dd and model.service_care_unit[s] == c and model.service_duration[s] == int(operator_duration * 0.25)]
        greater_tuple_list = [(p, s) for p, s, dd in model.do_index if d == dd and model.service_care_unit[s] == c and model.service_duration[s] >= int(operator_duration * 0.5 + 1)]
        if len(tuple_list) == 0 or len(greater_tuple_list) == 0:
            return pyo.Constraint.Skip
        return pyo.quicksum([model.do[p, s, d] for p, s in tuple_list]) <= operator_number * 4.0 - 3.0 * pyo.quicksum([model.do[p, s, d] for p, s in greater_tuple_list])
    
    @model.Constraint(model.care_units)
    def case_five_b(model, d, c):
        day_name = str(d)
        operator_number = len(instance['days'][day_name][c])
        operator_duration = instance['days'][day_name][c]['op00']['duration']
        tuple_list = [(p, s) for p, s, dd in model.do_index if d == dd and model.service_care_unit[s] == c and model.service_duration[s] == int(operator_duration * 0.25)]
        greater_tuple_list = [(p, s) for p, s, dd in model.do_index if d == dd and model.service_care_unit[s] == c and model.service_duration[s] == int(operator_duration * 0.5)]
        if len(tuple_list) == 0:
            return pyo.Constraint.Skip
        return pyo.quicksum([model.do[p, s, d] for p, s in tuple_list]) <= operator_number * 4.0 - 2.0 * pyo.quicksum([model.do[p, s, d] for p, s in greater_tuple_list])


def add_optimization_to_master_model(model, instance):

    for day in instance['days'].values():
        for care_unit in day.values():
            start_time = None
            for operator in care_unit.values():
                if start_time is None:
                    start_time = operator['start']
                elif start_time != operator['start']:
                    return

    # optimization_index are on the form (patient, day)
    optimization_index = set()
    for patient_name, _, day_name in model.do_index:
        optimization_index.add((patient_name, int(day_name)))
    model.optimization_index = pyo.Set(initialize=sorted(optimization_index))
    
    # max_duration[d, c] is the maximum operator duration
    @model.Param(model.days, domain=pyo.NonNegativeIntegers, mutable=False)
    def max_duration(model, d):
        return max([o['duration'] for c in instance['days'][str(d)].keys() for o in instance['days'][str(d)][c].values()])

    # it is impossible for a single patient to do services of a specific care unit
    # with a total duration greater than the longest operator duration of that care unit.
    # This constraint is only valid if every care unit has all its operators that start at the same time.
    @model.Constraint(model.optimization_index)
    def redundant_patient_total_duration(model, p, d):
        return pyo.quicksum([model.do[pp, s, dd] * model.service_duration[s] for pp, s, dd in model.do_index if pp == p and dd == d]) <= model.max_duration[d]


def get_results_from_master_model(model, config):

    scheduled_requests_grouped_per_day = {}
    for p, s, d in model.do_index:
        if pyo.value(model.do[p, s, d]) < 0.01:
            continue
        day_name = str(d)
        if day_name not in scheduled_requests_grouped_per_day:
            scheduled_requests_grouped_per_day[day_name] = []
        scheduled_requests_grouped_per_day[day_name].append({
            'patient': p,
            'service': s
        })

    rejected_requests = []
    for p, s, ws, we in model.window_index:
        if pyo.value(model.window[p, s, ws, we]) < 0.01:
            rejected_requests.append({
                'patient': p,
                'service': s,
                'window': [ws, we]
            })

    scheduled_requests_grouped_per_day = dict(sorted([(k, v) for k, v in scheduled_requests_grouped_per_day.items()], key=lambda vv: int(vv[0])))
    for daily_results in scheduled_requests_grouped_per_day.values():
        daily_results.sort(key=lambda v: (v['patient'], v['service']))
    rejected_requests.sort(key=lambda v: (v['patient'], v['service']))

    return {
        'scheduled': scheduled_requests_grouped_per_day,
        'rejected': rejected_requests
    }