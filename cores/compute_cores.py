import pyomo.environ as pyo


def compute_dumb_cores(all_subproblem_results):
    """Questa funzione calcola la lista dei core generati a partire da ciascun
    giorno contenente qualcosa di non schedulato. Tutte le richieste di quel
    giorno vengono aggiunte al core senza distinzione di schedulazione."""
    
    cores = []
    
    for day_name, subproblem_results in all_subproblem_results.items():
        
        # Non considerare giorni in cui è stato schedulato tutto.
        if len(subproblem_results['rejected']) == 0:
            continue

        components = []

        # Aggiunta di tutte le richieste schedulate
        for scheduled_request in subproblem_results['scheduled']:
            components.append({
                'patient': scheduled_request['patient'],
                'service': scheduled_request['service']
            })

        # Aggiunta di tutte le richieste non schedulate
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
    """Questa funzione calcola la lista dei core generati a partire da ciascuna
    singola richiesta non schedulata. Ciascun core basico conterrà una singola
    richiesta non schedulata e tutte quelle schedulate in quel giorno."""
    
    cores = []
    
    for day_name, subproblem_results in all_subproblem_results.items():
        
        # Non considerare giorni in cui è stato schedulato tutto.
        if len(subproblem_results['rejected']) == 0:
            continue

        # Lista con tutte le richieste schedulate.
        scheduled_components = []
        for scheduled_request in subproblem_results['scheduled']:
            scheduled_components.append({
                'patient': scheduled_request['patient'],
                'service': scheduled_request['service']
            })

        # Per ogni richiesta non schedulata in questo giorno, crea un nuovo core
        # copiando le richieste schedulate e aggiungendo quest'ultima.
        for rejected_request in subproblem_results['rejected']:
            
            core_components = scheduled_components.copy()
            core_components.append({
                'patient': rejected_request['patient'],
                'service': rejected_request['service']
            })
            
            cores.append({
                'components': core_components,
                'days': [str(day_name)]
            })

    return cores


def compute_reduced_cores(all_subproblem_results, master_instance):
    """Questa funzione calcola la lista dei core generati a partire da ciascuna
    singola richiesta non schedulata. Ciascun core ridotto conterrà una singola
    richiesta non schedulata e tutte quelle schedulate che hanno il paziente o
    l'unità di cura in comune. Si aggiungono pazienti e unità di cura ogni volta
    che qualcosa di nuovo viene inserito fra le componenti fino a che si ottiene
    un sottoinsieme chiuso in questo senso."""
    
    cores = []

    for day_name, day_results in all_subproblem_results.items():
        
        # Non considerare giorni in cui è stato schedulato tutto.
        if len(day_results['rejected']) == 0:
            continue

        # Generazione di un core per ogni singola richiesta non schedulata.
        for rejected_request in day_results['rejected']:

            rejected_patient_name = rejected_request['patient']
            rejected_service_name = rejected_request['service']
            rejected_service = master_instance['services'][rejected_service_name]
            rejected_care_unit_name = rejected_service['care_unit']

            # Componenti del nuovo core (lista di coppie paziente, servizio).
            core_components = [{
                'patient': rejected_patient_name,
                'service': rejected_service_name
            }]

            # Il processo di aggiunta delle componenti è analogo alla visita di
            # un grafo bipartito in cui a destra vi sono i pazienti e a sinistra
            # le unità di cura. Ogni richiesta schedulata corrisponde ad un arco
            # (paziente, unità di cura del servizio). Si aggiunge l'arco
            # relativo alla singola richiesta non schedulata e si calcola la
            # componente connessa, aggiungendo alle componenti del core ogni
            # arco attraversato.

            # Insiemi utilizzati nella visita del grafo. Il punto di partenza è
            # quello con il singolo paziente ed unità di cura della richiesta
            # non schedulata.
            care_units_to_do = set([rejected_care_unit_name])
            patients_to_do = set([rejected_patient_name])
            care_units_done = set()
            patients_done = set()

            while len(care_units_to_do) > 0 or len(patients_to_do) > 0:

                # Aggiungi tutti i pazienti di una unità di cura toccata.
                while len(care_units_to_do) > 0:

                    current_care_unit = care_units_to_do.pop()

                    for scheduled_service in day_results['scheduled']:

                        patient_name = scheduled_service['patient']
                        service_name = scheduled_service['service']

                        if scheduled_service['care_unit'] == current_care_unit:
                            
                            core_components.append({
                                'patient': patient_name,
                                'service': service_name
                            })

                            # Se il paziente è nuovo, aggiungilo a quelli da visitare
                            if patient_name not in patients_done:
                                patients_to_do.add(patient_name)

                    # Questa unità di cura non verrà più visitata
                    care_units_done.add(current_care_unit)

                # Aggiungi tutte le unità di cura toccate da qualche paziente.
                while len(patients_to_do) > 0:

                    current_patient = patients_to_do.pop()

                    for scheduled_service in day_results['scheduled']:

                        patient_name = scheduled_service['patient']
                        service_name = scheduled_service['service']
                        care_unit_name = scheduled_service['care_unit']

                        if patient_name == current_patient:

                            core_components.append({
                                'patient': patient_name,
                                'service': service_name
                                })
                            
                            # Se è una nuova unità di cura aggiungila a quelle da visitare
                            if care_unit_name not in care_units_done:
                                care_units_to_do.add(care_unit_name)

                    # Questo paziente non verrà più visitato
                    patients_done.add(current_patient)

            # Al termine della visita vengono rimossi eventuali duplicati dalle
            # componenti appena calcolate. Questa fase non è strettamente
            # necessaria se la visita è corretta, ma si possono catturare
            # eventuali bug del codice.
            unique_core_components = []
            for core_component in core_components:
                is_new_component = True
                for unique_core_component in unique_core_components:
                    if (unique_core_component['patient'] == core_component['patient'] and
                        unique_core_component['service'] == core_component['service']):
                        is_new_component = False
                        break
                if is_new_component:
                    unique_core_components.append(core_component)
            core_components = unique_core_components

            # Si aggiunge il core così calcolato, valido nel giorno corrente.
            cores.append({
                'components': sorted(core_components, key=lambda c: (c['patient'], c['service'])),
                'days': [day_name]
            })

    return cores


def aggregate_and_remove_duplicate_cores(new_cores, prev_cores):
    """Questa funzione si occupa della rimozione dalla lista dei nuovi core
    generati da una iterazione quando questi hanno le medesime componenti di un
    qualche core delle iterazioni passate. Se un nuovo core trova una di queste
    corrispondenze, gli eventuali nuovi giorni in cui è valido vengono aggiunti
    a quelli del core già valido. La funzione ritorna una coppia con (1) la
    lista dei nuovi core senza duplicati e (2) la lista dei core complessivi."""

    # Ogni core presente in 'new_cores' ma non in 'prev_cores' sarà aggiunto in questa lista.
    # Per essere considerati uguali i core devono possedere le stesse esatte componenti ground.
    unique_new_cores = []

    for new_core in new_cores:
        
        prev_found_core = None
        for prev_core in prev_cores:

            # Check di ottimizzazione (se i core hanno un diverso numero di componenti saranno sicuramente diversi).
            if len(new_core['components']) != len(prev_core['components']):
                continue
            
            are_components_exactly_the_same = True
            for new_core_component in new_core['components']:
                
                is_component_present_in_prev = False
                for prev_core_component in prev_core['components']:
                    if (new_core_component['patient'] == prev_core_component['patient'] and
                        new_core_component['service'] == prev_core_component['service']):
                        is_component_present_in_prev = True
                        break
                
                if not is_component_present_in_prev:
                    are_components_exactly_the_same = False
                    break
            
            # Se si trova un core con le stesse esatte componenti (a meno di un diverso ordine),
            # questo viene salvato e la ricerca termina.
            if are_components_exactly_the_same:
                prev_found_core = prev_core
                break

        # Se la ricerca non ha trovato nessun core con uguali componenti, il core viene aggiunto alla lista dei nuovi.
        # Viene aggiornata anche la lista complessiva dei core validi.
        if prev_found_core is None:
            unique_new_cores.append(new_core)
            prev_cores.append(new_core)
            continue

        # Se il core è già presente bisogna aggiungere (solo) gli eventuali nuovi giorni in cui è valido.
        days_not_in_prev_core = []
        for day_name in new_core['days']:
            if day_name not in prev_found_core['days']:
                days_not_in_prev_core.append(day_name)
        prev_found_core['days'].extend(days_not_in_prev_core)
        
        # Se il nuovo core non è valido in nessun nuovo giorno, non è necessario
        # aggiungerlo alla lista dei nuovi core in quanto non aggiunge
        # informazioni utili al taglio.
        if len(days_not_in_prev_core) == 0:
            continue
        
        # Risulta inutile aggiungere tagli nei giorni in cui è già valido il
        # core a lui identico quindi questi ultimi vengono tolti dal nuovo core.
        new_core['days'] = days_not_in_prev_core
        unique_new_cores.append(new_core)

    return unique_new_cores, prev_cores


def add_cores_constraint_class_to_master_model(master_model):
    """Funzione che crea la classe di vincoli nel modello MILP del master."""
    
    master_model.cores = pyo.ConstraintList()


def add_cores_constraints_to_master_model(master_model, cores):
    """Per ogni core nella lista fornita viene creato ed insterito nel modello
    un nuovo vincolo che vieta la comparsa delle sue componenti nei giorni
    specificati.

    Il vincolo ha la forma: sum( do[p,s,d] ) < |core|
    
    dove |core| è il numero di componenti del core e do[p,s,d] sono le variabili
    realtive alla schedulazione delle componenti. Il vincolo viene ripetuto ed
    inserito per ogni giorno 'd' in cui il core è valido."""

    for core in cores:

        # Se il core per qualche motivo non ha componenti si passa oltre.
        if len(core['components']) == 0:
            continue

        for day_name in core['days']:

            core_size = len(core['components'])
            expression = 0

            # Variabile che specifica se nel giorno corrente esiste
            # effettivamente l'elenco di richieste specificate dalla componenti
            # del core. Questo controllo è ridondante ma può essere utile per
            # catturare eventiali bug del codice.
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