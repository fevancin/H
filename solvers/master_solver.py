import pyomo.environ as pyo

from solvers.tools import clamp


def get_master_model(instance, additional_info):

    max_day_number = max([int(d) for d in instance['days'].keys()])

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

    @model.Param(model.patients, domain=pyo.PositiveIntegers, mutable=False)
    def patient_priority(model, p):
        return instance['patients'][p]['priority']
    
    # max_duration[d, c] is the maximum operator end time
    @model.Param(model.days, domain=pyo.NonNegativeIntegers, mutable=False)
    def max_duration(model, d):
        return max([o['start'] + o['duration'] for c in instance['days'][str(d)].keys() for o in instance['days'][str(d)][c].values()])

    # this variable stores a set of quadruples (patient, service, start, end) for
    # each interval requested by some protocol
    window_index = set()
    for patient_name, patient in instance['patients'].items():
        for service_name, windows in patient['requests'].items():
            for window in windows:
                window_index.add((patient_name, service_name, window[0], window[1]))

    # this set contains all (patient, service, day) tuples for
    # each possible protocol assignment. Those will be the indexes of actual
    # decision variables in the problem definition.
    schedulable_tuples = set()
    for patient_name, service_name, window_start, window_end in window_index:

        # for each day in the window interval...
        for day in range(window_start, window_end + 1):

            # ...add a possible schedulable tuple
            schedulable_tuples.add((patient_name, service_name, day))

    model.window_index = pyo.Set(initialize=sorted(window_index))
    model.do_index = pyo.Set(initialize=sorted(schedulable_tuples))
    del window_index, schedulable_tuples

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

    # pat_day_indexes are on the form (patient, day)
    pat_days_index = set()
    for patient_name, _, day_name in model.do_index:
        pat_days_index.add((patient_name, int(day_name)))
    model.pat_days_index = pyo.Set(initialize=sorted(pat_days_index))

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
            return pyo.Constraint.Skip
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

    # it is impossible for a single patient to do services of a specific care unit
    # with a total duration greater than the longest operator duration of that care unit.
    # This constraint is stronger if every care unit has all its operators that start and end at the same time.
    @model.Constraint(model.pat_days_index)
    def patient_total_duration(model, p, d):
        return pyo.quicksum([model.do[pp, s, dd] * model.service_duration[s] for pp, s, dd in model.do_index if pp == p and dd == d]) <= model.max_duration[d]


    if 'minimize_hospital_accesses' in additional_info:

        model.pat_use_day = pyo.Var(model.pat_days_index, domain=pyo.Binary)

        @model.Constraint(model.do_index)
        def if_patient_use_day(model, p, s, d):
            return model.do[p, s, d] <= model.pat_use_day[p, d]

    if 'use_bin_packing' in additional_info:
        add_bin_packing_cuts_to_master_model(model, instance)

    if 'use_objective_value_constraints' in additional_info:
        model.objective_value_constraints = pyo.ConstraintList()

    ############################## OBJECTIVE FUNCTION ##############################

    # the solution value depends linearly by the total service duration of the
    # satisfied request, scaled by the requesting patient priority.
    # A more important second objective is added with a big constant that makes
    # the solver prefer solutions that group toghether same-service windows of
    # the same patient if they overlap. It's possible to specify a third objective
    # consisting in the minimization of days unsed by the same patient.

    model.function_value_component = pyo.Var(model.days, domain=pyo.NonNegativeIntegers)

    @model.Constraint(model.days)
    def compose_function_value(model, d):
        return model.function_value_component[d] == pyo.quicksum(model.do[p, s, dd] * model.service_duration[s] * model.patient_priority[p] for p, s, dd in model.do_index if d == dd)
    
    if 'minimize_hospital_accesses' in additional_info:
        @model.Objective(sense=pyo.maximize)
        def total_satisfied_service_durations(model):
            return pyo.quicksum(model.function_value_component[d] for d in model.days) - 1e6 * pyo.quicksum(model.window_overlap[p, s, ws, we, wws, wwe] for p, s, ws, we, wws, wwe in model.window_overlap_index) - 1 / len(model.pat_days_index) * pyo.quicksum(model.pat_use_day[p, d] for p, d in model.pat_days_index)
    else:
        @model.Objective(sense=pyo.maximize)
        def total_satisfied_service_durations(model):
            return pyo.quicksum(model.function_value_component[d] for d in model.days) - 1e6 * pyo.quicksum(model.window_overlap[p, s, ws, we, wws, wwe] for p, s, ws, we, wws, wwe in model.window_overlap_index)
    
    return model


def add_bin_packing_cuts_to_master_model(model, instance):

    # il numero di servizi lunghi più della metà dello shift non può essere
    # maggiore al numero di operatori
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


def add_objective_value_constraints(model, instance, all_subproblem_results, max_possible_master_requests):

    # Per ogni giorno salva il valore della funzione obiettivo del sottoproblema
    solution_values = {}
    for day_name, day_results in all_subproblem_results.items():
        solution_value = 0
        for scheduled_request in day_results['scheduled']:
            patient_name = scheduled_request['patient']
            service_name = scheduled_request['service']
            solution_value += instance['services'][service_name]['duration'] * instance['patients'][patient_name]['priority']
        solution_values[day_name] = solution_value

    # Aggiungi il vincolo per cui z_d >= z_d* - M*sum(1 - x per ogni x=1) in cui:
    # > z è la funzione obiettivo del giorno corrispondente al sottoproblema
    # > z* è il valore della funzione obiettivo restituita dal sottoproblema
    # > M è una costante grande
    # > x sono le variabili di schedulazione poste ad 1 dal sottoproblema.
    # Questo vincolo è relativo ad un certo giorno d.

    # Se il MP chiede almeno quello che aveva chiesto al SP il valore della
    # funzione obiettivo sarà almeno z_d*.
    for day_name, day_results in all_subproblem_results.items():
        day_index = int(day_name)
        
        tuple_list = []
        for scheduled_request in day_results['scheduled']:
            patient_name = scheduled_request['patient']
            service_name = scheduled_request['service']
            tuple_list.append((patient_name, service_name, day_index))

        model.objective_value_constraints.add(expr=(model.function_value_component[day_index] >= solution_values[day_name] - solution_values[day_name] * 100 * pyo.quicksum([(1 - model.do[p, s, d]) for p, s, d in tuple_list])))

    # Aggiungi il vincolo per cui z_d <= z_d* + M*sum(x per ogni x=0) in cui:
    # > z è la funzione obiettivo del giorno corrispondente al sottoproblema
    # > z* è il valore della funzione obiettivo restituita dal sottoproblema
    # > M è una costante grande
    # > x sono le variabili di schedulazione non richieste al sottoproblema.
    # Questo vincolo è relativo ad un certo giorno d.

    # Se il MP chiede di nuovo qualcosa in cui continua a non esserci almeno ciò
    # che non aveva chiesto prima, la funzione obiettivo non potrà essere migliore.
    for day_name, day_results in all_subproblem_results.items():
        day_index = int(day_name)
            
        tuple_list = []
        for possible_request in max_possible_master_requests[day_name]:
        
            patient_name = possible_request['patient']
            service_name = possible_request['service']
        
            was_proposed_to_subproblem = False
            for rejected_request in day_results['rejected']:
                if rejected_request['patient'] == patient_name and rejected_request['service'] == service_name:
                    was_proposed_to_subproblem = True
                    break
            if not was_proposed_to_subproblem:
                for scheduled_request in day_results['scheduled']:
                    if scheduled_request['patient'] == patient_name and scheduled_request['service'] == service_name:
                        was_proposed_to_subproblem = True
                        break
            
            if not was_proposed_to_subproblem:
                tuple_list.append((patient_name, service_name, day_index))

        model.objective_value_constraints.add(expr=(model.function_value_component[day_index] <= solution_values[day_name] + solution_values[day_name] * 100 * pyo.quicksum([model.do[p, s, d] for p, s, d in tuple_list])))


def get_results_from_master_model(model):

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