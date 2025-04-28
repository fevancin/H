1 {take(Pat1, Srv1, Pat2, Srv2): arc(_, _, Pat2, Srv2)} 1 :- arc(Pat1, Srv1, _, _).
:- take(Pat1, Srv1, Pat2, Srv2), not arc(Pat1, Srv1, Pat2, Srv2).
:- take(Pat1, Srv1, Pat, Srv), take(Pat2, Srv2, Pat, Srv), Pat1 != Pat2, Srv1 != Srv2.

#show take/4.