# Proyecto Kubernetes 202630 - Gestor de Jobs

Gestor de Jobs de Kubernetes por línea de comandos, escrito en Python. El menú permite elegir lenguaje, tarea y complejidad, crea el `Job` con el cliente oficial `kubernetes`, y permite revisar su estado, ver sus logs y limpiar los Jobs terminados.

## Integrantes

- Santy Baza
- Samuel Lambertino
- Juan Benavides 

**Video demo:** [YouTube](TODO-enlace-al-video)

## Recorrido completo

```text
gestor_jobs.py -> Job de Kubernetes -> Pod -> contenedor con argumentos -> logs
```

1. **gestor_jobs.py.** El usuario elige lenguaje, tarea y complejidad en el menú. El gestor lee `catalogo/tareas.json` (lenguaje -> imagen y tareas), busca N en `TAMANOS` y los recursos en `NIVELES`, y arma `args = [<tarea>, <N>]`.
2. **Job.** `crear_job` construye un objeto `V1Job` (`batch/v1`) en el namespace `estudiantes-202630` y lo envía al API server con `create_namespaced_job`. No se usa `kubectl` desde Python.
3. **Pod.** El controlador de Jobs de Kubernetes crea un único Pod a partir de la plantilla del Job y lo etiqueta con `job-name=<nombre del Job>`. El Pod no se crea a mano.
4. **Contenedor con argumentos.** El Pod ejecuta el contenedor `tarea` con la imagen local del lenguaje (`imagePullPolicy: Never`). Los `args` son el contrato de entrada del programa de la imagen: `<tarea> <N>`.
5. **Logs.** El programa escribe en stdout y su última línea es un JSON de una línea. Los logs pertenecen al Pod, no al Job: el gestor busca el Pod por la etiqueta `job-name` y lee su log. Exit code 0 deja el Job en `Complete`; distinto de 0, en `Failed`.

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

**Por qué `--driver=docker --container-runtime=docker`.** `preparar-imagenes.ps1` ejecuta `minikube docker-env` para construir las imágenes contra el demonio Docker de Minikube. Con el runtime por defecto (containerd), `docker-env` falla en Windows (error `SSH_AGENT_START`) y el script se interrumpe. Con el runtime docker funciona.

Si la ExecutionPolicy bloquea el script:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\preparar-imagenes.ps1
```

Hay que volver a ejecutar el script cada vez que se cambie el programa de un contenedor. **No usar `minikube image load`**: no reemplaza un tag que ya existe y el clúster seguiría ejecutando la versión anterior sin avisar.

Ejecución del gestor (sin argumentos, desde la raíz):

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

Contraste con Kubernetes:

```powershell
kubectl get jobs,pods -n estudiantes-202630
kubectl logs -n estudiantes-202630 job/NOMBRE-COMPLETO-DEL-JOB
```

En el segundo comando hay que reemplazar `NOMBRE-COMPLETO-DEL-JOB` por el nombre completo del Job tal como lo lista `kubectl get jobs` (incluye el sufijo numérico, por ejemplo `python-fib-alta-1791130590`).

## Implementación

### Selección (`seleccionar`)

Usa `elegir_opcion` (lista numerada; vacío o 0 vuelve atrás). Las tareas salen de `catalogo[lenguaje]["tasks"]`, la imagen de `catalogo[lenguaje]["image"]`. El menú de complejidad muestra N y memoria de cada nivel:

```python
etiquetas = [
    f"{nivel} (N={tamanos[nivel]}, memoria {NIVELES[nivel]['mem_limit']})"
    for nivel in NIVELES
]
...
argumentos = [tarea, str(tamanos[complejidad])]  # [tarea, N del nivel elegido].
recursos = NIVELES[complejidad]
```

`nombre_job` genera `<lenguaje>-<tarea>-<complejidad>-<timestamp>` en minúsculas y solo con `[a-z0-9-]` (máximo 63 caracteres). El timestamp permite repetir la misma tarea sin chocar con un Job anterior.

### Creación del Job (`crear_job`)

Cada línea del cliente Python corresponde a un campo del YAML equivalente (el cliente usa snake_case, el YAML camelCase). En la tabla, `containers[0].*` abrevia `spec.template.spec.containers[0].*`:

| Código Python | Campo YAML | Para qué sirve |
|---|---|---|
| `api_version="batch/v1"`, `kind="Job"` | `apiVersion`, `kind` | tipo de recurso |
| `V1ObjectMeta(name=nombre, namespace=NAMESPACE)` | `metadata.name`, `metadata.namespace` | identidad y namespace |
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

- **requests vs limits.** `requests` es lo que Kubernetes reserva para programar el Pod. `limits` es el tope: si el contenedor supera el límite de memoria, es matado con `OOMKilled`; si supera el de CPU, se le frena (throttling).
- **`backoffLimit: 0` + `restartPolicy: Never`.** Juntos hacen que un fallo sea definitivo: el contenedor no se reinicia dentro del Pod y el Job no crea un Pod de reemplazo. Así un error u `OOMKilled` queda visible como Job `Failed` en lugar de reintentarse en silencio.
- **`imagePullPolicy: Never`.** Las imágenes son locales (dentro del demonio Docker de Minikube) y no se publican en ningún registro. `Never` garantiza que se use la imagen local y que nunca se intente descargarla. Con `Always`, Kubernetes intentaría descargarla de un registro donde no existe y el Pod fallaría con `ErrImagePull`/`ImagePullBackOff`.

### Estado (`describir_estado`, `listar_jobs`, `consultar_estado`)

Los contadores de `job.status` valen `None` hasta que Kubernetes los fija, de ahí el `or 0`. Orden de prioridad:

```python
if activos > 0:
    return "en ejecucion"
if correctos > 0:
    return "completado"
if fallidos > 0:
    return "fallido"
return "pendiente (el Pod todavia no ha arrancado)"
```

`listar_jobs` usa `list_namespaced_job` y devuelve `(nombre, estado)` para cada elemento de `.items` (es lo que muestra la opción 2). `consultar_estado` lee un Job concreto con `read_namespaced_job_status`.

### Logs (`consultar_logs`)

Los logs son del Pod. Kubernetes etiqueta cada Pod de un Job con `job-name=<nombre del Job>`:

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

Sin `_preload_content=False`, el cliente `kubernetes` 36.x devuelve el `repr` de los bytes y los logs se imprimen como `b'...\n...'` en una sola línea. Con esa opción se obtiene la respuesta sin procesar y se decodifica a texto. Si el Job aún no tiene Pods, se informa en lugar de fallar.

### Limpieza (`jobs_terminados`, `eliminar_job`)

Criterio de "terminado": sin Pods activos y con al menos un Pod correcto o fallido. Un Job en ejecución o pendiente nunca entra en la lista.

```python
if (job.status.active or 0) == 0
and ((job.status.succeeded or 0) > 0 or (job.status.failed or 0) > 0)
```

La opción 4 muestra los Jobs a eliminar y pide confirmación (`s`/`si`) antes de borrar. El borrado usa:

```python
cliente_batch().delete_namespaced_job(
    name=nombre,
    namespace=NAMESPACE,
    body=client.V1DeleteOptions(propagation_policy="Background"),
)
```

`propagation_policy="Background"` hace que Kubernetes borre también los Pods del Job. Sin esa opción, el Job desaparece pero su Pod queda huérfano en el namespace (se ve con `kubectl get pods -n estudiantes-202630`).

### Manejo de errores del menú

Las acciones se ejecutan dentro de `try`: un `ApiException` (nombre repetido, namespace inexistente...) imprime `Error de Kubernetes (<status>): <reason>` y cualquier otra excepción imprime `Error: ...`, sin cerrar el menú.

## Complejidad

La complejidad fija a la vez los recursos (`NIVELES`) y el tamaño del trabajo N (`TAMANOS`). Mayor nivel significa más trabajo y más recursos.

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

**Cómo provocar `OOMKilled`.** Solo para pruebas. En las pruebas se cambió temporalmente la fila `alta` de `NIVELES` a `mem_request: "32Mi"` y `mem_limit: "48Mi"` (el request debe ser menor o igual que el límite) y se lanzó `primos` alta en Python. Con N=50000000, la criba es un `bytearray` de casi 48 MiB; sumando el intérprete y los bytes temporales que se crean al tachar múltiplos, el proceso supera el límite. El Job queda `fallido` en la opción 2 y `Failed` en Kubernetes, y `kubectl describe pod -n estudiantes-202630 NOMBRE-DEL-POD` muestra `OOMKilled` con exit code 137. Después se restauraron los valores originales (`256Mi` / `1Gi`).

## Tarea adicional: `primos`

**Qué hace.** Criba de Eratóstenes hasta N: cuenta los primos menores o iguales que N y devuelve el mayor. Usa un `bytearray` de N+1 bytes, de modo que la memoria crece con N. Verifica el resultado comprobando por división de prueba que el mayor primo encontrado es primo. Salida final, por ejemplo: `{"tarea": "primos", "lenguaje": "python", "ms": ..., "n": ..., "primos": ..., "mayor": ...}`.

**Por qué Python.** El enunciado deja elegir el lenguaje. En Python el cambio es mínimo (una función y una entrada en el diccionario `TAREAS` de `imagenes/python/tareas.py`) y la imagen es ligera de reconstruir.

**Archivos tocados.**

- `imagenes/python/tareas.py`: función `primos` y entrada en `TAREAS`.
- `catalogo/tareas.json`: `"primos"` en la lista de tareas de `python`.
- `entrega/gestor_jobs.py`: fila `"primos"` en `TAMANOS`.
- Imagen `kubernates-202630-python:1.0` reconstruida con `preparar-imagenes.ps1`.

**Cómo verificarla.** El número de primos conocido por nivel debe coincidir con el campo `primos` de la última línea JSON de los logs:

| nivel | N | primos esperados |
|---|---|---|
| baja | 1000000 | 78498 |
| media | 10000000 | 664579 |
| alta | 50000000 | 3001134 |

**Por qué solo aparece en el menú de Python.** El catálogo declara las tareas por lenguaje y el menú las lee de ahí. `primos` solo está implementada en la imagen de Python, así que solo está en `tareas.json` para ese lenguaje; ofrecerla en Java o C haría fallar el Job.

## Pruebas realizadas

<!-- RESULTADOS-PRUEBAS -->

Entorno de las pruebas: Minikube con driver docker y runtime docker, Kubernetes v1.37.0, namespace `estudiantes-202630`. Las tres imágenes se reconstruyeron con `preparar-imagenes.ps1`.

| # | Prueba | Resultado | Evidencia |
|---|---|---|---|
| 1 | Creación de Job y Pod | Correcto | La opción 1 imprime `Job creado: python-primos-baja-1791130428`, la imagen `kubernates-202630-python:1.0`, los argumentos `['primos', '1000000']`, la CPU `100m - 500m` y la memoria `64Mi - 128Mi`. El YAML del Job en el clúster tiene `backoffLimit: 0`, `restartPolicy: Never`, el contenedor `tarea` con `imagePullPolicy: Never` y los mismos requests/limits. `kubectl get jobs,pods` muestra el Job y su Pod. |
| 2 | Tareas base en Python, Java y C | Correcto | Los 12 Jobs de nivel baja (4 tareas × 3 lenguajes) terminan `Complete 1/1`. `fib` y `matriz` en media y alta, en los tres lenguajes, también terminan `Complete`. |
| 3 | Niveles de complejidad | Correcto | Con `fib` en Python: baja `["fib","25"]` 100m/500m y 64Mi/128Mi → 75025; media `["fib","30"]` 250m/1 CPU y 128Mi/512Mi → 832040; alta `["fib","35"]` 500m/2 CPU y 256Mi/1Gi → 9227465. `ordenar` alta en Python (N=3000000, límite 1Gi) termina `Complete`, sin `OOMKilled`. |
| 4 | Estado del gestor = estado de Kubernetes | Correcto | La opción 2 y `kubectl get jobs` coinciden: `en ejecucion` ↔ `Running 0/1`, `completado` ↔ `Complete 1/1` y `fallido` ↔ `Failed 0/1` (el Job del OOM). |
| 5 | Logs | Correcto | La opción 3 sobre `python-primos-alta-1791130567` devuelve las mismas líneas que `kubectl logs -n estudiantes-202630 job/python-primos-alta-1791130567`, en varias líneas y sin `b'...'`. |
| 6 | Comparación entre lenguajes | Correcto | Ver "Comparación entre Python, Java y C". |
| 7 | OOMKilled | Correcto | Con NIVELES `alta` bajado temporalmente a `mem_request: 32Mi` y `mem_limit: 48Mi`, `primos` alta en Python queda `fallido` en la opción 2 y `Failed 0/1` en Kubernetes. El Pod termina con `reason: OOMKilled` y exit code 137. Después se restauró el valor original. |
| 8 | Limpieza segura | Correcto | Había 28 Jobs completados, 1 fallido (el del OOM) y `python-fib-alta-1791130617` en ejecución. La opción 4 lista 29, sin incluir el que corre. Con `N` responde `Cancelado, no se elimino nada.`; con `s`, `29 tarea(s) eliminada(s).`. Solo queda el Job en ejecución con su Pod, y no hay Pods huérfanos. |
| 9 | Tarea adicional `primos` | Correcto | Baja, media y alta dan 78498 / 664579 / 3001134 primos (mayor primo 999983 / 9999991 / 49999991). En los menús de C y Java solo aparecen `hola`, `ordenar`, `fib` y `matriz`. |
| 10 | Robustez del menú | Correcto | En el menú principal, `9`, `abc` o una entrada vacía dan `Opcion no valida.`. En los submenús, un número fuera de rango da `Escribe un numero entre 0 y N.`; `0` o vacío vuelven atrás; `5` sale con `Hasta luego.`. |

### Comparación entre Python, Java y C

Se usan dos medidas distintas:

- **`ms` del JSON.** Cada programa mide desde dentro el tiempo de la tarea, con el runtime ya arrancado. No incluye el arranque de la JVM ni el del intérprete de Python, ni la creación del Pod.
- **Vida del proceso.** Es `FinishedAt − StartedAt` del contenedor, leído con `docker inspect` en el demonio Docker de Minikube con resolución de nanosegundos. Los campos `startedAt`/`finishedAt` de Kubernetes solo tienen resolución de segundos y no sirven para esto. Incluye el arranque del runtime, la tarea y una sobrecarga fija del runtime de contenedores. Esa sobrecarga se ve en C: un binario estático que solo imprime unas líneas vive unos 86 ms.

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

`primos` (solo Python): baja 27 ms, media 105 ms y alta 712 ms.

**Vida del proceso frente a `ms` del JSON** (otra tanda de ejecuciones; en ms):

| tarea (límite de CPU) | medida | C | Java | Python |
|---|---|---|---|---|
| hola baja (500m) | vida del proceso, mediana de 3 | 86,2 | 310,1 | 412,1 |
| hola baja (500m) | `ms` del JSON por ejecución | 0 / 0 / 0 | 97 / 95 / 50 | 0 / 0 / 0 |
| hola baja (500m) | arranque estimado | — | ≈ 127 | ≈ 326 |
| fib alta (2000m) | vida del proceso, 1 ejecución | 90,1 | 192,7 | 1969,6 |
| fib alta (2000m) | `ms` del JSON | 16 | 46 | 1697 |
| fib alta (2000m) | arranque estimado | — | ≈ 73 | ≈ 198 |

El arranque estimado es (vida − `ms`) menos la sobrecarga del contenedor que marca C en el mismo caso: 86,2 ms en hola y 74,1 ms en fib alta. En hola se usa la mediana por ejecución. Es una aproximación con pocas repeticiones.

**Lectura de los datos.**

1. **Cálculo.** C es el más rápido, o empata, en todas las tareas. Java queda cerca de C cuando el JIT ya ha compilado el código caliente (fib alta: 47 ms frente a 16 ms), y Python es unas 100 veces más lento que C en recursión (fib alta: 1678 ms). La excepción es matriz baja, donde Python (11 ms) supera a Java (39 ms): con N=60 la JVM todavía ejecuta el bucle sin compilar. Entre niveles cambian a la vez N y la CPU asignada (500m, 1000m, 2000m), así que los tiempos de un mismo lenguaje no escalan solo con N. Por ejemplo, en Java matriz alta (49 ms) tarda menos que media (68 ms).
2. **Los ~95 ms de hola en Java no son el arranque de la JVM.** Se miden ya dentro de `main`. Corresponden a la inicialización perezosa del runtime: carga de clases, primera concatenación de cadenas y `printf`.
3. **Arranque.** El arranque de la JVM se nota frente al binario de C: unos 127 ms más con 500m de CPU. Sin embargo, en estas mediciones Python tarda más en arrancar que Java: 412 ms de vida del proceso frente a 310 ms en hola, y unos 326 ms de arranque estimado frente a 127 ms. Esto no coincide con lo que sugiere el enunciado para Python, y tiene una causa medida:
   - la imagen `python:3.12-alpine` no incluye bytecode precompilado: 0 archivos `.pyc` frente a 1097 `.py` en la biblioteca estándar;
   - cada contenedor nuevo compila desde el código fuente los módulos que importa `tareas.py`;
   - con `python -X importtime` y `--cpus 0.5`, los imports de nivel superior suman unos 352 ms, casi todo `json` (246 ms, por su dependencia de `re`) y `random` (70 ms);
   - con 2000m de CPU (fib alta) ese coste baja: el arranque estimado de Python cae a unos 198 ms y el de Java a unos 73 ms.
4. **Conclusión.** Para tareas efímeras, C es claramente el más barato, porque casi todo su tiempo es la sobrecarga del contenedor. En tareas largas el arranque pierde peso frente al cálculo, y ahí la diferencia la marca la velocidad de ejecución: C, después Java y, muy por detrás, Python.

## Restricciones respetadas

- El Job se crea con el cliente oficial `kubernetes`; no se invoca `kubectl` (ni `subprocess`/`os.system`) desde Python.
- Sin interfaz web ni gráfica: solo menú de terminal.
- Un solo nodo (Minikube).
- Sin RBAC propio.
- Sin selección manual de nodos (`nodeSelector`/`affinity`).
- Los Pods los crea únicamente el Job.
- Imágenes locales `kubernates-202630-*`, sin registro externo (`imagePullPolicy: Never`).
- Contrato de entrada de las tareas intacto: `<tarea> <N>`, logs en stdout y última línea JSON.
