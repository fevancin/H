# Programmatore di richieste ospedaliere

Per generare istanze (master o sottoproblema):
```bash
python generator.py -c CONFIG -o OUTPUT_DIR
```

Per eseguire i test dei vari modelli con singola risoluzione senza iterazioni (istanze master o sottoproblema):
```bash
python run_single_pass_tests.py -c CONFIG -i INPUT_DIR -o OUTPUT_DIR
```

Per eseguire i test dei vari modelli con iterazioni (solo istanze master):
```bash
python run_iterative_tests.py -c CONFIG -i INPUT_DIR -o OUTPUT_DIR
```

Per eseguire le analisi sui risultati (risultati master o sottoproblema):
```bash
python analyzer.py -c CONFIG -r RESULTS_DIR -o OUTPUT_DIR
```

Degli esempi di file di configurazione si possono trovare nella cartella `configs`

## Comandi di esempio

```bash
# Generazione di istanze
python generator.py -c configs/generator_master.yaml -o ../master_instances
python generator.py -c configs/generator_subproblem.yaml -o ../subproblem_instances

# Esecuzione dei test
python run_single_pass_tests.py -c configs/single_pass_test.yaml -i ../master_instances -o ../master_single_pass_results
python run_single_pass_tests.py -c configs/single_pass_test.yaml -i ../subproblem_instances -o ../subproblem_single_pass_results

python run_iterative_tests.py -c configs/iterative_test.yaml -i ../master_instances -o ../master_iterative_results

# Analisi dei risultati
python analyzer.py -c configs/analysis.yaml -r ../master_single_pass_results -o ../master_single_pass_analysis
python analyzer.py -c configs/analysis.yaml -r ../subproblem_single_pass_results -o ../subproblem_single_pass_analysis

python analyzer.py -c configs/analysis.yaml -r ../master_iterative_results -o ../master_iterative_analysis
```