import pyomo.environ as pyo


def get_sol_perm_model(master_instance, prev_solution_matrix: dict[tuple[str, str], list[tuple[int, int]]]):
    '''Funzione che ritorna il modello MILP del problema master senza
    assegnazione dell'operatore.'''

    model = pyo.ConcreteModel()

    # INSIEMI ##################################################################
    
    # Insieme di giorni
    day_indexes = set()
    for day_name in master_instance['days'].keys():
        day_indexes.add(int(day_name))
    model.days = pyo.Set(initialize=sorted(day_indexes))

    # (day, iteration)
    do_index = set()

    for day_iter_list in prev_solution_matrix.values():
        do_index.update(day_iter_list)
    model.do_index = pyo.Set(initialize=sorted(do_index))

    # (patient, service, window_start, window_end)
    sat_index = set()

    # Ogni coppia (p, s) viene inserita assieme a tutte le finestre di p che
    # includono almeno un qualche giorno nella matrice
    for pat_srv, day_iters in prev_solution_matrix.items():
        
        patient_name = pat_srv[0]
        service_name = pat_srv[1]
        
        # Giorni in cui è presente almeno una soluzione nella matrice
        day_indexes = [day_index for day_index, _ in day_iters]
        
        # Aggiungi tutte le finestre del paziente che intersecano un qualche
        # giorno in cui è presente una soluzione nella matrice
        for window in master_instance['patients'][patient_name]['requests'][service_name]:
            for day_index in range(window[0], window[1] + 1):
                if day_index in day_indexes:
                    sat_index.add((patient_name, service_name, window[0], window[1]))

    model.sat_index = pyo.Set(initialize=sorted(sat_index))

    # VARIABILI ################################################################

    # Variabili decisionali che descrivono che iterazione è scelta per ogni
    # giorno
    model.do = pyo.Var(model.do_index, domain=pyo.Binary)
    
    # Variabili decisionali che codificano il soddisfacimento di una richiesta 
    model.sat = pyo.Var(model.sat_index, domain=pyo.Binary)

    # VINCOLI ##################################################################

    # Se una richesta è soddisfatta, è soddisfatta al minimo da un giorno nella
    # sua finestra in una qualche iterazione
    @model.Constraint(model.sat_index)
    def link_do_to_sat(model, p, s, ws, we):
        return pyo.quicksum(model.do[d, i] for d, i in prev_solution_matrix[p, s] if d >= ws and d <= we) >= model.sat[p, s, ws, we]

    # Vincolo che obbliga ogni giorno a scegliere solo un'iterazione
    @model.Constraint(model.days)
    def max_one_iteration_per_day(model, d):
        return pyo.quicksum(model.do[d, i] for dd, i in model.do_index if d == dd) == 1

    # FUNZIONE OBIETTIVO #######################################################

    # Massimizza il numero di richieste soddisfatte, pesate per la loro durata e
    # priorità del paziente
    @model.Objective(sense=pyo.maximize)
    def objective_function(model):
        return pyo.quicksum(model.sat[p, s, ws, we] * master_instance['patients'][p]['priority'] * master_instance['services'][s]['duration'] for p, s, ws, we in model.sat_index)

    return model


def get_results_from_sol_perm_model(model):
    '''Funzione che ritorna un elenco di iterazioni in cui trovare la
    combinazione di soluzioni dei sottoprobemi atta a coprire le richieste del
    master.'''

    # Oggetto che identifica le iterazioni di ogni giorno da considerare nei
    # risultati finali
    day_iterations: dict[str, int] = {}
    for d, i in model.do_index:
        if pyo.value(model.do[d, i]) < 0.01:
            continue
        day_iterations[str(d)] = i

    return day_iterations


def get_fixed_final_results(master_instance, all_subproblem_results):
    '''Funzione che elabora la soluzione finale aggregata e rimuove le eventuali
    richieste doppie all'interno della stessa finestra.'''

    satisfied_requests = set()
    rejected_requests = set()

    for patient_name, patient in master_instance['patients'].items():
        for service_name, windows in patient['requests'].items():
            for window in windows:

                is_request_satisfied = False
                
                # Cerca la prima occorrenza delle richieste soddisfatte
                for day_index in range(window[0], window[1] + 1):
                    for scheduled_request in all_subproblem_results[str(day_index)]['scheduled']:
                        if scheduled_request['patient'] == patient_name and scheduled_request['service'] == service_name:
                            satisfied_requests.add((patient_name, service_name, day_index, scheduled_request['care_unit'], scheduled_request['operator'], scheduled_request['time']))
                            is_request_satisfied = True
                            break
                
                # Se la richiesta non esiste nei risultati allora è rigettata
                if not is_request_satisfied:
                    rejected_requests.add((patient_name, service_name, window[0], window[1]))

    final_results = {
        'scheduled': {},
        'rejected': []
    }

    # Inserimento delle richieste schedulate
    for request in satisfied_requests:
        day_name = str(request[2])

        if day_name not in final_results['scheduled']:
            final_results['scheduled'][day_name] = []
        
        final_results['scheduled'][day_name].append({
            'patient': request[0],
            'service': request[1],
            'care_unit': request[3],
            'operator': request[4],
            'time': request[5]
        })
    final_results['scheduled'] = dict(sorted((d, s) for d, s in final_results['scheduled'].items()))
    for satisfied_requests in final_results['scheduled'].values():
        satisfied_requests.sort(key=lambda t: (t['patient'], t['service'], t['care_unit'], t['operator'], t['time']))

    # Inserimento delle finestre rifiutate
    for request in rejected_requests:
        final_results['rejected'].append({
            'patient': request[0],
            'service': request[1],
            'window': [request[2], request[3]]
        })
    final_results['rejected'].sort(key=lambda t: (t['patient'], t['service'], t['window'][0], t['window'][1]))
    
    return final_results