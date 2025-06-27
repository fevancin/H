import pyomo.environ as pyo


def get_fat_subproblem_model(instance, additional_info):
    '''Funzione che ritorna il modello MILP del sottoproblema con
    assegnazione dell'operatore.'''

    model = pyo.ConcreteModel()
    
    # INSIEMI ##################################################################
   
    # Nomi delle unità di cura
    model.care_units = pyo.Set(initialize=sorted([c for c in instance['day'].keys()]))

    # Tutte le coppie (care_unit, operator)
    model.operators = pyo.Set(initialize=sorted([(c, o)
        for c, cu in instance['day'].items()
        for o in cu.keys()]))

    # PARAMETRI ################################################################

    # max_time[c] è il massimo tempo di fine degli operatori in c
    @model.Param(model.care_units, domain=pyo.NonNegativeIntegers, mutable=False)
    def max_time(model, c):
        return max([o['start'] + o['duration'] for o in instance['day'][c].values()]) + 1

    # INDICI ###################################################################

    # Coppie (p, s) per ogni richiesta
    satisfy_index = set()

    # Quadruple (p, s, c, o) per ogni possibile assegnamento valido
    do_index = set()

    # Terne (p, s1, s2) per ogni coppia di richieste dello stesso paziente
    patient_overlap_index = set()

    # Tuple (p1, s1, p2, s2, c, o)
    operator_overlap_index = set()

    for p, patient in instance['patients'].items():
        for s in patient['requests']:
            satisfy_index.add((p, s))

            duration = instance['services'][s]['duration']
            c = instance['services'][s]['care_unit']

            for o, operator in instance['day'][c].items():
                if operator['duration'] < duration:
                    continue

                do_index.add((p, s, c, o))

    for p, patient in instance['patients'].items():
        
        # Bisogna avere almeno due richieste
        request_number = len(patient['requests'])
        if request_number < 2:
            continue
        
        # Itera tutte le coppie
        for i in range(request_number - 1):
            s1 = patient['requests'][i]
            for j in range(i + 1, request_number):
                s2 = patient['requests'][j]
                patient_overlap_index.add((p, s1, s2))

    for p, s, c, o in do_index:
        for pp, ss, cc, oo in do_index:
            
            # Deve essere lo stesso operatore
            if c != cc or o != oo:
                continue
            
            # Controllo sulla simmetria
            if p >= pp or (p == pp and s >= ss):
                continue
            
            operator_overlap_index.add((p, s, pp, ss, c, o))

    model.satisfy_index = pyo.Set(initialize=sorted(satisfy_index))
    model.do_index = pyo.Set(initialize=sorted(do_index))
    model.patient_overlap_index = pyo.Set(initialize=sorted(patient_overlap_index))
    model.operator_overlap_index = pyo.Set(initialize=sorted(operator_overlap_index))
    del satisfy_index, do_index, patient_overlap_index, operator_overlap_index

    def get_time_bounds(model, p: str, s: str) -> tuple[int, int]:
        '''Ritorna (0, T) dove T è l'ultimo slot temporale utile per svolgere
        il servizio da un operatore dell'unità di cura corretta.'''

        service_duration = instance['services'][s]['duration']

        c = instance['services'][s]['care_unit']
        max_operator_end = max(o['start'] + 1 + o['duration'] for o in instance['day'][c].values())
        
        return (0, max_operator_end - service_duration)

    # VARIABILI ################################################################

    # Variabili decisionali che controllano quale richiesta è soddisfatta
    model.satisfy = pyo.Var(model.satisfy_index, domain=pyo.Binary)

    # Se una richiesta è sodisfatta le variabili 'time' assumono un valore
    # positivo che descrive il tempo di inizio
    model.time = pyo.Var(model.satisfy_index, domain=pyo.NonNegativeIntegers, bounds=get_time_bounds)

    # Variabili decisionali che descrivono che operatore svolge ogni richiesta
    model.do = pyo.Var(model.do_index, domain=pyo.Binary)

    # Variabili ausiliarie per la mutua esclusione delle richieste assegnate
    model.patient_overlap = pyo.Var(model.patient_overlap_index, domain=pyo.Binary)
    model.operator_overlap_1 = pyo.Var(model.operator_overlap_index, domain=pyo.Binary)
    model.operator_overlap_2 = pyo.Var(model.operator_overlap_index, domain=pyo.Binary)

    # VINCOLI ##################################################################

    # Se una richiesta viene soddisfatta, viene assegnata una volta sola
    @model.Constraint(model.satisfy_index)
    def link_satisfy_to_do_variables(model, p, s):
        return model.satisfy[p, s] == pyo.quicksum([model.do[pp, ss, c, o] for pp, ss, c, o in model.do_index if p == pp and s == ss and c == instance['services'][s]['care_unit']])
    
    # Rispetto dei tempi di attività degli operatori
    @model.Constraint(model.do_index)
    def respect_operator_start(model, p, s, c, o):
        return (instance['day'][c][o]['start'] + 1) * model.do[p, s, c, o] <= model.time[p, s]
    @model.Constraint(model.do_index)
    def respect_operator_end(model, p, s, c, o):
        end = instance['day'][c][o]['start'] + 1 + instance['day'][c][o]['duration']
        return model.time[p, s] + instance['services'][s]['duration'] <= end + (1 - model.do[p, s, c, o]) * model.max_time[c]

    # Disgiunzione dei servizi dello stesso paziente
    @model.Constraint(model.patient_overlap_index)
    def patient_not_overlap_1(model, p, s, ss):
        return model.time[p, s] + instance['services'][s]['duration'] * model.satisfy[p, s] <= model.time[p, ss] + (1 - model.patient_overlap[p, s, ss]) * model.max_time[instance['services'][s]['care_unit']]
    @model.Constraint(model.patient_overlap_index)
    def patient_not_overlap_2(model, p, s, ss):
        return model.time[p, ss] + instance['services'][ss]['duration'] * model.satisfy[p, ss] <= model.time[p, s] + (model.patient_overlap[p, s, ss]) * model.max_time[instance['services'][ss]['care_unit']]

    # Vincoli ausilari che regolano le variabili 'patient_overlap'
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

    # Disgiunzione dei servizi dello stesso operatore
    @model.Constraint(model.operator_overlap_index)
    def operator_not_overlap_1(model, p, s, pp, ss, c, o):
        return model.time[p, s] + instance['services'][s]['duration'] * model.do[p, s, c, o] <= model.time[pp, ss] + (1 - model.operator_overlap_1[p, s, pp, ss, c, o]) * model.max_time[c]
    @model.Constraint(model.operator_overlap_index)
    def operator_not_overlap_2(model, p, s, pp, ss, c, o):
        return model.time[pp, ss] + instance['services'][ss]['duration'] * model.do[pp, ss, c, o] <= model.time[p, s] + (1 - model.operator_overlap_2[p, s, pp, ss, c, o]) * model.max_time[c]

    # Vincoli ausilari che regolano le variabili 'operator_overlap'
    # o-------------------------------------------------o
    # | A | B | operator_overlap_1 + operator_overlap_2 |
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

    # La durata totale dei servizi assegnati ad un operatore non può superare la
    # durata di attività di quest'ultimo
    @model.Constraint(model.operators)
    def respect_operator_duration(model, c, o):
        
        tuples_affected = [(p, s) for p, s, cc, oo in model.do_index if cc == c and oo == o]
        
        if len(tuples_affected) == 0 or sum(instance['services'][s]['duration'] for _, s in tuples_affected) <= instance['day'][c][o]['duration']:
            return pyo.Constraint.Skip
        
        return pyo.quicksum(model.do[p, s, c, o] * instance['services'][s]['duration'] for p, s in tuples_affected) <= instance['day'][c][o]['duration']

    # FUNZIONE OBIETTIVO #######################################################

    # L'obiettivo è massimizzare la durata dei servizi svolti, pesati per la
    # priorità dei pazienti. 
    @model.Objective(sense=pyo.maximize)
    def objective_function(model):
        return pyo.quicksum(model.satisfy[p, s] * instance['services'][s]['duration'] * instance['patients'][p]['priority'] for p, s in model.satisfy_index)

    return model


def get_results_from_fat_subproblem_model(model):
    '''Funzione che ritorna i risultati (inseriti e rigettati) contenuti nel
    modello del sottoproblema risolto.'''

    # Lista di tuple (p, s, c, o, t)
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

    # Elenco di coppie (p, s) di ogni richiesta non soddisfatta
    rejected_requests = []
    for p, s in model.satisfy_index:
        if pyo.value(model.satisfy[p, s]) < 0.01:
            rejected_requests.append({
                'patient': p,
                'service': s
            })

    # Ordina le chiavi
    scheduled_requests.sort(key=lambda v: (v['patient'], v['service'], v['care_unit'], v['operator'], v['time']))
    rejected_requests.sort(key=lambda v: (v['patient'], v['service']))

    return {
        'scheduled': scheduled_requests,
        'rejected': rejected_requests
    }


def get_slim_subproblem_model(instance, additional_info):
    '''Funzione che ritorna il modello MILP del sottoproblema senza
    assegnazione dell'operatore.'''

    model = pyo.ConcreteModel()
    
    # INSIEMI ##################################################################
   
    # Nomi delle unità di cura
    model.care_units = pyo.Set(initialize=sorted([c for c in instance['day'].keys()]))

    # Tutte le coppie (care_unit, operator)
    model.operators = pyo.Set(initialize=sorted([(c, o)
        for c, cu in instance['day'].items()
        for o in cu.keys()]))

    # PARAMETRI ################################################################

    # max_time[c] è il massimo tempo di fine degli operatori in c
    @model.Param(model.care_units, domain=pyo.NonNegativeIntegers, mutable=False)
    def max_time(model, c):
        return max([o['start'] + o['duration'] for o in instance['day'][c].values()]) + 1

    # INDICI ###################################################################

    # Quadruple (p, s, c, o) per ogni possibile assegnamento valido
    do_index = set()

    # Tuple (p, s1, c1, o1, s2, c2, o2) per ogni coppia di richieste dello
    # stesso paziente o operatore
    overlap_index = set()

    for p, patient in instance['patients'].items():
        for request in patient['requests']:
            
            s = request['service']
            c = request['care_unit']
            o = request['operator']

            do_index.add((p, s, c, o))

    for p, s, c, o in do_index:
        for pp, ss, cc, oo in do_index:
            
            # Deve essere lo stesso paziente o operatore
            if p != pp and (c != cc or o != oo):
                continue
            
            # Controllo sulla simmetria
            if p > pp or (p == pp and s >= ss) or (p == pp and s == ss and c == cc and o == oo):
                continue
            
            overlap_index.add((p, s, c, o, pp, ss, cc, oo))

    model.do_index = pyo.Set(initialize=sorted(do_index))
    model.overlap_index = pyo.Set(initialize=sorted(overlap_index))
    del do_index, overlap_index

    def get_time_bounds(model, p: str, s: str, c: str, o: str) -> tuple[int, int]:
        '''Ritorna (0, T) dove T è l'ultimo slot temporale utile per svolgere
        il servizio da un operatore dell'unità di cura corretta.'''

        service_duration = instance['services'][s]['duration']

        operator_end = instance['day'][c][o]['duration']
        
        return (0, operator_end - service_duration)

    # VARIABILI ################################################################

    # Se una richiesta è sodisfatta le variabili 'time' assumono un valore
    # positivo che descrive il tempo di inizio
    model.time = pyo.Var(model.do_index, domain=pyo.NonNegativeIntegers, bounds=get_time_bounds)

    # Variabili decisionali che descrivono che operatore svolge ogni richiesta
    model.do = pyo.Var(model.do_index, domain=pyo.Binary)

    # Variabili ausiliarie per la mutua esclusione delle richieste assegnate
    model.overlap = pyo.Var(model.overlap_index, domain=pyo.Binary)

    # VINCOLI ##################################################################

    # Rispetto dei tempi di attività degli operatori
    @model.Constraint(model.do_index)
    def respect_operator_start(model, p, s, c, o):
        return (instance['day'][c][o]['start'] + 1) * model.do[p, s, c, o] <= model.time[p, s, c, o]
    @model.Constraint(model.do_index)
    def respect_operator_end(model, p, s, c, o):
        return model.time[p, s, c, o] <= (instance['day'][c][o]['start'] + 1 + instance['day'][c][o]['duration'] - instance['services'][s]['duration']) * model.do[p, s, c, o]

    # Disgiunzione dei servizi dello stesso paziente o operatore
    @model.Constraint(model.overlap_index)
    def not_overlap_1(model, p, s, c, o, pp, ss, cc, oo):
        return model.time[p, s, c, o] + instance['services'][s]['duration'] * model.do[p, s, c, o] <= model.time[pp, ss, cc, oo] + (1 - model.overlap[p, s, c, o, pp, ss, cc, oo]) * model.max_time[instance['services'][s]['care_unit']]
    @model.Constraint(model.overlap_index)
    def not_overlap_2(model, p, s, c, o, pp, ss, cc, oo):
        return model.time[pp, ss, cc, oo] + instance['services'][ss]['duration'] * model.do[pp, ss, cc, oo] <= model.time[p, s, c, o] + (model.overlap[p, s, c, o, pp, ss, cc, oo]) * model.max_time[instance['services'][ss]['care_unit']]

    # Vincoli ausilari che regolano le variabili 'overlap'
    # o-----------------------------------------o
    # | A | B | overlap                         |
    # |---|---|---------------------------------|
    # | o | o | zero or one                     |
    # | o | x | zero                            |
    # | x | o | one                             |
    # | x | x | zero                            |
    # o-----------------------------------------o
    @model.Constraint(model.overlap_index)
    def overlap_auxiliary_constraint_1(model, p, s, c, o, pp, ss, cc, oo):
        return model.overlap[p, s, c, o, pp, ss, cc, oo] <= model.do[pp, ss, cc, oo]
    @model.Constraint(model.overlap_index)
    def overlap_auxiliary_constraint_2(model, p, s, c, o, pp, ss, cc, oo):
        return model.do[pp, ss, cc, oo] - model.do[p, s, c, o] <= model.overlap[p, s, c, o, pp, ss, cc, oo]

    # FUNZIONE OBIETTIVO #######################################################

    # L'obiettivo è massimizzare la durata dei servizi svolti, pesati per la
    # priorità dei pazienti. 
    @model.Objective(sense=pyo.maximize)
    def objective_function(model):
        return pyo.quicksum(model.do[p, s, c, o] * instance['services'][s]['duration'] * instance['patients'][p]['priority'] for p, s, c, o in model.do_index)

    return model


def get_results_from_slim_subproblem_model(model):
    '''Funzione che ritorna i risultati (inseriti e rigettati) contenuti nel
    modello del sottoproblema risolto.'''

    # Lista di tuple (p, s, c, o, t)
    scheduled_requests = []
    
    # Elenco di coppie (p, s) di ogni richiesta non soddisfatta
    rejected_requests = []

    for p, s, c, o in model.do_index:
        
        if pyo.value(model.do[p, s, c, o]) < 0.01:
            rejected_requests.append({
                'patient': p,
                'service': s
            })

        else:
            time_slot = int(pyo.value(model.time[p, s, c, o]) - 1)
            scheduled_requests.append({
                'patient': p,
                'service': s,
                'care_unit': c,
                'operator': o,
                'time': time_slot
            })

    # Ordina le chiavi
    scheduled_requests.sort(key=lambda v: (v['patient'], v['service'], v['care_unit'], v['operator'], v['time']))
    rejected_requests.sort(key=lambda v: (v['patient'], v['service']))

    return {
        'scheduled': scheduled_requests,
        'rejected': rejected_requests
    }