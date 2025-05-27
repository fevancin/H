% Programma che prende in input un grafo bipartito e calcola un matching in
% maniera tale che ogni vertice di sinistra scelga un compagno.
% 
% L'input deve specificare l'elenco di archi del grafo nella forma:
% arc(pat1, srv1, pat2, arv2).
% 
% L'output contiene il sottoinsieme di archi scelti nella forma:
% take(pat1, srv1, pat2, arv2).


% Scegli un solo arco per ogni vertice di sinistra.
1 {take(Pat1, Srv1, Pat2, Srv2): arc(_, _, Pat2, Srv2)} 1 :- arc(Pat1, Srv1, _, _).

% Non è possibile scegliere archi che non esistono.
:- take(Pat1, Srv1, Pat2, Srv2), not arc(Pat1, Srv1, Pat2, Srv2).

% Non è possibile che più vertici di sinistra scelgano lo stesso vertice di destra.
:- take(Pat1, Srv1, Pat, Srv), take(Pat2, Srv2, Pat, Srv), Pat1 != Pat2, Srv1 != Srv2.

#show take/4.