import pyomo.environ as pyo


def get_subproblem_model(instance, additional_info):
    
    model = pyo.ConcreteModel()

    ############################ MODEL SETS AND INDEXES ############################

    # all service names
    model.services = pyo.Set(initialize=sorted(instance['services'].keys()))

    # all care_units
    model.care_units = pyo.Set(initialize=sorted([c for c in instance['day'].keys()]))

    # all patient names
    model.patients = pyo.Set(initialize=sorted(instance['patients'].keys()))

    # couples (care_unit, operator) for each operator available
    model.operators = pyo.Set(initialize=sorted([(c, o)
                                        for c, cu in instance['day'].items()
                                        for o in cu.keys()]))

    ############################### MODEL PARAMETERS ###############################

    @model.Param(model.services, domain=pyo.Any, mutable=False)
    def service_care_unit(model, s):
        return instance['services'][s]['care_unit']

    @model.Param(model.services, domain=pyo.PositiveIntegers, mutable=False)
    def service_duration(model, s):
        return instance['services'][s]['duration']

    @model.Param(model.operators, domain=pyo.NonNegativeIntegers, mutable=False)
    def operator_start(model, c, o):
        return instance['day'][c][o]['start'] + 1

    @model.Param(model.operators, domain=pyo.PositiveIntegers, mutable=False)
    def operator_duration(model, c, o):
        return instance['day'][c][o]['duration']

    # max_time[c] is the maximum end time between each operator
    @model.Param(model.care_units, domain=pyo.NonNegativeIntegers, mutable=False)
    def max_time(model, c):
        return max([o['start'] + o['duration'] for o in instance['day'][c].values()]) + 1

    @model.Param(model.patients, domain=pyo.PositiveIntegers, mutable=False)
    def patient_priority(model, p):
        return instance['patients'][p]['priority']

    # tuples (patient, service) that specify what request is satisfied
    schedulable_tuples = set()

    # this set contains all (patient, service, care_unit, operator) tuples for
    # each possible request assignment. Those will be the indexes of actual
    # decision variables in the problem definition.
    schedulable_tuples_with_operators = set()

    for p, patient in instance['patients'].items():
        for s in patient['requests']:

            schedulable_tuples.add((p, s))

            duration = model.service_duration[s]
            c = model.service_care_unit[s]

            for o, operator in instance['day'][c].items():

                if operator['duration'] < duration:
                    continue

                schedulable_tuples_with_operators.add((p, s, c, o))

    # set of all (patient, service, service) found.
    # This tuples will indicize all overlap constraints between same patient.
    patient_overlap_tuples = set()

    for p, s in schedulable_tuples:
        for pp, ss in schedulable_tuples:
            
            if p != pp:
                continue

            # discarding indexes referred to the same request
            if s == ss:
                continue
            
            # simmetry check
            if s > ss:
                continue

            patient_overlap_tuples.add((p, s, ss))

    # operator_overlap_index is (patient, service, patient, service, operator, care_unit, i)
    # 'i' is 0 or 1
    operator_overlap_tuples = []

    for p, s, c, o in schedulable_tuples_with_operators:
        for pp, ss, cc, oo in schedulable_tuples_with_operators:
            
            if c != cc or o != oo:
                continue
            
            # simmetry check
            if p >= pp or (p == pp and s >= ss):
                continue
            
            operator_overlap_tuples.append((p, s, pp, ss, c, o))

    model.satisfy_index = pyo.Set(initialize=sorted(schedulable_tuples))
    model.do_index = pyo.Set(initialize=sorted(schedulable_tuples_with_operators))
    model.patient_overlap_index = pyo.Set(initialize=sorted(patient_overlap_tuples))
    model.operator_overlap_index = pyo.Set(initialize=sorted(operator_overlap_tuples))
    del schedulable_tuples, schedulable_tuples_with_operators, patient_overlap_tuples, operator_overlap_tuples

    def get_time_bounds(model, patient_name: str, service_name: str) -> tuple[int, int]:
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

        for operator in instance['day'][service_care_unit].values():

            operator_start = operator['start'] + 1
            operator_duration = operator['duration']
            operator_end = operator_start + operator_duration
            
            if min_operator_start is None or operator_start < min_operator_start:
                min_operator_start = operator_start
            if max_operator_end is None or operator_end > max_operator_end:
                max_operator_end = operator_end
        
        return (min_operator_start - 1, max_operator_end - service_duration)

    ############################# VARIABLES DEFINITION #############################

    # decision variables that describe if a request is satisfied.
    # Its index is (patient, service)
    model.satisfy = pyo.Var(model.satisfy_index, domain=pyo.Binary)

    # if a 'satisfy' variable is equal to 1 then its corresponding
    # 'time' variable specify in which time slot the request is satisfied.
    # Its index is (patient, service)
    model.time = pyo.Var(model.satisfy_index, domain=pyo.NonNegativeIntegers, bounds=get_time_bounds)

    # decision variables that describe what request is satisfied by which operator.
    # Its index is (patient, service, care_unit, operator)
    model.do = pyo.Var(model.do_index, domain=pyo.Binary)

    # variables used for specifing what service is done first if the patient is the same.
    # Their index is: (patient, service, service)
    model.patient_overlap = pyo.Var(model.patient_overlap_index, domain=pyo.Binary)

    # variables used for specifing what service is done first if the operator is the same.
    # Their index is: (patient, service, patient, service, care_unit, operator)
    model.operator_overlap_1 = pyo.Var(model.operator_overlap_index, domain=pyo.Boolean)
    model.operator_overlap_2 = pyo.Var(model.operator_overlap_index, domain=pyo.Boolean)

    ############################ CONSTRAINTS DEFINITION ############################

    # if a 'satisfy' variable is 1 then exactly one 'do' variables inside its
    # operators must be equal to 1 (if a request is satisfied then it's satisfied by
    # only one operator; if a request is not satisfied then all its operator variables are
    # equal to 0).
    @model.Constraint(model.satisfy_index)
    def link_satisfy_to_do_variables(model, p, s):
        return pyo.quicksum([model.do[pp, ss, c, o] for pp, ss, c, o in model.do_index if p == pp and s == ss and c == model.service_care_unit[s]]) == model.satisfy[p, s]

    # constraint that describes the implications:
    # (t[p,s,ws,we] > 0) -> (s[p,s,ws,we] = 1)
    # (s[p,s,ws,we] = 0) -> (t[p,s,ws,we] = 0)
    @model.Constraint(model.satisfy_index)
    def link_time_to_satisfy_variables(model, p, s):
        c = model.service_care_unit[s]
        return model.time[p, s] <= model.satisfy[p, s] * (model.max_time[c] - model.service_duration[s])

    # constraint that describes the implications:
    # (t[p,s,ws,we] = 0) -> (s[p,s,ws,we] = 0)
    # (s[p,s,ws,we] = 1) -> (t[p,s,ws,we] > 0)
    @model.Constraint(model.satisfy_index)
    def link_satisfy_to_time_variables(model, p, s):
        return model.satisfy[p, s] <= model.time[p, s]

    # operator start and end times must be respected
    @model.Constraint(model.do_index)
    def respect_operator_start(model, p, s, c, o):
        return model.operator_start[c, o] * model.do[p, s, c, o] <= model.time[p, s]
    @model.Constraint(model.do_index)
    def respect_operator_end(model, p, s, c, o):
        end = model.operator_start[c, o] + model.operator_duration[c, o]
        return model.time[p, s] + model.service_duration[s] <= end + (1 - model.do[p, s, c, o]) * model.max_time[c]

    # constraints that force disjunction of services scheduled to be done by the
    # same patient. Only one of the following must be valid:
    # 
    # end_A <= start_B
    # end_B <= start_A
    # 
    # One auxiliary variable is needed.
    # Constraints need to be present for each couple of requests.
    # Constraint index is effectively (patient1, service1, service2)
    @model.Constraint(model.patient_overlap_index)
    def patient_not_overlap_1(model, p, s, ss):
        return model.time[p, s] + model.service_duration[s] * model.satisfy[p, s] <= model.time[p, ss] + (1 - model.patient_overlap[p, s, ss]) * model.max_time[model.service_care_unit[s]]
    @model.Constraint(model.patient_overlap_index)
    def patient_not_overlap_2(model, p, s, ss):
        return model.time[p, ss] + model.service_duration[ss] * model.satisfy[p, ss] <= model.time[p, s] + (model.patient_overlap[p, s, ss]) * model.max_time[model.service_care_unit[ss]]

    # auxiliary contraints that force variables 'patient_overlap' to fixed values.
    # o-----------------------------------------o
    # | A | B | patient_overlap                 |
    # |---|---|---------------------------------|
    # | o | o | zero or one                     |
    # | o | x | zero                            |
    # | x | o | one                             |
    # | x | x | zero                            |
    # o-----------------------------------------o
    @model.Constraint(model.patient_overlap_index)
    def patient_overlap_auxiliary_constraint_1(model, p, s, ss):
        return model.patient_overlap[p, s, ss] <= model.satisfy[p, ss]
    @model.Constraint(model.patient_overlap_index)
    def patient_overlap_auxiliary_constraint_2(model, p, s, ss):
        return model.satisfy[p, ss] - model.satisfy[p, s] <= model.patient_overlap[p, s, ss]

    # constraints that force disjunction of services scheduled to be done by the
    # same operator. Only one of the following must be valid:
    # 
    # end_A <= start_B
    # end_B <= start_A
    # 
    # Two auxiliary variables are needed.
    # Constraints need to be present for each couple of requests.
    # Constraint index is effectively (patient1, service1, patient2, service2, care_unit, operator, n)
    # 'n' is 0 or 1
    @model.Constraint(model.operator_overlap_index)
    def operator_not_overlap_1(model, p, s, pp, ss, c, o):
        return model.time[p, s] + model.service_duration[s] * model.do[p, s, c, o] <= model.time[pp, ss] + (1 - model.operator_overlap_1[p, s, pp, ss, c, o]) * model.max_time[c]
    @model.Constraint(model.operator_overlap_index)
    def operator_not_overlap_2(model, p, s, pp, ss, c, o):
        return model.time[pp, ss] + model.service_duration[ss] * model.do[pp, ss, c, o] <= model.time[p, s] + (1 - model.operator_overlap_2[p, s, pp, ss, c, o]) * model.max_time[c]

    # auxiliary contraints that force variables 'operator_overlap' to fixed values.
    # o-------------------------------------------------o
    # | A | B | operator_overlap_0 + operator_overlap_1 |
    # |---|---|-----------------------------------------|
    # | o | o | one                                     |
    # | o | x | zero                                    |
    # | x | o | zero                                    |
    # | x | x | zero                                    |
    # o-------------------------------------------------o
    @model.Constraint(model.operator_overlap_index)
    def operator_overlap_auxiliary_constraint_1(model, p, s, pp, ss, c, o):
        return model.do[p, s, c, o] + model.do[pp, ss, c, o] - 1 <= model.operator_overlap_1[p, s, pp, ss, c, o] + model.operator_overlap_2[p, s, pp, ss, c, o]
    @model.Constraint(model.operator_overlap_index)
    def operator_overlap_auxiliary_constraint_2(model, p, s, pp, ss, c, o):
        return model.do[p, s, c, o] >= model.operator_overlap_1[p, s, pp, ss, c, o] + model.operator_overlap_2[p, s, pp, ss, c, o]
    @model.Constraint(model.operator_overlap_index)
    def operator_overlap_auxiliary_constraint_3(model, p, s, pp, ss, c, o):
        return model.do[pp, ss, c, o] >= model.operator_overlap_1[p, s, pp, ss, c, o] + model.operator_overlap_2[p, s, pp, ss, c, o]

    # *optional* additional constraint. The total duration of services assigned to one operator must
    # not be greater than the operator duration. This constraint could be omitted
    # without loss of correctedness but helps with a faster convergence.
    @model.Constraint(model.operators)
    def redundant_operator_cut(model, c, o):
        tuples_affected = [(p, s) for p, s, cc, oo in model.do_index if cc == c and oo == o]
        if len(tuples_affected) == 0 or sum(model.service_duration[s] for _, s in tuples_affected) <= model.operator_duration[c, o]:
            return pyo.Constraint.Skip
        return pyo.quicksum(model.do[p, s, c, o] * model.service_duration[s] for p, s in tuples_affected) <= model.operator_duration[c, o]

    ############################## OBJECTIVE FUNCTION ##############################

    # the solution value depends linearly by the total service duration of the
    # satisfied request, scaled by the requesting patient priority.
    @model.Objective(sense=pyo.maximize)
    def total_satisfied_service_durations(model):
        return pyo.quicksum(model.do[p, s, c, o] * model.service_duration[s] * model.patient_priority[p] for p, s, c, o in model.do_index)

    return model


def get_results_from_subproblem_model(model):

    scheduled_requests = []
    for p, s, c, o in model.do_index:
        if pyo.value(model.do[p, s, c, o]) < 0.01:
            continue
        time_slot = int(pyo.value(model.time[p, s]) - 1)
        scheduled_requests.append({
            'patient': p,
            'service': s,
            'care_unit': c,
            'operator': o,
            'time': time_slot
        })

    rejected_requests = []
    for p, s in model.satisfy_index:
        if pyo.value(model.satisfy[p, s]) < 0.01:
            rejected_requests.append({
                'patient': p,
                'service': s
            })

    scheduled_requests.sort(key=lambda v: (v['patient'], v['service'], v['care_unit'], v['operator'], v['time']))
    rejected_requests.sort(key=lambda v: (v['patient'], v['service']))

    return {
        'scheduled': scheduled_requests,
        'rejected': rejected_requests
    }