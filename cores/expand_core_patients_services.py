import subprocess
from pathlib import Path


def get_max_possible_master_requests(master_instance):
    '''Funzione che calcola tutte le richieste che potrebbero essere effettuate
    in ogni giorno. La funzione ritorna un dict[day, list[patient, service]].'''

    # Dizionario che indicizza sui giorni
    max_requests = {}

    # Cicli che per ogni paziente, protocollo e servizio richiesto popola
    # 'max_requests'.
    for patient_name, patient in master_instance['patients'].items():
        for service_name, windows in patient['requests'].items():
            for window in windows:
                for day_index in range(window[0], window[1] + 1):
                    if day_index not in max_requests:
                        max_requests[day_index] = set()
                    max_requests[day_index].add((patient_name, service_name))
    
    # Trasforma i set in dict
    max_requests = {str(day_index): list({'patient': r[0], 'service': r[1]} for r in requests) for day_index, requests in max_requests.items()}
    
    return max_requests


def remove_unfeasible_cores(master_instance, cores):
    '''Funzione che rimuove i core quando le loro componenti risultano
    complessivamente non ammissibili nei suoi giorni. La non ammissibilità è
    calcolata sommando le durate dei servizi presenti nelle componenti, divise
    per le rispettive unità di cura, e verificando che questi totali siano non
    superiori alla durata totale degli operatori di quella unità di cura. Questo
    controllo è necessario solo nel caso si anonimizzino i servizi e quindi
    siano possibili richieste con durata >=. La funzione ritorna la lista dei
    core ammissibili.'''

    # Dizionario che contiene, per ogni giorno e unità di cura, il totale delle
    # durate degli operatori presenti.
    max_capacities = {}
    for day_name, day in master_instance['days'].items():
        max_capacities[day_name] = {}
        for care_unit_name, care_unit in day.items():
            max_capacities[day_name][care_unit_name] = 0
            for operator in care_unit.values():
                max_capacities[day_name][care_unit_name] += operator['duration']
    
    # Lista dei soli core ritenuti ammissibili.
    feasible_cores = []

    for core in cores:
        
        # Giorni in cui il core è valido
        valid_days = []

        for day_name in core['days']:
            
            is_day_valid = True

            # Elenco delle durate totali dei servizi nelle componenti, divise
            # per unità di cura.
            core_capacities = {}
            
            for component in core['components']:
                
                service_name = component['service']
                service = master_instance['services'][service_name]
                service_duration = service['duration']
                care_unit_name = service['care_unit']

                if care_unit_name not in core_capacities:
                    core_capacities[care_unit_name] = 0
                core_capacities[care_unit_name] += service_duration

                # Se durante il calcolo si ottiene una durata maggiore della
                # capacità totale dell'unità di cura, il core non è ammissibile
                # nel giorno corrente.
                if core_capacities[care_unit_name] > max_capacities[day_name][care_unit_name]:
                    is_day_valid = False
                    break
            
            if is_day_valid:
                valid_days.append(day_name)
        
        # Il core è valido se ha almeno un giorno in cui è ammissibile
        if len(valid_days) > 0:
            feasible_cores.append({
                'components': core['components'],
                'days': valid_days
            })
    
    return feasible_cores


def expand_core_patients_services(cores, max_possible_master_requests, master_instance,
                                  expand_patients: bool, expand_services: bool, max_expansions_per_core: int):
    '''Funzione che ritorna la lista di core con nomi di pazienti e/o servizi
    anonimizzati.'''

    # Path utilizzati per i file di input/output di lavoro.
    asp_input_file_path = Path('asp_input.lp')
    asp_program_file_path = Path('cores/match.lp')
    asp_output_file_path = Path('asp_output.txt')

    # Lista contenente i core con nuovi nomi di pazienti e/o servizi.
    expanded_cores = []

    for core in cores:
        for day_name in core['days']:

            # Lista con le stringhe corrispondenti ai fatti da utilizzare come
            # input per il programma ASP che effettua i matching.
            asp_input = []

            for core_component in core['components']:

                core_patient_name = core_component['patient']
                core_service_name = core_component['service']
                
                for request in max_possible_master_requests[day_name]:

                    request_patient_name = request['patient']
                    request_service_name = request['service']

                    # Per ogni componente del core e per ogni possibile
                    # richiesta del master, guarda se è una possibile espansione
                    # valida.
                    is_valid_expansion = True
                    if not expand_patients and core_patient_name != request_patient_name:
                        is_valid_expansion = False
                    if not expand_services and core_service_name != request_service_name:
                        is_valid_expansion = False
                    
                    # Se si anonimizzano i nomi dei servizi è possibile
                    # aggiungere solo quelli della stessa unità di cura che
                    # hanno una durata maggiore o uguale a quella della
                    # componente del core.
                    if expand_services:
                        
                        core_service = master_instance['services'][core_service_name]
                        core_care_unit = core_service['care_unit']
                        core_duration = core_service['duration']
                        
                        request_service = master_instance['services'][request_service_name]
                        request_care_unit = request_service['care_unit']
                        request_duration = request_service['duration']
                        
                        if core_care_unit != request_care_unit or core_duration > request_duration:
                            is_valid_expansion = False

                    # Se l'anonimizzazione è valida aggiungi un arco al grafo.
                    if is_valid_expansion:
                        asp_input.append(f'arc({core_patient_name}, {core_service_name}, {request_patient_name}, {request_service_name}).\n')

            # Scrivi il file di input.
            with open(asp_input_file_path, 'w') as file:
                file.writelines(asp_input)
            
            # Esegui il programma ASP.
            with open(asp_output_file_path, 'w') as file:
                subprocess.run([
                    'clingo', '-n', str(max_expansions_per_core), '--verbose=0',
                    asp_input_file_path, asp_program_file_path],
                    stdout=file)
            
            # Leggi l'ouput con i matching.
            with open(asp_output_file_path, 'r') as file:
                lines = file.readlines()
            
            # Controllo dell'ultima riga dell'output per la non
            # soddisfacibilità: il core non ha espansioni valide in questo
            # giorno.
            if lines[-1] == 'UNSATISFIABLE':
                continue

            # Decodifica il file di output creando un nuovo core per ogni linea
            # dell'output (che quindi corrisponde ad una differente soluzione).
            # Ogni linea dell'output (a parte l'ultima) ha la forma:
            # take(p,s,p,s) take(p,s,p,s) take(p,s,p,s) take(p,s,p,s)\n
            for line in lines[:-1]:

                # Lista di 'p,s,p,s) ' e 'p,s,p,s)\n' per l'ultimo fatto.
                splitted_line = line.split('take(')[1:]
                
                expanded_components = []

                for token in splitted_line:

                    # Rimpozione dei caratteri di spaziatura.
                    token = token.removesuffix('\n')
                    token = token.removesuffix(' ')
                    token = token.removesuffix(')')

                    # Lista di 4 stringhe [pat1, srv1, pat2, srv2]
                    patient_service_names = token.split(',')

                    # La nuova componente riguarda solo i nomi dei vertici di
                    # destra del grafo bipartito.
                    expanded_components.append({
                        'patient': patient_service_names[2],
                        'service': patient_service_names[3]
                    })

                expanded_cores.append({
                    'components': expanded_components,
                    'days': day_name
                })
    
    # Elimina i file di lavoro.
    asp_input_file_path.unlink()
    asp_output_file_path.unlink()

    # Se si anonimizzano i nomi dei servizi potrebbero essere stati generati
    # nuovi core con durata totale per unità di cura non ammissibile; vengono
    # rimossi quelli non validi.
    if expand_services:
        expanded_cores = remove_unfeasible_cores(master_instance, expanded_cores)
    
    return expanded_cores