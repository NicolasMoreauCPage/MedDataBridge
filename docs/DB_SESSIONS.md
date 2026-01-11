DB sessions: bonne pratique d'utilisation
========================================

But: éviter d'appeler directement la dépendance FastAPI `get_session()`
avec `next(get_session())` ou en conservant le générateur et en appelant
manuellement `next()` dessus. Cette pratique laisse le générateur ouvert
et peut empêcher la fermeture propre de la `Session`, provoquant des erreurs
SQLAlchemy/DBAPI (ex. rollback sur transaction inexistante) qui remontent
dans l'ASGI finalizer et génèrent des 500 intermittents.

Recommandations:

- Pour les handlers FastAPI (routes) : utiliser `Depends(get_session)`.

  Exemple :

  ```py
  from fastapi import Depends
  from app.db import get_session

  @router.get("/items")
  def list_items(session: Session = Depends(get_session)):
      return session.exec(select(Item)).all()
  ```

- Pour le code hors-contexte FastAPI (scripts, CLI, tâches background) :
  utiliser `session_factory()` en contexte `with` pour garantir ouverture/fermeture.

  Exemple :

  ```py
  from app.db import session_factory

  def run_cleanup():
      with session_factory() as session:
          # travail transactionnel
          session.add(MyObject(...))
          session.commit()
  ```

- Pour des usages temporaires/tests unitaires, si vous avez besoin d'un
  contexte géré similaire à Depends, vous pouvez utiliser le générateur
  `get_session()` via `yield from` (ex: fixtures pytest) mais veillez à
  consommer correctement le générateur pour fermer la session.

Raison technique succincte:
- FastAPI attend que les dépendances générateur (yield) soient correctement
  finalisées pour exécuter la logique de cleanup. Appeler `next(get_session())`
  crée la session mais ne déclenche pas la fermeture si le générateur n'est
  pas fermé/résilié (par ex. par `close()`), provoquant des rollbacks/erreurs
  lors de la tentative de `session.close()` plus tard. `session_factory()`
  renvoie un `Session` non-géré que vous pouvez fermer explicitement ou
  utiliser avec `with` (conseillé).

Si vous voulez, je peux :
- appliquer automatiquement un remplacement dans les tests (p.ex. substituer
  `session = next(get_session())` par `with session_factory() as session:`),
  ou
- simplement laisser les tests tels quels (ils peuvent utiliser des
  fixtures contrôlées par le runner de tests). Indiquez votre préférence.
