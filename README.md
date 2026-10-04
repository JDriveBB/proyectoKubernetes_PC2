# Proyecto Kubernetes 202630 — Jobs parametrizados desde línea de comandos

Proyecto **grupal**: se trabaja en los grupos que se han venido usando durante el curso y
se entrega antes de la clase de la semana 12 (ver [Entrega](#entrega)).

Ya han trabajado con manifiestos `Job` de Kubernetes. En este proyecto el grupo usará esa
misma idea desde una herramienta de línea de comandos escrita en Python: en vez de editar
un YAML para cada ejecución, el programa presenta un menú donde el usuario elige el
lenguaje, la tarea y la complejidad, y crea el `Job` usando el cliente oficial de
Kubernetes. El mismo menú permite revisar el estado de las tareas lanzadas y ver sus
logs.

Kubernetes crea entonces un Pod y ejecuta el contenedor elegido con los argumentos
suministrados. El recorrido completo que el grupo debe entender —y saber defender— es:

```text
gestor_jobs.py -> Job de Kubernetes -> Pod -> contenedor con argumentos -> logs
```

No se incluye interfaz web, múltiples nodos, RBAC propio ni selección manual de nodos.
Esas capas quedan para la versión completa.

## Qué se entrega y qué construye el grupo

Se entrega como infraestructura, ya funcional:

- `imagenes/`: tres imágenes (Python, Java y C). Las tres implementan el mismo conjunto de
  tareas y el mismo contrato: reciben `<tarea> <N>` como argumentos, escriben logs en
  stdout y cierran con un JSON de una línea.
- `catalogo/tareas.json`: catálogo modificable de lenguajes, imágenes y tareas admitidas.
- `k8s/00-namespace.yaml`: namespace dedicado para los Jobs.
- `scripts/preparar-imagenes.ps1`: construye las imágenes y las carga en Minikube.

Construye el grupo, sobre el esqueleto de `entrega/`:

- `entrega/gestor_jobs.py`, un programa de menú con cinco capacidades:
  1. selección de lenguaje, tarea y complejidad;
  2. creación del `Job` mediante el cliente Python de Kubernetes;
  3. revisión del estado de las tareas lanzadas;
  4. consulta de los logs de una tarea;
  5. limpieza de las tareas ya terminadas, para dejar el namespace en orden.

- Una tarea adicional, en el lenguaje que el grupo prefiera. Implica ajustar el programa
  del contenedor que corresponda, reconstruir y cargar la imagen, añadir la tarea en
  `catalogo/tareas.json` y su fila en la tabla `TAMANOS` del gestor.

### Las tareas que traen los contenedores

| tarea | qué hace | parámetro N |
|---|---|---|
| `hola` | saluda e imprime datos del entorno de ejecución | no usa N |
| `ordenar` | genera N enteros aleatorios y los ordena, verificando el resultado | cantidad de elementos |
| `fib` | calcula fib(N) recursivamente, sin memoización: satura una CPU | N |
| `matriz` | multiplica dos matrices densas de N×N con triple bucle | dimensión |

Las cuatro están implementadas en los tres lenguajes, así que la misma tarea puede
compararse entre Python, Java y C. La tarea `hola` es la más reveladora en esa
comparación: el arranque de la JVM se nota frente a Python y a un binario de C.

### Qué significa la complejidad

La complejidad elegida (`baja`, `media`, `alta`) fija dos cosas a la vez, ambas en el
gestor:

- **los recursos** que el Job le pide a Kubernetes: `requests` y `limits` de CPU y
  memoria, en la tabla `NIVELES`;
- **el tamaño del trabajo**, el valor de N que recibe la tarea, en la tabla `TAMANOS`.

Por eso un nivel alto no sólo tarda más: también reserva más CPU y permite más memoria.
Bajar el `mem_limit` por debajo de lo que necesita la tarea es la forma de provocar un
`OOMKilled` y verlo reflejado en el estado del Job.

El esqueleto ya trae la estructura del programa y el andamiaje del cliente de Kubernetes
armado: el bucle del menú, los listados numerados, la carga del catálogo, el objeto `Job`
con sus clases anidadas y la búsqueda del Pod por etiqueta. Lo pendiente está marcado con `TODO` y con `...` en los
campos a completar, de modo que el trabajo sea entender el `Job` y no pelear con Python.

No está permitido resolver el proyecto invocando `kubectl` desde Python: el `Job` debe
crearse con el cliente `kubernetes`.

Como la entrega se defiende en grupo, todos los integrantes deben poder explicar el
código y el recorrido completo, sin importar quién escribió cada parte.

## Preparación

Ejecuten los siguientes comandos desde la carpeta raíz del proyecto:

```powershell
minikube start
kubectl apply -f .\k8s\00-namespace.yaml
.\scripts\preparar-imagenes.ps1
```

Instalen luego las dependencias de Python:

```powershell
pip install -r .\entrega\requirements.txt
```

Los nombres de imagen son deliberadamente locales (`kubernates-202630-*`) y no se publica
ninguna imagen durante el proyecto.

`preparar-imagenes.ps1` construye directamente contra el demonio Docker de Minikube, así
que **hay que volver a ejecutarlo cada vez que se cambie el programa de un contenedor**.
No usen `minikube image load` para actualizar una imagen: no reemplaza un tag que ya
existe, y el clúster seguiría ejecutando la versión anterior sin avisar.

## Ejecución

Una vez implementado el gestor, se ejecuta sin argumentos:

```powershell
python .\entrega\gestor_jobs.py
```

El menú ofrece:

```text
=== Gestor de Jobs - namespace estudiantes-202630 ===
  1. Ejecutar una tarea nueva
  2. Revisar el estado de las tareas
  3. Ver los logs de una tarea
  4. Limpiar las tareas terminadas
  5. Salir
```

La opción 1 pide lenguaje, tarea y complejidad en listas numeradas —el menú de
complejidad muestra el N y la memoria que implica cada nivel— y al terminar imprime el
nombre del Job creado con sus recursos. La opción 2 lista todas las tareas del namespace con su estado.
La opción 3 deja elegir una de esas tareas y muestra la salida de su contenedor. La
opción 4 borra las tareas ya terminadas —completadas o fallidas— tras pedir confirmación,
y deja intactas las que siguen corriendo.

Prueben las tres tareas incluidas variando la complejidad, y contrasten lo que muestra el
menú con lo que reporta el clúster:

```powershell
kubectl get jobs,pods -n estudiantes-202630
kubectl logs -n estudiantes-202630 job/<nombre-del-job>
```

## Entrega

El proyecto es grupal y se trabaja en los grupos que se han venido usando durante el
curso. La entrega vence **antes de la clase de la semana 12**.

1. Link al repositorio público entregado por la actividad del catálogo, antes de la clase
   de la semana 12.
2. En el README del repositorio se debe explicar la implementación.
3. En el README se debe agregar un link a un video de YouTube con el demo del proyecto.
4. El grupo completo debe estar disponible para defender la entrega.
