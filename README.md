# Proyecto Kubernetes 202630 - Gestor de Jobs

Este repositorio tiene un gestor de Jobs de Kubernetes que se usa desde la terminal. Está escrito en Python. En el menú se elige lenguaje, tarea y complejidad, y el programa crea el `Job` con el cliente oficial `kubernetes`. Desde el mismo menú se revisa el estado de las tareas, se leen sus logs y se borran las que ya terminaron.

## Integrantes

- Santy Baza
- Samuel Lambertino
- Juan Benavides

**Video demo:** [YouTube](TODO-enlace-al-video)

## Recorrido completo

```text
gestor_jobs.py -> Job de Kubernetes -> Pod -> contenedor con argumentos -> logs
```

1. **gestor_jobs.py.** El usuario elige lenguaje, tarea y complejidad. El gestor lee `catalogo/tareas.json` (lenguaje -> imagen y tareas), toma N de `TAMANOS` y los recursos de `NIVELES`, y arma `args = [<tarea>, <N>]`.
2. **Job.** `crear_job` construye un `V1Job` (`batch/v1`) en el namespace `estudiantes-202630` y lo envía al API server con `create_namespaced_job`. Python nunca llama a `kubectl`.
3. **Pod.** El controlador de Jobs crea un único Pod a partir de la plantilla y le pone la etiqueta `job-name=<nombre del Job>`. Nosotros no creamos Pods a mano.
4. **Contenedor con argumentos.** El Pod ejecuta el contenedor `tarea` con la imagen local del lenguaje (`imagePullPolicy: Never`). Los `args` siguen el contrato de entrada de las imágenes, `<tarea> <N>`.
5. **Logs.** El programa escribe en stdout y termina con una línea JSON. Esa salida queda en el Pod, así que el gestor busca el Pod por la etiqueta `job-name` y lee su log. Si el programa sale con código 0, el Job queda en `Complete`; con cualquier otro código, en `Failed`.

## Estructura del repositorio

```text
README.md                        este documento
entrega/
  gestor_jobs.py                 gestor con menú (programa principal)
  requirements.txt               dependencias de Python (cliente kubernetes)
catalogo/
  tareas.json                    lenguajes, imágenes y tareas admitidas
k8s/
  00-namespace.yaml              namespace estudiantes-202630
scripts/
  preparar-imagenes.ps1          construye las imágenes dentro del demonio Docker de Minikube
imagenes/
  python/  (Dockerfile, tareas.py)    imagen kubernates-202630-python:1.0
  java/    (Dockerfile, Tareas.java)  imagen kubernates-202630-java:1.0
  c/       (Dockerfile, tareas.c)     imagen kubernates-202630-c:1.0
```

## Preparación y ejecución

Desde la raíz del proyecto, en PowerShell:

```powershell
minikube start --driver=docker --container-runtime=docker
kubectl apply -f .\k8s\00-namespace.yaml
.\scripts\preparar-imagenes.ps1
pip install -r .\entrega\requirements.txt
```

Arrancamos Minikube con `--driver=docker --container-runtime=docker` por un problema concreto. `preparar-imagenes.ps1` llama a `minikube docker-env` para construir las imágenes en el demonio Docker de Minikube, y con el runtime por defecto (containerd) ese comando falla en Windows con el error `SSH_AGENT_START`. Con el runtime docker el script corre sin problema.

Si la ExecutionPolicy de PowerShell bloquea el script, se puede lanzar así:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\preparar-imagenes.ps1
```

Cada vez que se cambia el programa de un contenedor hay que volver a ejecutar el script. Ojo con `minikube image load`: no reemplaza un tag que ya existe, y el clúster seguiría corriendo la versión vieja sin avisar.

El gestor se ejecuta sin argumentos, también desde la raíz:

```powershell
python .\entrega\gestor_jobs.py
```

```text
=== Gestor de Jobs - namespace estudiantes-202630 ===
  1. Ejecutar una tarea nueva
  2. Revisar el estado de las tareas
  3. Ver los logs de una tarea
  4. Limpiar las tareas terminadas
  5. Salir
```

Para comparar lo que muestra el menú con lo que dice Kubernetes:

```powershell
kubectl get jobs,pods -n estudiantes-202630
kubectl logs -n estudiantes-202630 job/NOMBRE-COMPLETO-DEL-JOB
```

En el segundo comando, `NOMBRE-COMPLETO-DEL-JOB` se cambia por el nombre que aparece en `kubectl get jobs`, con el sufijo numérico incluido (por ejemplo `python-fib-alta-1791130590`).

## Implementación

### Selección (`seleccionar`)

Las listas se muestran con `elegir_opcion`, que numera las opciones y vuelve atrás con 0 o con una entrada vacía. Las tareas salen de `catalogo[lenguaje]["tasks"]` y la imagen de `catalogo[lenguaje]["image"]`. En el menú de complejidad cada nivel muestra su N y su memoria:

```python
etiquetas = [
    f"{nivel} (N={tamanos[nivel]}, memoria {NIVELES[nivel]['mem_limit']})"
    for nivel in NIVELES
]
...
argumentos = [tarea, str(tamanos[complejidad])]  # [tarea, N del nivel elegido].
recursos = NIVELES[complejidad]
```

`nombre_job` arma el nombre como `<lenguaje>-<tarea>-<complejidad>-<timestamp>`, en minúsculas, solo con `[a-z0-9-]` y con un máximo de 63 caracteres. Gracias al timestamp se puede repetir la misma tarea aunque el Job anterior siga en el namespace.

### Creación del Job (`crear_job`)

Cada línea del cliente Python equivale a un campo del YAML. El cliente usa snake_case y el YAML camelCase. En la tabla, `containers[0].*` es una abreviatura de `spec.template.spec.containers[0].*`.

| Código Python | Campo YAML | Para qué sirve |
|---|---|---|
| `api_version="batch/v1"`, `kind="Job"` | `apiVersion`, `kind` | tipo de recurso |
| `V1ObjectMeta(name=nombre, namespace=NAMESPACE)` | `metadata.name`, `metadata.namespace` | nombre y namespace |
| `backoff_limit=0` | `spec.backoffLimit` | cuántas veces reintenta el Job |
| `restart_policy="Never"` | `spec.template.spec.restartPolicy` | el kubelet no reinicia el contenedor |
| `name="tarea"` | `containers[0].name` | nombre del contenedor |
| `image=imagen` | `containers[0].image` | imagen del catálogo |
| `image_pull_policy="Never"` | `containers[0].imagePullPolicy` | usa solo la imagen local, no descarga |
| `args=argumentos` | `containers[0].args` | `[<tarea>, <N>]` |
| `V1ResourceRequirements(requests=..., limits=...)` | `resources.requests`, `resources.limits` | CPU y memoria |

```python
limites = client.V1ResourceRequirements(
    requests={"cpu": recursos["cpu_request"], "memory": recursos["mem_request"]},
    limits={"cpu": recursos["cpu_limit"], "memory": recursos["mem_limit"]},
)
```

- `requests` es lo que Kubernetes reserva al programar el Pod y `limits` es el tope. Si el contenedor pasa el límite de memoria, Kubernetes lo mata con `OOMKilled`. Si pasa el de CPU, lo frena (throttling).
- `backoffLimit: 0` junto con `restartPolicy: Never` hace que un fallo sea definitivo. El contenedor no se reinicia dentro del Pod y el Job tampoco crea un Pod nuevo, así que un error o un `OOMKilled` se ve como Job `Failed` y no queda escondido detrás de reintentos.
- Las imágenes viven en el demonio Docker de Minikube y no están publicadas en ningún registro. Con `imagePullPolicy: Never` Kubernetes usa la imagen local y nunca intenta descargarla. Si pusiéramos `Always`, intentaría bajarla de un registro donde no existe y el Pod fallaría con `ErrImagePull`/`ImagePullBackOff`.

### Estado (`describir_estado`, `listar_jobs`, `consultar_estado`)

Mientras Kubernetes no fija los contadores de `job.status`, valen `None`. Por eso cada uno lleva `or 0`. Se revisan en este orden:

```python
if activos > 0:
    return "en ejecucion"
if correctos > 0:
    return "completado"
if fallidos > 0:
    return "fallido"
return "pendiente (el Pod todavia no ha arrancado)"
```

`listar_jobs` llama a `list_namespaced_job` y devuelve `(nombre, estado)` por cada elemento de `.items`. Eso es lo que imprime la opción 2. `consultar_estado` lee un Job puntual con `read_namespaced_job_status`.

### Logs (`consultar_logs`)

Los logs se piden al Pod. Kubernetes marca cada Pod de un Job con la etiqueta `job-name=<nombre del Job>` y el gestor la usa para encontrarlo:

```python
pods = core.list_namespaced_pod(
    namespace=NAMESPACE,
    label_selector=f"job-name={nombre}",
)
pod = pods.items[0].metadata.name
respuesta = core.read_namespaced_pod_log(
    name=pod, namespace=NAMESPACE, _preload_content=False)
return respuesta.data.decode("utf-8", errors="replace")
```

El parámetro `_preload_content=False` hace falta. Sin él, el cliente `kubernetes` 36.x devuelve el `repr` de los bytes y el log sale como `b'...\n...'` en una sola línea. Con él llega la respuesta cruda y la decodificamos a texto. Si el Job todavía no tiene Pods, el gestor lo avisa en vez de fallar.

### Limpieza (`jobs_terminados`, `eliminar_job`)

Un Job cuenta como terminado si no tiene Pods activos y tiene al menos un Pod correcto o fallido. Los que están en ejecución o pendientes nunca entran en la lista.

```python
if (job.status.active or 0) == 0
and ((job.status.succeeded or 0) > 0 or (job.status.failed or 0) > 0)
```

La opción 4 muestra qué Jobs va a borrar y pide confirmación (`s`/`si`). El borrado se hace así:

```python
cliente_batch().delete_namespaced_job(
    name=nombre,
    namespace=NAMESPACE,
    body=client.V1DeleteOptions(propagation_policy="Background"),
)
```

Con `propagation_policy="Background"` Kubernetes borra también los Pods del Job. Si se quita, el Job desaparece pero su Pod se queda huérfano en el namespace, y se puede ver con `kubectl get pods -n estudiantes-202630`.

### Manejo de errores del menú

Cada acción corre dentro de un `try` y, si algo falla, el menú sigue abierto. En vez de la traza original, `explicar_error` imprime una frase con la causa probable y qué hacer:

| Situación | Mensaje |
|---|---|
| Minikube detenido (`minikube stop`) o sin kubeconfig | `No hay un cluster activo en kubeconfig.` y el comando para arrancarlo |
| Docker Desktop cerrado o el contenedor de Minikube parado | `No se pudo conectar con el cluster.` y que revise `minikube status` |
| Falta el namespace | `El namespace estudiantes-202630 no existe.` y el `kubectl apply` que lo crea |
| El Job o el Pod ya no existe | `Ya no existe en el cluster: ...` |
| Nombre de Job repetido | `Ya existe un Job con ese nombre.` |
| Logs de un contenedor que aún no arranca | `El contenedor todavia no ha arrancado: ...`; si el motivo es `ErrImageNeverPull`, indica ejecutar `preparar-imagenes.ps1` |
| Permisos, petición inválida o error interno del API server | el código HTTP y el mensaje que devuelve Kubernetes |
| Catálogo ausente o con JSON inválido | aviso al arrancar y el programa termina con código 1 |

Con el clúster apagado, el cliente reintentaba la conexión varias veces antes de fallar. `cargar_configuracion` desactiva esos reintentos para que el aviso aparezca enseguida. Además, la limpieza sigue con el resto de Jobs aunque alguno ya se haya borrado por otro lado, y si se cierra la entrada estándar el programa termina con `Interrumpido.` en vez de una traza.

## Complejidad

El nivel elegido define dos cosas a la vez: los recursos del contenedor (`NIVELES`) y el tamaño del trabajo, N (`TAMANOS`). Un nivel más alto pide más CPU y memoria y también manda un N más grande.

**NIVELES**

| nivel | cpu_request | cpu_limit | mem_request | mem_limit |
|---|---|---|---|---|
| baja | 100m | 500m | 64Mi | 128Mi |
| media | 250m | 1000m | 128Mi | 512Mi |
| alta | 500m | 2000m | 256Mi | 1Gi |

**TAMANOS (valor de N)**

| tarea | baja | media | alta |
|---|---|---|---|
| hola | 0 | 0 | 0 |
| ordenar | 100000 | 1000000 | 3000000 |
| fib | 25 | 30 | 35 |
| matriz | 60 | 120 | 250 |
| primos | 1000000 | 10000000 | 50000000 |

### Cómo provocar `OOMKilled`

Esto se hizo solo para probar. Cambiamos por un momento la fila `alta` de `NIVELES` a `mem_request: "32Mi"` y `mem_limit: "48Mi"` (el request no puede ser mayor que el límite) y lanzamos `primos` alta en Python. Con N=50000000 la criba es un `bytearray` de casi 48 MiB. Sumándole el intérprete y los bytes temporales que se crean al tachar múltiplos, el proceso se pasa del límite. El Job aparece como `fallido` en la opción 2 y como `Failed` en Kubernetes, y `kubectl describe pod -n estudiantes-202630 NOMBRE-DEL-POD` muestra `OOMKilled` con exit code 137. Después dejamos los valores como estaban (`256Mi` / `1Gi`).

## Tarea adicional: `primos`

`primos` aplica la criba de Eratóstenes hasta N. Cuenta los primos menores o iguales que N y devuelve el mayor. Usa un `bytearray` de N+1 bytes, así que la memoria sube con N. Antes de terminar comprueba por división de prueba que el mayor encontrado es primo de verdad. La última línea tiene esta forma: `{"tarea": "primos", "lenguaje": "python", "ms": ..., "n": ..., "primos": ..., "mayor": ...}`.

La hicimos en Python porque el enunciado deja escoger y ahí el cambio era el más pequeño: una función y una entrada en el diccionario `TAREAS` de `imagenes/python/tareas.py`. Además, esa imagen se reconstruye rápido.

Cambios que implicó:

- `imagenes/python/tareas.py`: función `primos` y entrada en `TAREAS`.
- `catalogo/tareas.json`: `"primos"` en la lista de tareas de `python`.
- `entrega/gestor_jobs.py`: fila `"primos"` en `TAMANOS`.
- Imagen `kubernates-202630-python:1.0` reconstruida con `preparar-imagenes.ps1`.

Para verificarla basta comparar el campo `primos` de la última línea del log con la cantidad conocida para cada N:

| nivel | N | primos esperados |
|---|---|---|
| baja | 1000000 | 78498 |
| media | 10000000 | 664579 |
| alta | 50000000 | 3001134 |

En el menú solo aparece para Python. El catálogo declara las tareas por lenguaje, el menú las lee de ahí y `primos` solo existe en la imagen de Python. Si se ofreciera en Java o en C, el Job fallaría.

## Pruebas realizadas

<!-- RESULTADOS-PRUEBAS -->

Probamos en Minikube con driver docker y runtime docker, Kubernetes v1.37.0, en el namespace `estudiantes-202630`. Antes reconstruimos las tres imágenes con `preparar-imagenes.ps1`.

| # | Prueba | Resultado | Evidencia |
|---|---|---|---|
| 1 | Creación de Job y Pod | Correcto | La opción 1 imprime `Job creado: python-primos-baja-1791130428`, la imagen `kubernates-202630-python:1.0`, los argumentos `['primos', '1000000']`, la CPU `100m - 500m` y la memoria `64Mi - 128Mi`. En el clúster, el YAML del Job tiene `backoffLimit: 0`, `restartPolicy: Never`, el contenedor `tarea` con `imagePullPolicy: Never` y los mismos requests/limits. `kubectl get jobs,pods` muestra el Job y su Pod. |
| 2 | Tareas base en Python, Java y C | Correcto | Los 12 Jobs de nivel baja (4 tareas × 3 lenguajes) terminan en `Complete 1/1`. `fib` y `matriz` en media y alta, en los tres lenguajes, también terminan en `Complete`. |
| 3 | Niveles de complejidad | Correcto | Con `fib` en Python: baja `["fib","25"]` 100m/500m y 64Mi/128Mi → 75025; media `["fib","30"]` 250m/1 CPU y 128Mi/512Mi → 832040; alta `["fib","35"]` 500m/2 CPU y 256Mi/1Gi → 9227465. `ordenar` alta en Python (N=3000000, límite 1Gi) termina en `Complete`, sin `OOMKilled`. |
| 4 | Estado del gestor = estado de Kubernetes | Correcto | La opción 2 y `kubectl get jobs` coinciden: `en ejecucion` ↔ `Running 0/1`, `completado` ↔ `Complete 1/1` y `fallido` ↔ `Failed 0/1` (el Job del OOM). |
| 5 | Logs | Correcto | La opción 3 sobre `python-primos-alta-1791130567` devuelve las mismas líneas que `kubectl logs -n estudiantes-202630 job/python-primos-alta-1791130567`, separadas y sin `b'...'`. |
| 6 | Comparación entre lenguajes | Correcto | Ver "Comparación entre Python, Java y C". |
| 7 | OOMKilled | Correcto | Con la fila `alta` de NIVELES bajada por un momento a `mem_request: 32Mi` y `mem_limit: 48Mi`, `primos` alta en Python sale `fallido` en la opción 2 y `Failed 0/1` en Kubernetes. El Pod termina con `reason: OOMKilled` y exit code 137. Luego se restauró el valor original. |
| 8 | Limpieza segura | Correcto | Había 28 Jobs completados, 1 fallido (el del OOM) y `python-fib-alta-1791130617` corriendo. La opción 4 lista 29 y deja fuera el que corre. Con `N` responde `Cancelado, no se elimino nada.` y con `s`, `29 tarea(s) eliminada(s).`. Al final queda solo el Job en ejecución con su Pod, sin Pods huérfanos. |
| 9 | Tarea adicional `primos` | Correcto | Baja, media y alta dan 78498 / 664579 / 3001134 primos (mayor primo 999983 / 9999991 / 49999991). En los menús de C y Java solo aparecen `hola`, `ordenar`, `fib` y `matriz`. |
| 10 | Robustez del menú | Correcto | En el menú principal, `9`, `abc` o una entrada vacía dan `Opcion no valida.`. En los submenús, un número fuera de rango da `Escribe un numero entre 0 y N.`, mientras que `0` o vacío vuelven atrás. `5` sale con `Hasta luego.`. |

### Comparación entre Python, Java y C

Medimos el tiempo de dos maneras, porque cada una deja fuera cosas distintas.

- **`ms` del JSON.** Lo calcula cada programa desde dentro, con el runtime ya cargado. Ahí no entran el arranque de la JVM, el del intérprete de Python ni la creación del Pod.
- **Vida del proceso.** Es `FinishedAt − StartedAt` del contenedor, leído con `docker inspect` en el demonio Docker de Minikube, con resolución de nanosegundos. Los campos `startedAt`/`finishedAt` de Kubernetes no sirven aquí porque solo llegan al segundo. Esta medida incluye el arranque del runtime, la tarea y una sobrecarga fija del runtime de contenedores. La sobrecarga se ve bien en C, donde un binario estático que solo imprime unas líneas vive unos 86 ms.

**`ms` del JSON** (una ejecución por celda):

| tarea | nivel | N | C | Java | Python |
|---|---|---|---|---|---|
| hola | baja | 0 | 0 | 95 | 0 |
| ordenar | baja | 100000 | 11 | 121 | 250 |
| fib | baja | 25 | 0 | 1 | 65 |
| matriz | baja | 60 | 0 | 39 | 11 |
| fib | media | 30 | 1 | 5 | 149 |
| matriz | media | 120 | 1 | 68 | 90 |
| fib | alta | 35 | 16 | 47 | 1678 |
| matriz | alta | 250 | 8 | 49 | 789 |

`primos` (solo Python) tardó 27 ms en baja, 105 ms en media y 712 ms en alta.

**Vida del proceso frente a `ms` del JSON** (otra tanda de ejecuciones; en ms):

| tarea (límite de CPU) | medida | C | Java | Python |
|---|---|---|---|---|
| hola baja (500m) | vida del proceso, mediana de 3 | 86,2 | 310,1 | 412,1 |
| hola baja (500m) | `ms` del JSON por ejecución | 0 / 0 / 0 | 97 / 95 / 50 | 0 / 0 / 0 |
| hola baja (500m) | arranque estimado | — | ≈ 127 | ≈ 326 |
| fib alta (2000m) | vida del proceso, 1 ejecución | 90,1 | 192,7 | 1969,6 |
| fib alta (2000m) | `ms` del JSON | 16 | 46 | 1697 |
| fib alta (2000m) | arranque estimado | — | ≈ 73 | ≈ 198 |

El arranque estimado sale de restar el `ms` a la vida del proceso y quitarle después la sobrecarga del contenedor que marca C en el mismo caso (86,2 ms en hola y 74,1 ms en fib alta). En hola se toma la mediana por ejecución. Son pocas repeticiones, así que hay que leerlo como una aproximación.

#### Qué muestran los datos

En cálculo, C gana o empata en todas las tareas. Java se le acerca cuando el JIT ya compiló el código caliente (fib alta: 47 ms contra 16 ms). Python, en cambio, es unas 100 veces más lento que C en recursión, con 1678 ms en fib alta. Hay una excepción en matriz baja, donde Python (11 ms) le gana a Java (39 ms) porque con N=60 la JVM todavía ejecuta el bucle sin compilar. Además, entre niveles cambian a la vez N y la CPU asignada (500m, 1000m, 2000m), y por eso los tiempos de un mismo lenguaje no crecen solo con N. En Java, matriz alta (49 ms) termina antes que media (68 ms).

Los ~95 ms de hola en Java no corresponden al arranque de la JVM, porque se miden ya dentro de `main`. Son la inicialización perezosa del runtime, es decir, la carga de clases, la primera concatenación de cadenas y `printf`.

El arranque de la JVM sí se nota frente al binario de C, con unos 127 ms de diferencia a 500m de CPU. Lo que no esperábamos es que Python arrancara más lento que Java: 412 ms de vida del proceso contra 310 ms en hola, y unos 326 ms de arranque estimado contra 127 ms. El enunciado sugiere lo contrario para Python, y la causa la pudimos medir:

- la imagen `python:3.12-alpine` no trae bytecode precompilado (0 archivos `.pyc` frente a 1097 `.py` en la biblioteca estándar);
- por eso cada contenedor nuevo compila desde el código fuente los módulos que importa `tareas.py`;
- con `python -X importtime` y `--cpus 0.5`, los imports de nivel superior suman unos 352 ms, casi todo `json` (246 ms, por su dependencia de `re`) y `random` (70 ms);
- con 2000m de CPU (fib alta) ese costo baja, y el arranque estimado de Python cae a unos 198 ms y el de Java a unos 73 ms.

Para tareas cortas, C sale mucho más barato, porque casi todo su tiempo es la sobrecarga del contenedor. En las largas el arranque pesa poco al lado del cálculo y manda la velocidad de ejecución, donde el orden es C, luego Java y, bastante más atrás, Python.

## Restricciones respetadas

- El Job se crea con el cliente oficial `kubernetes`; Python no invoca `kubectl` (ni `subprocess`/`os.system`).
- No hay interfaz web ni gráfica, solo el menú de terminal.
- Un solo nodo (Minikube).
- Sin RBAC propio.
- Sin selección manual de nodos (`nodeSelector`/`affinity`).
- Los Pods los crea únicamente el Job.
- Imágenes locales `kubernates-202630-*`, sin registro externo (`imagePullPolicy: Never`).
- El contrato de entrada de las tareas no cambió: `<tarea> <N>`, logs en stdout y última línea JSON.
