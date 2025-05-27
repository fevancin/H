import pyomo.environ as pyo

from tools import clamp


def get_monolithic_model(instance, additional_info):

    max_day_number = max([int(d) for d in instance['days'].keys()])

    if 'use_inefficient_operators' in additional_info:
        use_inefficient_operators = True
    else:
        start = None
        duration = None
        are_all_operators_equal = True
        for day in instance['days'].values():
            for care_unit in day.values():
                for operator in care_unit.values():
                    if start is None:
                        start = operator['start']
                        duration = operator['duration']
                    if operator['start'] != start or operator['duration'] != duration:
                        are_all_operators_equal = False
                        break
                if not are_all_operators_equal:
                    break
            if not are_all_operators_equal:
                break
        use_inefficient_operators = not are_all_operators_equal
    
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
    model.operators = pyo.Set(initialize=sorted([(int(d), c, o)
                                        for d, day in instance['days'].items()
                                        for c, cu in day.items()
                                        for o in cu.keys()]))

    ############################### MODEL PARAMETERS ###############################

    @model.Param(model.services, domain=pyo.Any, mutable=False)
    def service_care_unit(model, s):
        return instance['services'][s]['care_unit']

    @model.Param(model.services, domain=pyo.PositiveIntegers, mutable=False)
    def service_duration(model, s):
        return instance['services'][s]['duration']

    @model.Param(model.operators, domain=pyo.NonNegativeIntegers, mutable=False)
    def operator_start(model, d, c, o):
        return instance['days'][str(d)][c][o]['start'] + 1

    @model.Param(model.operators, domain=pyo.PositiveIntegers, mutable=False)
    def operator_duration(model, d, c, o):
        return instance['days'][str(d)][c][o]['duration']

    # max_time[d, c] is the maximum end time between each operator
    @model.Param(model.care_units, domain=pyo.NonNegativeIntegers, mutable=False)
    def max_time(model, d, c):
        return max([o['start'] + o['duration'] for o in instance['days'][str(d)][c].values()]) + 1

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

    # this set contains all (patient, service, day, care_unit, operator) tuples for
    # each possible protocol assignment. Those will be the indexes of actual
    # decision variables in the problem definition.
    schedulable_tuples_with_operators = set()

    if use_inefficient_operators:
        schedulable_tuples_with_operators_and_windows = set()

    # for each window...
    for patient_name, service_name, window_start, window_end in windows:

        care_unit_name = instance['services'][service_name]['care_unit']

        # for each day in the window interval...
        for day in range(window_start, window_end + 1):

            # for each operator active that day (of the correct care unit)...
            for operator_name in instance['days'][str(day)][care_unit_name].keys():

                # ...add a possible schedulable tuple
                schedulable_tuples_with_operators.add((patient_name, service_name, day, care_unit_name, operator_name))

                if use_inefficient_operators:
                    schedulable_tuples_with_operators_and_windows.add((patient_name, service_name, day, care_unit_name, operator_name, window_start, window_end))

    # set of all (patient1, patient2, service1, service2, day, care_unit, operator1, operator2) found.
    # This tuples will indicize all overlap constraints between same patient and same operator.
    overlap_tuples = set()

    for patient_name_1, service_name_1, day_1, care_unit_name_1, operator_name_1 in schedulable_tuples_with_operators:
        for patient_name_2, service_name_2, day_2, care_unit_name_2, operator_name_2 in schedulable_tuples_with_operators:
            # day must be the same in order to have a meaningful overlap
            if day_1 != day_2:
                continue
            
            # at least one between patients and operators must be the same
            if patient_name_1 != patient_name_2 and (operator_name_1 != operator_name_2 or care_unit_name_1 != care_unit_name_2):
                continue

            # discarding indexes referred to the same request
            if patient_name_1 == patient_name_2 and service_name_1 == service_name_2:
                continue
            
            # simmetry check
            if service_name_1 > service_name_2 or (patient_name_1 > patient_name_2 and service_name_1 == service_name_2) or (operator_name_1 >= operator_name_2 and patient_name_1 == patient_name_2 and service_name_1 == service_name_2):
                continue

            overlap_tuples.add((patient_name_1, service_name_1, patient_name_2, service_name_2, day_1, care_unit_name_1, operator_name_1, care_unit_name_2, operator_name_2))

    model.window_index = pyo.Set(initialize=sorted(windows))
    model.do_index = pyo.Set(initialize=sorted(schedulable_tuples_with_operators))
    if use_inefficient_operators:
        model.duration_index = pyo.Set(initialize=sorted(schedulable_tuples_with_operators_and_windows))
        del schedulable_tuples_with_operators_and_windows
    model.overlap_index = pyo.Set(initialize=sorted(overlap_tuples))
    del windows, schedulable_tuples_with_operators, overlap_tuples

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

    def get_time_bounds(model, patient_name: str, service_name: str, ws: int, we: int) -> tuple[int, int]:
        """
        Returns a couple (min_time, max_time) where the bounds correspond to the
        time slot interval in which a service can be scheduled in order to be
        fully completed by any operator that day.
        If no operator are found active, (None, None) is returned.
        """

        service_care_unit = model.service_care_unit[service_name]
        service_duration = model.service_duration[service_name]

        min_operator_start = None
        max_operator_end = None

        for day in range(ws, we + 1):
            for operator in instance['days'][str(day)][service_care_unit].values():

                operator_start = operator['start'] + 1
                operator_duration = operator['duration']
                operator_end = operator_start + operator_duration
                
                if min_operator_start is None or operator_start < min_operator_start:
                    min_operator_start = operator_start
                if max_operator_end is None or operator_end > max_operator_end:
                    max_operator_end = operator_end
        
        return (min_operator_start - 1, max_operator_end - service_duration)

    ############################# VARIABLES DEFINITION #############################

    # decision variables that describe if a request window is satisfied.
    # Its index is (patient, service, window_start, window_end)
    model.window = pyo.Var(model.window_index, domain=pyo.Binary)

    # if a 'window' variable is equal to 1 then its corresponding
    # 'time' variable specify in which time slot the request is satisfied.
    # Its index is (patient, service, window_start, window_end)
    model.time = pyo.Var(model.window_index, domain=pyo.NonNegativeIntegers, bounds=get_time_bounds)

    # decision variables that describe what request is satisfied in which day and
    # by which operator.
    # Its index is (patient, service, day, care_unit, operator)
    model.do = pyo.Var(model.do_index, domain=pyo.Binary)

    # variables used for specifing what service is done first if the patient or
    # operator are the same.
    # Their index is:
    # (patient, service, patient, service, day, care_unit, operator, operator)
    model.overlap_aux_1 = pyo.Var(model.overlap_index, domain=pyo.Binary)
    model.overlap_aux_2 = pyo.Var(model.overlap_index, domain=pyo.Binary)

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
        return pyo.quicksum([model.do[pp, ss, d, c, o] for pp, ss, d, c, o in model.do_index if p == pp and s == ss and d >= ws and d <= we and c == model.service_care_unit[s]]) == model.window[p, s, ws, we]

    if not use_inefficient_operators:

        # constraint that describes the implications:
        # (t[p,s,ws,we] > 0) -> (w[p,s,ws,we] = 1)
        # (w[p,s,ws,we] = 0) -> (t[p,s,ws,we] = 0)
        @model.Constraint(model.window_index)
        def link_time_to_window_variables(model, p, s, ws, we):
            d = ws
            c = model.service_care_unit[s]
            return model.time[p, s, ws, we] <= model.window[p, s, ws, we] * (model.max_time[d, c] - model.service_duration[s])

        # constraint that describes the implications:
        # (t[p,s,ws,we] = 0) -> (w[p,s,ws,we] = 0)
        # (w[p,s,ws,we] = 1) -> (t[p,s,ws,we] > 0)
        @model.Constraint(model.window_index)
        def link_window_to_time_variables(model, p, s, ws, we):
            return model.window[p, s, ws, we] <= model.time[p, s, ws, we]

    # alternative operator time constraints, required only if operators are not all
    # equal in duration and start time. Alternative to the two constraint
    # classes above if used.
    else:
        @model.Constraint(model.duration_index)
        def link_time_to_window_variables(model, p, s, d, c, o, ws, we):
            return model.time[p, s, ws, we] <= model.operator_start[d, c, o] + model.operator_duration[d, c, o] - model.service_duration[s] + (1 - model.do[p, s, d, c, o]) * model.max_time[d, c]

        @model.Constraint(model.duration_index)
        def link_window_to_time_variables(model, p, s, d, c, o, ws, we):
            return model.do[p, s, d, c, o] * model.operator_start[d, c, o] <= model.time[p, s, ws, we]

    # merge 'overlap_index' with window bounds of all windows containing those
    # requests.
    # (p, s, pp, ss, d, c, o, oo, ws, we, wws, wwe)
    overlap_constraint_index = set()
    for p, s, pp, ss, d, c, o, cc, oo in model.overlap_index:
        for ppp, sss, ws, we in model.window_index:
            if p != ppp or s != sss or we < d or ws > d:
                continue
            for pppp, ssss, wws, wwe in model.window_index:
                if pp != pppp or ss != ssss or wwe < d or wws > d:
                    continue
                overlap_constraint_index.add((p, s, pp, ss, d, c, o, cc, oo, ws, we, wws, wwe))
    model.overlap_constraint_index = pyo.Set(initialize=sorted(overlap_constraint_index))

    # constraints that force disjunction of services scheduled to be done by the
    # same patient or operator. Only one of the following must be valid:
    # 
    # end_A <= start_B
    # end_B <= start_A
    # 
    # Two auxiliary variables are needed because those services could also be
    # done, but by different patients or operators.
    # Constraints need to be present for each couple of request window and for each
    # operator capable of satisfy them.
    # Constraint index is effectively (patient1, service1, patient2, service2, day, care_unit, operator1, operator2, window1, window2)
    @model.Constraint(model.overlap_constraint_index)
    def services_not_overlap_1(model, p, s, pp, ss, d, c, o, cc, oo, ws, we, wws, wwe):
        return model.time[p, s, ws, we] + model.service_duration[s] * model.do[p, s, d, c, o] <= model.time[pp, ss, wws, wwe] + (1 - model.overlap_aux_1[p, s, pp, ss, d, c, o, cc, oo]) * model.max_time[d, c]
    @model.Constraint(model.overlap_constraint_index)
    def services_not_overlap_2(model, p, s, pp, ss, d, c, o, cc, oo, ws, we, wws, wwe):
        return model.time[pp, ss, wws, wwe] + model.service_duration[ss] * model.do[pp, ss, d, cc, oo] <= model.time[p, s, ws, we] + (1 - model.overlap_aux_2[p, s, pp, ss, d, c, o, cc, oo]) * model.max_time[d, cc]

    # auxiliary contraints that force variables 'overlap_aux_1' and
    # 'overlap_aux_2' to fixed values.
    # They must sum to one only if both A and B are done.
    # If at least one service is not done then they are forced to zero.
    # o-----------------------------------------o
    # | A | B | overlap_aux_1 + overlap_aux_2   |
    # |---|---|---------------------------------|
    # | o | o | sum to one                      |
    # | o | x | zero                            |
    # | x | o | zero                            |
    # | x | x | zero                            |
    # o-----------------------------------------o
    @model.Constraint(model.overlap_index)
    def operator_overlap_auxiliary_constraint_1(model, p, s, pp, ss, d, c, o, cc, oo):
        return model.do[p, s, d, c, o] + model.do[pp, ss, d, cc, oo] - 1 <= model.overlap_aux_1[p, s, pp, ss, d, c, o, cc, oo] + model.overlap_aux_2[p, s, pp, ss, d, c, o, cc, oo]
    @model.Constraint(model.overlap_index)
    def operator_overlap_auxiliary_constraint_2(model, p, s, pp, ss, d, c, o, cc, oo):
        return model.do[p, s, d, c, o] >= model.overlap_aux_1[p, s, pp, ss, d, c, o, cc, oo] + model.overlap_aux_2[p, s, pp, ss, d, c, o, cc, oo]
    @model.Constraint(model.overlap_index)
    def operator_overlap_auxiliary_constraint_3(model, p, s, pp, ss, d, c, o, cc, oo):
        return model.do[pp, ss, d, cc, oo] >= model.overlap_aux_1[p, s, pp, ss, d, c, o, cc, oo] + model.overlap_aux_2[p, s, pp, ss, d, c, o, cc, oo]

    if 'use_redundant_patient_cut' in additional_info:

        model.patients_days = pyo.Set(initialize=sorted([(p, int(d)) for p, s, d, c, o in model.do_index]))

        # *optional* additional constraint. The total duration of services assigned to one patient must
        # not be greater than the maximum time slot assignable that day for operators of involved care units.
        # This constraint could be omitted without loss of correctedness but helps with a faster convergence.
        @model.Constraint(model.patients_days)
        def redundant_patient_cut(model, p, d):
            tuples_affected = [(s, c, o) for pp, s, dd, c, o in model.do_index if p == pp and d == dd]
            if len(tuples_affected) == 0:
                return pyo.Constraint.Feasible
            involved_care_unit_names = set(tuples_affected[i][1] for i in range(len(tuples_affected)))
            max_time_slot = max(model.max_time[d, c] for c in involved_care_unit_names)
            return pyo.quicksum(model.do[p, s, d, cc, o] * model.service_duration[s] for s, cc, o in tuples_affected) <= max_time_slot

    if 'use_redundant_operator_cut' in additional_info:
        
        # *optional* additional constraint. The total duration of services assigned to one operator must
        # not be greater than the operator duration. This constraint could be omitted
        # without loss of correctedness but helps with a faster convergence.
        @model.Constraint(model.operators)
        def redundant_operator_cut(model, d, c, o):
            tuples_affected = [(p, s) for p, s, dd, cc, oo in model.do_index if d == dd and cc == c and oo == o]
            if len(tuples_affected) == 0:
                return pyo.Constraint.Feasible
            return pyo.quicksum(model.do[p, s, d, c, o] * model.service_duration[s] for p, s in tuples_affected) <= model.operator_duration[d, c, o]

    # constraint that links service satisfacion with 'window_overlap' variables.
    # if services of overlapping windows are satisfied not efficiently, the variable
    # value in the right side of the disequation is forced to 1.
    @model.Constraint(model.window_overlap_index)
    def window_overlap_constraint(model, p, s, ws, we, wws, wwe):
        min_ws = min(ws, wws)
        max_we = max(we, wwe)
        tuples_affected = [(p, s, d, c, o) for d in range(min_ws, max_we + 1) for pp, ss, dd, c, o in model.do_index if p == pp and s == ss and d == dd]
        return pyo.quicksum(model.do[p, s, d, c, o] for p, s, d, c, o in tuples_affected) <= 1 + model.window_overlap[p, s, ws, we, wws, wwe]

    ############################## OBJECTIVE FUNCTION ##############################

    # the solution value depends linearly by the total service duration of the
    # satisfied request, scaled by the requesting patient priority.
    # A more important second objective is added with a big constant that makes
    # the solver prefer solutions that group toghether same-service windows of
    # the same patient if they overlap.
    if use_priorities:
        @model.Objective(sense=pyo.maximize)
        def total_satisfied_service_durations(model):
            return pyo.quicksum(model.do[p, s, d, c, o] * model.service_duration[s] * model.patient_priority[p] for p, s, d, c, o in model.do_index) - 1e6 * pyo.quicksum(model.window_overlap[p, s, ws, we, wws, wwe] for p, s, ws, we, wws, wwe in model.window_overlap_index)
    else:
        @model.Objective(sense=pyo.maximize)
        def total_satisfied_service_durations(model):
            return pyo.quicksum(model.do[p, s, d, c, o] * model.service_duration[s] for p, s, d, c, o in model.do_index) - 1e6 * pyo.quicksum(model.window_overlap[p, s, ws, we, wws, wwe] for p, s, ws, we, wws, wwe in model.window_overlap_index)

    return model


def get_results_from_monolithic_model(model, additional_info):

    scheduled_requests_grouped_per_day = {}
    for p, s, d, c, o in model.do_index:
        if pyo.value(model.do[p, s, d, c, o]) < 0.01:
            continue
        window = None
        for pp, ss, ws, we in model.window_index:
            if p != pp or s != ss or int(d) < ws or int(d) > we:
                continue
            if pyo.value(model.window[p, s, ws, we]) > 0.99:
                window = (ws, we)
                break
        day_name = str(d)
        time_slot = int(pyo.value(model.time[p, s, window[0], window[1]]) - 1)
        if day_name not in scheduled_requests_grouped_per_day:
            scheduled_requests_grouped_per_day[day_name] = []
        scheduled_requests_grouped_per_day[day_name].append({
            'patient': p,
            'service': s,
            'care_unit': c,
            'operator': o,
            'time': time_slot
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
        daily_results.sort(key=lambda v: (v['patient'], v['service'], v['care_unit'], v['operator'], v['time']))
    rejected_requests.sort(key=lambda v: (v['patient'], v['service']))

    return {
        'scheduled': scheduled_requests_grouped_per_day,
        'rejected': rejected_requests
    }