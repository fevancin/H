import pyomo.environ as pyo


def get_slim_master_model(instance, additional_info: list[str]):
    '''Funzione che ritorna il modello MILP del problema master senza
    assegnazione dell'operatore.'''

    model = pyo.ConcreteModel()

    # INSIEMI ##################################################################
    
    # Insieme di giorni (casting ad intero)
    model.days = pyo.Set(initialize=sorted([int(d) for d in instance['days'].keys()]), domain=pyo.NonNegativeIntegers)

    # Tutte le coppie (day, care_unit)
    model.care_units = pyo.Set(initialize=sorted([(int(d), c) for d, day in instance['days'].items() for c in day.keys()]))

    # PARAMETRI ################################################################

    # capacity[d, c] è la somma delle durate degli operatori in c
    @model.Param(model.care_units, domain=pyo.NonNegativeIntegers, mutable=False)
    def capacity(model, d, c):
        return sum([o['duration'] for o in instance['days'][str(d)][c].values()])

    # max_time[d, c] è il massimo tempo di fine degli operatori in d
    @model.Param(model.days, domain=pyo.NonNegativeIntegers, mutable=False)
    def max_time(model, d):
        return max([o['start'] + o['duration'] for c in instance['days'][str(d)].keys() for o in instance['days'][str(d)][c].values()])

    # INDICI ###################################################################

    # Insieme di quadruple (p, s, start, end) per ogni finestra
    window_index = set()

    # Terne (p, s, d) per ogni giorno che può potenzialmente avere (p, s)
    do_index = set()

    # Indici nella forma (p, d)
    pat_days_index = set()

    # Insieme con tutte le coppie di finestre dello stesso paziente e servizio
    # che si intersecano: (p, s, start1, end1, start2, end2)
    window_overlap_index = set()

    for patient_name, patient in instance['patients'].items():
        for service_name, windows in patient['requests'].items():
            for window in windows:
                window_index.add((patient_name, service_name, window[0], window[1]))

    for patient_name, service_name, window_start, window_end in window_index:
        for day_index in range(window_start, window_end + 1):
            do_index.add((patient_name, service_name, day_index))
            pat_days_index.add((patient_name, day_index))

    for patient_name, patient in instance['patients'].items():
        for service_name, windows in patient['requests'].items():
            
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
                        window_overlap_index.add((patient_name, service_name, ws1, we1, ws2, we2))

    model.window_index = pyo.Set(initialize=sorted(window_index))
    model.do_index = pyo.Set(initialize=sorted(do_index))
    model.window_overlap_index = pyo.Set(initialize=sorted(window_overlap_index))
    model.pat_days_index = pyo.Set(initialize=sorted(pat_days_index))
    del window_index, do_index, window_overlap_index, pat_days_index

    # VARIABILI ################################################################

    # Variabili decisionali che descrivono se una finestra è soddisfatta
    model.window = pyo.Var(model.window_index, domain=pyo.Binary)

    # Variabili decisionali che specificano quando ogni servizio è programmato
    model.do = pyo.Var(model.do_index, domain=pyo.Binary)

    # Variabili che sono 1 se una coppia di finestre dello stesso paziente e
    # servizio è svolta in maniera non efficiente
    model.window_overlap = pyo.Var(model.window_overlap_index, domain=pyo.Binary)

    # Variabili che specificano se un paziente ha almeno una richiesta in un
    # certo giorno
    if 'minimize_hospital_accesses' in additional_info:
        model.pat_use_day = pyo.Var(model.pat_days_index, domain=pyo.Binary)
    
    # Componente giornaliera della funzione obiettivo
    if 'use_optimality_constraints' in additional_info:
        model.objective_function_day_component = pyo.Var(model.days, domain=pyo.NonNegativeIntegers)

    # VINCOLI ##################################################################

    # Se una finestra è soddisfatta, è soddisfatta in un unico giorno interno
    # alla sua finestra
    @model.Constraint(model.window_index)
    def link_window_to_do_variables(model, p, s, ws, we):
        return model.window[p, s, ws, we] == pyo.quicksum([model.do[pp, ss, d] for pp, ss, d in model.do_index if p == pp and s == ss and d >= ws and d <= we])

    # La durata totale dei servizi programmati per ogni unità di cura non può
    # superare la capacità di quest'ultima
    @model.Constraint(model.care_units)
    def respect_care_unit_capacity(model, d, c):
        
        tuples_affected = [(p, s) for p, s, dd in model.do_index if d == dd and c == instance['services'][s]['care_unit']]
        
        if len(tuples_affected) == 0:
            return pyo.Constraint.Skip
        if sum(instance['services'][s]['duration'] for _, s in tuples_affected) <= model.capacity[d, c]:
            return pyo.Constraint.Skip

        return pyo.quicksum(model.do[p, s, d] * instance['services'][s]['duration'] for p, s in tuples_affected) <= model.capacity[d, c]

    # Vincolo che lega le variabili 'window_overlap' alle variabili 'do'
    @model.Constraint(model.window_overlap_index)
    def window_overlap_constraint(model, p, s, ws, we, wws, wwe):
        
        min_ws = min(ws, wws)
        max_we = max(we, wwe)
        
        tuples_affected = [d for d in range(min_ws, max_we + 1) for pp, ss, dd in model.do_index if p == pp and s == ss and d == dd]
        
        return pyo.quicksum(model.do[p, s, d] for d in tuples_affected) <= 1 + model.window_overlap[p, s, ws, we, wws, wwe]

    # Non è possibile inserire richieste dello stesso paziente la cui durata
    # totale eccede gli slot temporali di quel giorno
    @model.Constraint(model.pat_days_index)
    def patient_total_duration(model, p, d):
        
        tuples_affected = [s for pp, s, dd in model.do_index if pp == p and dd == d]
        
        if sum(instance['services'][s]['duration'] for s in tuples_affected) <= model.max_time[d]:
            return pyo.Constraint.Skip
        
        return pyo.quicksum([model.do[p, s, d] * instance['services'][s]['duration'] for s in tuples_affected]) <= model.max_time[d]

    # Vincolo che forza 'pat_use_day' ad 1 se è presente almeno una richiesta
    # del paziente in quel giorno
    if 'minimize_hospital_accesses' in additional_info:
        @model.Constraint(model.do_index)
        def if_patient_uses_day(model, p, s, d):
            return model.do[p, s, d] <= model.pat_use_day[p, d]

    # Vincoli che eliminano le possibili programmazioni che non sono inseribili
    # negli operatori senza avere qualche servizio a metà fra due
    if 'use_bin_packing' in additional_info:
        add_bin_packing_cuts_to_master_model(model, instance)

    # Vincoli di ottimalità
    if 'use_optimality_constraints' in additional_info:
        @model.Constraint(model.days)
        def link_objective_component(model, d):
            
            tuples_affected = [(p, s) for p, s, dd in model.do_index if d == dd]
            
            if len(tuples_affected) == 0:
                return model.objective_function_day_component[d] == 0
            
            return pyo.quicksum(model.do[p, s, d] * instance['services'][s]['duration'] * instance['patients'][p]['priority'] for p, s in tuples_affected) == model.objective_function_day_component[d]
    
        model.objective_value_constraints = pyo.ConstraintList()

    # FUNZIONE OBIETTIVO #######################################################

    # L'obiettivo è massimizzare la durata dei servizi svolti, pesati per la
    # priorità dei pazienti. Un vincolo secondario è quello di minimizzare il
    # numero di giorni che ciascun paziente utilizza. Si cerca inoltre di
    # minimizzare programmazioni inefficienti per quanto riguarda finestre dello
    # stesso paziente e servizio che si sovrappongono

    if 'minimize_hospital_accesses' in additional_info:
        @model.Objective(sense=pyo.maximize)
        def objective_function(model):
            return (pyo.quicksum(model.do[p, s, d] * instance['services'][s]['duration'] * instance['patients'][p]['priority'] for p, s, d in model.do_index)
                    - 1e6 * pyo.quicksum(model.window_overlap[p, s, ws, we, wws, wwe] for p, s, ws, we, wws, wwe in model.window_overlap_index)
                    - 1.0 / len(model.pat_days_index) * pyo.quicksum(model.pat_use_day[p, d] for p, d in model.pat_days_index))
    else:
        @model.Objective(sense=pyo.maximize)
        def objective_function(model):
            return (pyo.quicksum(pyo.quicksum(model.do[p, s, d] * instance['services'][s]['duration'] * instance['patients'][p]['priority'] for p, s, d in model.do_index))
                    - 1e6 * pyo.quicksum(model.window_overlap[p, s, ws, we, wws, wwe] for p, s, ws, we, wws, wwe in model.window_overlap_index))
    
    return model


def add_bin_packing_cuts_to_master_model(model, instance):

    # il numero di servizi lunghi più della metà dello shift non può essere
    # maggiore al numero di operatori
    @model.Constraint(model.care_units)
    def case_two(model, d, c):
        day_name = str(d)
        operator_number = len(instance['days'][day_name][c])
        operator_duration = instance['days'][day_name][c]['op00']['duration']
        tuple_list = [(p, s) for p, s, dd in model.do_index if d == dd and instance['services'][s]['care_unit'] == c and instance['services'][s]['duration'] >= (operator_duration * 0.5 + 1)]
        if len(tuple_list) == 0:
            return pyo.Constraint.Skip
        return pyo.quicksum([model.do[p, s, d] for p, s in tuple_list]) <= operator_number

    @model.Constraint(model.care_units)
    def case_three(model, d, c):
        day_name = str(d)
        operator_number = len(instance['days'][day_name][c])
        operator_duration = instance['days'][day_name][c]['op00']['duration']
        tuple_list = [(p, s) for p, s, dd in model.do_index if d == dd and instance['services'][s]['care_unit'] == c and instance['services'][s]['duration'] == int(operator_duration * 0.5)]
        greater_tuple_list = [(p, s) for p, s, dd in model.do_index if d == dd and instance['services'][s]['care_unit'] == c and instance['services'][s]['duration'] >= int(operator_duration * 0.5 + 1)]
        if len(tuple_list) == 0 or len(greater_tuple_list) == 0:
            return pyo.Constraint.Skip
        return pyo.quicksum([model.do[p, s, d] for p, s in tuple_list]) <= operator_number * 2.0 - 2.0 * pyo.quicksum([model.do[p, s, d] for p, s in greater_tuple_list])
    
    @model.Constraint(model.care_units)
    def case_four_a(model, d, c):
        day_name = str(d)
        operator_number = len(instance['days'][day_name][c])
        operator_duration = instance['days'][day_name][c]['op00']['duration']
        tuple_list = [(p, s) for p, s, dd in model.do_index if d == dd and instance['services'][s]['care_unit'] == c and instance['services'][s]['duration'] == int(operator_duration * 0.5 - 1)]
        greater_tuple_list = [(p, s) for p, s, dd in model.do_index if d == dd and instance['services'][s]['care_unit'] == c and instance['services'][s]['duration'] == int(operator_duration * 0.5 + 1)]
        if len(tuple_list) == 0 or len(greater_tuple_list) == 0:
            return pyo.Constraint.Skip
        return pyo.quicksum([model.do[p, s, d] for p, s in tuple_list]) <= operator_number * 2.0 - pyo.quicksum([model.do[p, s, d] for p, s in greater_tuple_list])
    
    @model.Constraint(model.care_units)
    def case_four_b(model, d, c):
        day_name = str(d)
        operator_number = len(instance['days'][day_name][c])
        operator_duration = instance['days'][day_name][c]['op00']['duration']
        tuple_list = [(p, s) for p, s, dd in model.do_index if d == dd and instance['services'][s]['care_unit'] == c and instance['services'][s]['duration'] == int(operator_duration * 0.5 - 1)]
        greater_tuple_list = [(p, s) for p, s, dd in model.do_index if d == dd and instance['services'][s]['care_unit'] == c and instance['services'][s]['duration'] == int(operator_duration * 0.5 + 2)]
        if len(tuple_list) == 0 or len(greater_tuple_list) == 0:
            return pyo.Constraint.Skip
        return pyo.quicksum([model.do[p, s, d] for p, s in tuple_list]) <= operator_number * 2.0 - 2.0 * pyo.quicksum([model.do[p, s, d] for p, s in greater_tuple_list])
    
    @model.Constraint(model.care_units)
    def case_five_a(model, d, c):
        day_name = str(d)
        operator_number = len(instance['days'][day_name][c])
        operator_duration = instance['days'][day_name][c]['op00']['duration']
        tuple_list = [(p, s) for p, s, dd in model.do_index if d == dd and instance['services'][s]['care_unit'] == c and instance['services'][s]['duration'] == int(operator_duration * 0.25)]
        greater_tuple_list = [(p, s) for p, s, dd in model.do_index if d == dd and instance['services'][s]['care_unit'] == c and instance['services'][s]['duration'] >= int(operator_duration * 0.5 + 1)]
        if len(tuple_list) == 0 or len(greater_tuple_list) == 0:
            return pyo.Constraint.Skip
        return pyo.quicksum([model.do[p, s, d] for p, s in tuple_list]) <= operator_number * 4.0 - 3.0 * pyo.quicksum([model.do[p, s, d] for p, s in greater_tuple_list])
    
    @model.Constraint(model.care_units)
    def case_five_b(model, d, c):
        day_name = str(d)
        operator_number = len(instance['days'][day_name][c])
        operator_duration = instance['days'][day_name][c]['op00']['duration']
        tuple_list = [(p, s) for p, s, dd in model.do_index if d == dd and instance['services'][s]['care_unit'] == c and instance['services'][s]['duration'] == int(operator_duration * 0.25)]
        greater_tuple_list = [(p, s) for p, s, dd in model.do_index if d == dd and instance['services'][s]['care_unit'] == c and instance['services'][s]['duration'] == int(operator_duration * 0.5)]
        if len(tuple_list) == 0:
            return pyo.Constraint.Skip
        return pyo.quicksum([model.do[p, s, d] for p, s in tuple_list]) <= operator_number * 4.0 - 2.0 * pyo.quicksum([model.do[p, s, d] for p, s in greater_tuple_list])


def add_optimality_constraints(model, instance, all_subproblem_results, max_possible_master_requests):
    '''Funzione che aggiunge i due vincoli di ottimalità ad ogni iterazione.'''

    # Per ogni giorno salva il valore della funzione obiettivo del sottoproblema
    solution_values = {}
    for day_name, day_results in all_subproblem_results.items():
        
        solution_value = 0
        
        for scheduled_request in day_results['scheduled']:
            
            patient_name = scheduled_request['patient']
            service_name = scheduled_request['service']
            
            solution_value += instance['services'][service_name]['duration'] * instance['patients'][patient_name]['priority']
        
        solution_values[day_name] = solution_value

    # Aggiungi il vincolo per cui z_d >= z_d* - M*sum(1 - x per ogni x=1) in
    # cui:
    # > z è la funzione obiettivo del giorno corrispondente al sottoproblema
    # > z* è il valore della funzione obiettivo restituita dal sottoproblema
    # > M è una costante grande
    # > x sono le variabili di schedulazione poste ad 1 dal sottoproblema.
    # Questo vincolo è relativo ad un certo giorno d.

    # Se il MP chiede almeno quello che aveva chiesto al SP, il valore della
    # funzione obiettivo sarà almeno z_d*.
    for day_name, day_results in all_subproblem_results.items():
        day_index = int(day_name)
        
        tuple_list = []
        for scheduled_request in day_results['scheduled']:
            patient_name = scheduled_request['patient']
            service_name = scheduled_request['service']
            tuple_list.append((patient_name, service_name, day_index))

        model.objective_value_constraints.add(expr=(model.objective_function_day_component[day_index] >= solution_values[day_name] - solution_values[day_name] * 100 * pyo.quicksum([(1 - model.do[p, s, d]) for p, s, d in tuple_list])))

    # Aggiungi il vincolo per cui z_d <= z_d* + M*sum(x per ogni x=0) in cui:
    # > z è la funzione obiettivo del giorno corrispondente al sottoproblema
    # > z* è il valore della funzione obiettivo restituita dal sottoproblema
    # > M è una costante grande
    # > x sono le variabili di schedulazione non richieste al sottoproblema.
    # Questo vincolo è relativo ad un certo giorno d.

    # Se il MP chiede di nuovo qualcosa in cui continua a non esserci almeno ciò
    # che non aveva chiesto prima, la funzione obiettivo non potrà essere
    # migliore.
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

        model.objective_value_constraints.add(expr=(model.objective_function_day_component[day_index] <= solution_values[day_name] + solution_values[day_name] * 100 * pyo.quicksum([model.do[p, s, d] for p, s, d in tuple_list])))


def get_results_from_slim_master_model(model):
    '''Funzione che ritorna i risultati (inseriti e rigettati) contenuti nel
    modello master risolto.'''

    # Oggetto indicizzato per giorno contenente la lista di coppie (p, s)
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
        daily_results.sort(key=lambda v: (v['patient'], v['service']))
    rejected_requests.sort(key=lambda v: (v['patient'], v['service']))

    return {
        'scheduled': scheduled_requests_grouped_per_day,
        'rejected': rejected_requests
    }


def get_fat_master_model(instance, additional_info: list[str]):
    '''Funzione che ritorna il modello MILP del problema master con
    assegnazione dell'operatore.'''

    model = pyo.ConcreteModel()

    # INSIEMI ##################################################################
    
    # Insieme di giorni (casting ad intero)
    model.days = pyo.Set(initialize=sorted([int(d) for d in instance['days'].keys()]), domain=pyo.NonNegativeIntegers)

    # Tutte le coppie (day, care_unit)
    model.operators = pyo.Set(initialize=sorted([(int(d), cn, o) for d, day in instance['days'].items() for cn, c in day.items() for o in c.keys()]))

    # PARAMETRI ################################################################

    # max_time[d, c] è il massimo tempo di fine degli operatori in d
    @model.Param(model.days, domain=pyo.NonNegativeIntegers, mutable=False)
    def max_time(model, d):
        return max([o['start'] + o['duration'] for c in instance['days'][str(d)].keys() for o in instance['days'][str(d)][c].values()])

    # INDICI ###################################################################

    # Insieme di quadruple (p, s, start, end) per ogni finestra
    window_index = set()

    # Tuple (p, s, d, c, o) per ogni opreatore che può soddisfare (p, s)
    do_index = set()

    # Indici nella forma (p, d)
    pat_days_index = set()

    # Insieme con tutte le coppie di finestre dello stesso paziente e servizio
    # che si intersecano: (p, s, start1, end1, start2, end2)
    window_overlap_index = set()

    for p, patient in instance['patients'].items():
        for s, windows in patient['requests'].items():
            for w in windows:
                window_index.add((p, s, w[0], w[1]))

    for p, s, ws, we in window_index:
        c = instance['services'][s]['care_unit']
        for d in range(ws, we + 1):
            for o in instance['days'][str(d)][c].keys():
                do_index.add((p, s, d, c, o))
            pat_days_index.add((p, d))

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

    model.window_index = pyo.Set(initialize=sorted(window_index))
    model.do_index = pyo.Set(initialize=sorted(do_index))
    model.window_overlap_index = pyo.Set(initialize=sorted(window_overlap_index))
    model.pat_days_index = pyo.Set(initialize=sorted(pat_days_index))
    del window_index, do_index, window_overlap_index, pat_days_index

    # VARIABILI ################################################################

    # Variabili decisionali che descrivono se una finestra è soddisfatta
    model.window = pyo.Var(model.window_index, domain=pyo.Binary)

    # Variabili decisionali che specificano quando ogni servizio è programmato
    model.do = pyo.Var(model.do_index, domain=pyo.Binary)

    # Variabili che sono 1 se una coppia di finestre dello stesso paziente e
    # servizio è svolta in maniera non efficiente
    model.window_overlap = pyo.Var(model.window_overlap_index, domain=pyo.Binary)

    # Variabili che specificano se un paziente ha almeno una richiesta in un
    # certo giorno
    if 'minimize_hospital_accesses' in additional_info:
        model.pat_use_day = pyo.Var(model.pat_days_index, domain=pyo.Binary)
    
    # Componente giornaliera della funzione obiettivo
    if 'use_optimality_constraints' in additional_info:
        model.objective_function_day_component = pyo.Var(model.days, domain=pyo.NonNegativeIntegers)

    # VINCOLI ##################################################################

    # Se una finestra è soddisfatta, è soddisfatta in un unico giorno interno
    # alla sua finestra
    @model.Constraint(model.window_index)
    def link_window_to_do_variables(model, p, s, ws, we):
        return model.window[p, s, ws, we] == pyo.quicksum([model.do[pp, ss, d, c, o] for pp, ss, d, c, o in model.do_index if p == pp and s == ss and d >= ws and d <= we])

    # La durata totale dei servizi programmati per ogni operatore non può
    # superare la sua durata
    @model.Constraint(model.operators)
    def respect_operator_duration(model, d, c, o):
        
        tuples_affected = [(p, s) for p, s, dd, cc, oo in model.do_index if d == dd and c == cc and o == oo]
        operator_duration = instance['days'][str(d)][c][o]['duration']
        
        if len(tuples_affected) == 0:
            return pyo.Constraint.Skip
        if sum(instance['services'][s]['duration'] for _, s in tuples_affected) <= operator_duration:
            return pyo.Constraint.Skip

        return pyo.quicksum(model.do[p, s, d, c, o] * instance['services'][s]['duration'] for p, s in tuples_affected) <= operator_duration

    # Vincolo che lega le variabili 'window_overlap' alle variabili 'do'
    @model.Constraint(model.window_overlap_index)
    def window_overlap_constraint(model, p, s, ws, we, wws, wwe):
        
        min_ws = min(ws, wws)
        max_we = max(we, wwe)
        
        tuples_affected = [(d, c, o) for d in range(min_ws, max_we + 1) for pp, ss, dd, c, o in model.do_index if p == pp and s == ss and d == dd]
        
        return pyo.quicksum(model.do[p, s, d, c, o] for d, c, o in tuples_affected) <= 1 + model.window_overlap[p, s, ws, we, wws, wwe]

    # Non è possibile inserire richieste dello stesso paziente la cui durata
    # totale eccede gli slot temporali di quel giorno
    @model.Constraint(model.pat_days_index)
    def patient_total_duration(model, p, d):
        
        tuples_affected = [(s, c, o) for pp, s, dd, c, o in model.do_index if pp == p and dd == d]
        
        if sum(instance['services'][s]['duration'] for s, c, o in tuples_affected) <= model.max_time[d]:
            return pyo.Constraint.Skip
        
        return pyo.quicksum([model.do[p, s, d, c, o] * instance['services'][s]['duration'] for s, c, o in tuples_affected]) <= model.max_time[d]

    # Vincolo che forza 'pat_use_day' ad 1 se è presente almeno una richiesta
    # del paziente in quel giorno
    if 'minimize_hospital_accesses' in additional_info:
        @model.Constraint(model.do_index)
        def if_patient_uses_day(model, p, s, d, c, o):
            return model.do[p, s, d, c, o] <= model.pat_use_day[p, d]

    # Vincoli che eliminano le possibili programmazioni che non sono inseribili
    # negli operatori senza avere qualche servizio a metà fra due
    if 'use_bin_packing' in additional_info:
        add_bin_packing_cuts_to_master_model(model, instance)

    # Vincoli di ottimalità
    if 'use_optimality_constraints' in additional_info:
        @model.Constraint(model.days)
        def link_objective_component(model, d):
            
            tuples_affected = [(p, s, c, o) for p, s, dd, c, o in model.do_index if d == dd]
            
            if len(tuples_affected) == 0:
                return model.objective_function_day_component[d] == 0
            
            return pyo.quicksum(model.do[p, s, d, c, o] * instance['services'][s]['duration'] * instance['patients'][p]['priority'] for p, s, c, o in tuples_affected) == model.objective_function_day_component[d]
    
        model.objective_value_constraints = pyo.ConstraintList()

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


def get_results_from_fat_master_model(model):
    '''Funzione che ritorna i risultati (inseriti e rigettati) contenuti nel
    modello master risolto.'''

    # Oggetto indicizzato per giorno contenente la lista di tuple (p, s, c, o)
    scheduled_requests_grouped_per_day = {}
    for p, s, d, c, o in model.do_index:
        if pyo.value(model.do[p, s, d, c, o]) < 0.01:
            continue
        day_name = str(d)
        if day_name not in scheduled_requests_grouped_per_day:
            scheduled_requests_grouped_per_day[day_name] = []
        scheduled_requests_grouped_per_day[day_name].append({
            'patient': p,
            'service': s,
            'care_unit': c,
            'operator': o
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
        daily_results.sort(key=lambda v: (v['patient'], v['service'], v['care_unit'], v['operator']))
    rejected_requests.sort(key=lambda v: (v['patient'], v['service']))

    return {
        'scheduled': scheduled_requests_grouped_per_day,
        'rejected': rejected_requests
    }