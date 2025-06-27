import pyomo.environ as pyo


def get_monolithic_model(instance, additional_info):
    '''Funzione che ritorna il modello MILP monolitico del problema'''

    # Controllo sull'uguaglianza degli operatori per una maggiore efficienza
    # nella scrittura dei vincoli
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
    
    model = pyo.ConcreteModel()

    # INSIEMI ##################################################################

    # Insieme di giorni (casting ad intero)
    model.days = pyo.Set(initialize=sorted([int(d) for d in instance['days'].keys()]), domain=pyo.NonNegativeIntegers)

    # Tutte le coppie (day, care_unit)
    model.care_units = pyo.Set(initialize=sorted([(int(d), c) for d, day in instance['days'].items() for c in day.keys()]))

    # Triple (day, care_unit, operator) per ogni operatore presente
    model.operators = pyo.Set(initialize=sorted([(int(d), c, o)
        for d, day in instance['days'].items()
        for c, cu in day.items()
        for o in cu.keys()]))

    # PARAMETRI ################################################################

    # max_time[d, c] è il massimo tempo di fine degli operatori in d, c
    @model.Param(model.care_units, domain=pyo.NonNegativeIntegers, mutable=False)
    def max_time(model, d, c):
        return max([o['start'] + o['duration'] for o in instance['days'][str(d)][c].values()]) + 1

    # INDICI ###################################################################


    # Insieme di quadruple (p, s, start, end) per ogni finestra
    window_index = set()

    # Tuple (p, s, d, c, o) per ogni assegnamento possibile
    do_index = set()

    # Tupla (p1, p2, s1, s2, d, c1, op1, c2, op2) per ogni possibile conflitto
    # dello stesso paziente o operatore
    overlap_index = set()

    # Tuple (p, s1, s2, start1, end1, start2, end2) di ogni finestra dello
    # stesso paziente che si sovrappongono
    window_overlap_index = set()

    # Indici nella forma (p, d)
    pat_days_index = set()

    # Tuple (p, s, pp, ss, d, c, o, cc, oo, ws, we, wws, wwe)
    overlap_constraint_index = set()

    # Tuple (p, s, d, c, o, ws, we) se gli operatori non sono tutti uguali
    if not are_all_operators_equal:
        schedulable_tuples_with_operators_and_windows = set()

    for patient_name, patient in instance['patients'].items():
        for service_name, windows in patient['requests'].items():
            for window in windows:
                window_index.add((patient_name, service_name, window[0], window[1]))

    for p, s, ws, we in window_index:
        c = instance['services'][s]['care_unit']

        for d in range(ws, we + 1):
            for o in instance['days'][str(d)][c].keys():
                do_index.add((p, s, d, c, o))
                pat_days_index.add((p, d))

                if not are_all_operators_equal:
                    schedulable_tuples_with_operators_and_windows.add((p, s, d, c, o, ws, we))

    for p1, s1, d1, c1, o1 in do_index:
        for p2, s2, d2, c2, o2 in do_index:
            
            # Solo giorni uguali
            if d1 != d2:
                continue
            
            # Il paziente o l'operatore deve essere lo stesso
            if p1 != p2 and (o1 != o2 or c1 != c2):
                continue

            # Non la stessa richiesta
            if p1 == p2 and s1 == s2:
                continue
            
            # Controllo sulla simmetria
            if s1 > s2 or (p1 > p2 and s1 == s2) or (o1 >= o2 and p1 == p2 and s1 == s2):
                continue

            overlap_index.add((p1, s1, p2, s2, d1, c1, o1, c2, o2))

    for p, patient in instance['patients'].items():
        for s, windows in patient['requests'].items():
            
            # Bisogna avere almeno due finestre
            window_number = len(windows)
            if window_number < 2:
                continue

            # Itera tutte le coppie cercando la sovrapposizione
            for i in range(window_number - 1):
                ws1, we1 = windows[i]
                
                for j in range(i + 1, window_number):
                    ws2, we2 = windows[j]

                    if ((we1 >= ws2 and we1 <= we2) or
                        (we2 >= ws1 and we2 <= we1)):
                        window_overlap_index.add((p, s, ws1, we1, ws2, we2))

    for p, s, pp, ss, d, c, o, cc, oo in overlap_index:
        for ppp, sss, ws, we in window_index:
            if p != ppp or s != sss or we < d or ws > d:
                continue
            for pppp, ssss, wws, wwe in window_index:
                if pp != pppp or ss != ssss or wwe < d or wws > d:
                    continue
                overlap_constraint_index.add((p, s, pp, ss, d, c, o, cc, oo, ws, we, wws, wwe))

    model.window_index = pyo.Set(initialize=sorted(window_index))
    model.do_index = pyo.Set(initialize=sorted(do_index))
    model.overlap_index = pyo.Set(initialize=sorted(overlap_index))
    model.window_overlap_index = pyo.Set(initialize=sorted(window_overlap_index))
    model.pat_days_index = pyo.Set(initialize=sorted(pat_days_index))
    model.overlap_constraint_index = pyo.Set(initialize=sorted(overlap_constraint_index))
    del window_index, do_index, overlap_index, window_overlap_index, overlap_constraint_index
    
    if not are_all_operators_equal:
        model.duration_index = pyo.Set(initialize=sorted(schedulable_tuples_with_operators_and_windows))
        del schedulable_tuples_with_operators_and_windows

    def get_time_bounds(model, p: str, s: str, ws: int, we: int) -> tuple[int, int]:
        '''Ritorna (0, T) dove T è l'ultimo slot temporale utile per svolgere
        il servizio da un operatore dell'unità di cura corretta.'''

        service_duration = instance['services'][s]['duration']

        c = instance['services'][s]['care_unit']
        max_operator_end = max(o['start'] + 1 + o['duration'] for d in range(ws, we + 1) for o in instance['days'][str(d)][c].values())
        
        return (0, max_operator_end - service_duration)

    # VARIABILI ################################################################

    # Variabili decisionali che descrivono se una finestra è soddisfatta
    model.window = pyo.Var(model.window_index, domain=pyo.Binary)

    # Se una richiesta è sodisfatta le variabili 'time' assumono un valore
    # positivo che descrive il tempo di inizio
    model.time = pyo.Var(model.window_index, domain=pyo.NonNegativeIntegers, bounds=get_time_bounds)

    # Variabili decisionali che descrivono che operatore svolge ogni richiesta
    # in che giorno
    model.do = pyo.Var(model.do_index, domain=pyo.Binary)

    # Variabili ausiliarie per la mutua esclusione delle richieste assegnate
    model.overlap_aux_1 = pyo.Var(model.overlap_index, domain=pyo.Binary)
    model.overlap_aux_2 = pyo.Var(model.overlap_index, domain=pyo.Binary)

    # Variabili che sono 1 se una coppia di finestre dello stesso paziente e
    # servizio è svolta in maniera non efficiente
    model.window_overlap = pyo.Var(model.window_overlap_index, domain=pyo.Binary)

    # Variabili che specificano se un paziente ha almeno una richiesta in un
    # certo giorno
    if 'minimize_hospital_accesses' in additional_info:
        model.pat_use_day = pyo.Var(model.pat_days_index, domain=pyo.Binary)
 
    # VINCOLI ##################################################################

    # Se una finestra è soddisfatta, è soddisfatta in un unico giorno interno
    # alla sua finestra
    @model.Constraint(model.window_index)
    def link_window_to_do_variables(model, p, s, ws, we):
        return pyo.quicksum([model.do[pp, ss, d, c, o] for pp, ss, d, c, o in model.do_index if p == pp and s == ss and d >= ws and d <= we and c == instance['services'][s]['care_unit']]) == model.window[p, s, ws, we]

    # Modulazione del dominio di 'time' in funzione di un'effettivo servizio
    # svolto: time>0 se e solo se window=1
    if are_all_operators_equal:
        @model.Constraint(model.window_index)
        def link_time_to_window_variables(model, p, s, ws, we):
            c = instance['services'][s]['care_unit']
            return model.time[p, s, ws, we] <= model.window[p, s, ws, we] * (model.max_time[ws, c] - instance['services'][s]['duration'])
        @model.Constraint(model.window_index)
        def link_window_to_time_variables(model, p, s, ws, we):
            return model.window[p, s, ws, we] <= model.time[p, s, ws, we]

    else:
        @model.Constraint(model.duration_index)
        def link_time_to_window_variables(model, p, s, d, c, o, ws, we):
            return model.time[p, s, ws, we] <= instance['days'][str(d)][c][o]['start'] + 1 + instance['days'][str(d)][c][o]['duration'] - instance['services'][s]['duration'] + (1 - model.do[p, s, d, c, o]) * model.max_time[d, c]
        @model.Constraint(model.duration_index)
        def link_window_to_time_variables(model, p, s, d, c, o, ws, we):
            return model.do[p, s, d, c, o] * instance['days'][str(d)][c][o]['start'] + 1 <= model.time[p, s, ws, we]

    # Disguinzione dei servizi dello stesso paziente o operatore
    @model.Constraint(model.overlap_constraint_index)
    def services_not_overlap_1(model, p, s, pp, ss, d, c, o, cc, oo, ws, we, wws, wwe):
        return model.time[p, s, ws, we] + instance['services'][s]['duration'] * model.do[p, s, d, c, o] <= model.time[pp, ss, wws, wwe] + (1 - model.overlap_aux_1[p, s, pp, ss, d, c, o, cc, oo]) * model.max_time[d, c]
    @model.Constraint(model.overlap_constraint_index)
    def services_not_overlap_2(model, p, s, pp, ss, d, c, o, cc, oo, ws, we, wws, wwe):
        return model.time[pp, ss, wws, wwe] + instance['services'][ss]['duration'] * model.do[pp, ss, d, cc, oo] <= model.time[p, s, ws, we] + (1 - model.overlap_aux_2[p, s, pp, ss, d, c, o, cc, oo]) * model.max_time[d, cc]

    # Vincoli ausilari che regolano le variabili 'overlap_aux'
    # o-----------------------------------------o
    # | A | B | overlap_aux_1 + overlap_aux_2   |
    # |---|---|---------------------------------|
    # | o | o | sum to one                      |
    # | o | x | zero                            |
    # | x | o | zero                            |
    # | x | x | zero                            |
    # o-----------------------------------------o
    @model.Constraint(model.overlap_index)
    def overlap_auxiliary_constraint_1(model, p, s, pp, ss, d, c, o, cc, oo):
        return model.do[p, s, d, c, o] + model.do[pp, ss, d, cc, oo] - 1 <= model.overlap_aux_1[p, s, pp, ss, d, c, o, cc, oo] + model.overlap_aux_2[p, s, pp, ss, d, c, o, cc, oo]
    @model.Constraint(model.overlap_index)
    def overlap_auxiliary_constraint_2(model, p, s, pp, ss, d, c, o, cc, oo):
        return model.do[p, s, d, c, o] >= model.overlap_aux_1[p, s, pp, ss, d, c, o, cc, oo] + model.overlap_aux_2[p, s, pp, ss, d, c, o, cc, oo]
    @model.Constraint(model.overlap_index)
    def overlap_auxiliary_constraint_3(model, p, s, pp, ss, d, c, o, cc, oo):
        return model.do[pp, ss, d, cc, oo] >= model.overlap_aux_1[p, s, pp, ss, d, c, o, cc, oo] + model.overlap_aux_2[p, s, pp, ss, d, c, o, cc, oo]

    # Non è possibile inserire richieste dello stesso paziente la cui durata
    # totale eccede gli slot temporali di quel giorno nelle unità di cura
    # toccate
    if 'use_redundant_patient_cut' in additional_info:
        @model.Constraint(model.pat_days_index)
        def redundant_patient_cut(model, p, d):
            
            tuples_affected = [(s, c, o) for pp, s, dd, c, o in model.do_index if p == pp and d == dd]
            
            if len(tuples_affected) == 0:
                return pyo.Constraint.Skip
            
            involved_care_unit_names = set(tuples_affected[i][1] for i in range(len(tuples_affected)))
            max_time_slot = max(model.max_time[d, c] for c in involved_care_unit_names)
            
            return pyo.quicksum(model.do[p, s, d, cc, o] * instance['services'][s]['duration'] for s, cc, o in tuples_affected) <= max_time_slot

    # Non è possibile inserire richieste dello stesso operatore la cui durata
    # totale eccede i suoi slot temporali
    if 'use_redundant_operator_cut' in additional_info:
        @model.Constraint(model.operators)
        def redundant_operator_cut(model, d, c, o):
            
            tuples_affected = [(p, s) for p, s, dd, cc, oo in model.do_index if d == dd and cc == c and oo == o]
            
            if len(tuples_affected) == 0:
                return pyo.Constraint.Skip
            
            operator_duration = instance['days'][str(d)][c][o]['duration']
            
            if sum(instance['services'][s]['duration'] for _, s in tuples_affected) <= operator_duration:
                return pyo.Constraint.Skip
    
            return pyo.quicksum(model.do[p, s, d, c, o] * instance['services'][s]['duration'] for p, s in tuples_affected) <= operator_duration

    # Vincolo che lega le variabili 'window_overlap' alle variabili 'do'
    @model.Constraint(model.window_overlap_index)
    def window_overlap_constraint(model, p, s, ws, we, wws, wwe):
        
        min_ws = min(ws, wws)
        max_we = max(we, wwe)
        
        tuples_affected = [(p, s, d, c, o) for d in range(min_ws, max_we + 1) for pp, ss, dd, c, o in model.do_index if p == pp and s == ss and d == dd]

        if len(tuples_affected) < 2:
            return pyo.Constraint.Skip
        
        return pyo.quicksum(model.do[p, s, d, c, o] for p, s, d, c, o in tuples_affected) <= 1 + model.window_overlap[p, s, ws, we, wws, wwe]

    # Vincolo che forza 'pat_use_day' ad 1 se è presente almeno una richiesta
    # del paziente in quel giorno
    if 'minimize_hospital_accesses' in additional_info:
        @model.Constraint(model.do_index)
        def if_patient_uses_day(model, p, s, d, c, o):
            return model.do[p, s, d, c, o] <= model.pat_use_day[p, d]


    # FUNZIONE OBIETTIVO #######################################################

    # L'obiettivo è massimizzare la durata dei servizi svolti, pesati per la
    # priorità dei pazienti. Un vincolo secondario è quello di minimizzare il
    # numero di giorni che ciascun paziente utilizza. Si cerca inoltre di
    # minimizzare programmazioni inefficienti per quanto riguarda finestre dello
    # stesso paziente e servizio che si sovrappongono

    if 'minimize_hospital_accesses' in additional_info:
        @model.Objective(sense=pyo.maximize)
        def objective_function(model):
            return (pyo.quicksum(model.do[p, s, d, c, o] * instance['services'][s]['duration'] * instance['patients'][p]['priority'] for p, s, d, c, o in model.do_index)
                    - 1e6 * pyo.quicksum(model.window_overlap[p, s, ws, we, wws, wwe] for p, s, ws, we, wws, wwe in model.window_overlap_index)
                    - 1.0 / len(model.pat_days_index) * pyo.quicksum(model.pat_use_day[p, d] for p, d in model.pat_days_index))
    else:
        @model.Objective(sense=pyo.maximize)
        def objective_function(model):
            return (pyo.quicksum(pyo.quicksum(model.do[p, s, d, c, o] * instance['services'][s]['duration'] * instance['patients'][p]['priority'] for p, s, d, c, o in model.do_index))
                    - 1e6 * pyo.quicksum(model.window_overlap[p, s, ws, we, wws, wwe] for p, s, ws, we, wws, wwe in model.window_overlap_index))

    return model


def get_results_from_monolithic_model(model):
    '''Funzione che ritorna i risultati (inseriti e rigettati) contenuti nel
    modello monolitico risolto.'''

    # Oggetto indicizzato per giorno contenente la lista di tuple
    # (p, s, c, o, t)
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

    # Elenco di terne (p, s, w) di ogni finestra non soddisfatta
    rejected_requests = []
    for p, s, ws, we in model.window_index:
        if pyo.value(model.window[p, s, ws, we]) < 0.01:
            rejected_requests.append({
                'patient': p,
                'service': s,
                'window': [ws, we]
            })

    # Ordina le chiavi
    scheduled_requests_grouped_per_day = dict(sorted([(k, v) for k, v in scheduled_requests_grouped_per_day.items()], key=lambda vv: int(vv[0])))
    for daily_results in scheduled_requests_grouped_per_day.values():
        daily_results.sort(key=lambda v: (v['patient'], v['service'], v['care_unit'], v['operator'], v['time']))
    rejected_requests.sort(key=lambda v: (v['patient'], v['service']))

    return {
        'scheduled': scheduled_requests_grouped_per_day,
        'rejected': rejected_requests
    }