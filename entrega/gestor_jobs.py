import json
import re
import time
from pathlib import Path

from kubernetes import client, config
from kubernetes.client.rest import ApiException
from kubernetes.config.config_exception import ConfigException
from urllib3.exceptions import MaxRetryError

NAMESPACE = "estudiantes-202630"
RAIZ = Path(__file__).resolve().parent.parent
CATALOGO = RAIZ / "catalogo" / "tareas.json"

NIVELES = {
    "baja": {
        "cpu_request": "100m",
        "cpu_limit": "500m",
        "mem_request": "64Mi",
        "mem_limit": "128Mi",
    },
    "media": {
        "cpu_request": "250m",
        "cpu_limit": "1000m",
        "mem_request": "128Mi",
        "mem_limit": "512Mi",
    },
    "alta": {
        "cpu_request": "500m",
        "cpu_limit": "2000m",
        "mem_request": "256Mi",
        "mem_limit": "1Gi",
    },
}

TAMANOS = {
    "hola": {"baja": 0, "media": 0, "alta": 0},
    "ordenar": {"baja": 100000, "media": 1000000, "alta": 3000000},
    "fib": {"baja": 25, "media": 30, "alta": 35},
    "matriz": {"baja": 60, "media": 120, "alta": 250},
    "primos": {"baja": 1000000, "media": 10000000, "alta": 50000000},
}


# Carga y retorna el catálogo de tareas desde el archivo JSON.
def cargar_catalogo():
    with CATALOGO.open(encoding="utf-8") as archivo:
        return json.load(archivo)


# Muestra un menú de opciones numeradas en consola y retorna la opción seleccionada o None.
def elegir_opcion(titulo, opciones):
    print(f"\n{titulo}")
    for numero, opcion in enumerate(opciones, start=1):
        print(f"  {numero}. {opcion}")
    print("  0. Volver")

    while True:
        respuesta = input("Opcion: ").strip()
        if respuesta in ("", "0"):
            return None
        if respuesta.isdigit() and 1 <= int(respuesta) <= len(opciones):
            return opciones[int(respuesta) - 1]
        print(f"Escribe un numero entre 0 y {len(opciones)}.")


# Solicita interactivamente lenguaje, tarea y complejidad, retornando la configuración y recursos elegidos.
def seleccionar(catalogo):
    lenguaje = elegir_opcion("Lenguaje:", sorted(catalogo))
    if lenguaje is None:
        return None

    definicion = catalogo[lenguaje]
    tarea = elegir_opcion("Tarea:", definicion["tasks"])
    if tarea is None:
        return None

    tamanos = TAMANOS.get(tarea)
    if not tamanos:
        print(f"La tarea {tarea} no tiene tamanos definidos en TAMANOS.")
        return None

    etiquetas = [
        f"{nivel} (N={tamanos[nivel]}, memoria {NIVELES[nivel]['mem_limit']})"
        for nivel in NIVELES
    ]
    etiqueta = elegir_opcion("Complejidad:", etiquetas)
    if etiqueta is None:
        return None
    complejidad = etiqueta.split(" ")[0]

    imagen = definicion["image"]
    argumentos = [tarea, str(tamanos[complejidad])]
    recursos = NIVELES[complejidad]

    return lenguaje, tarea, complejidad, imagen, argumentos, recursos


# Construye y retorna un nombre válido para el Job en Kubernetes.
def nombre_job(lenguaje, tarea, complejidad):
    base = f"{lenguaje}-{tarea}-{complejidad}-{int(time.time())}".lower()
    return re.sub(r"[^a-z0-9-]", "-", base)[:63].strip("-")


# Carga la configuración de kubeconfig y desactiva los reintentos de conexión.
def cargar_configuracion():
    config.load_kube_config()
    configuracion = client.Configuration.get_default_copy()
    configuracion.retries = 0
    client.Configuration.set_default(configuracion)


# Inicializa la configuración de Kubernetes y retorna una instancia del cliente BatchV1Api.
def cliente_batch():
    cargar_configuracion()
    return client.BatchV1Api()


# Construye y envía la definición del Job al clúster de Kubernetes en el namespace configurado.
def crear_job(nombre, imagen, argumentos, recursos):
    limites = client.V1ResourceRequirements(
        requests={"cpu": recursos["cpu_request"], "memory": recursos["mem_request"]},
        limits={"cpu": recursos["cpu_limit"], "memory": recursos["mem_limit"]},
    )

    contenedor = client.V1Container(
        name="tarea",
        image=imagen,
        image_pull_policy="Never",
        args=argumentos,
        resources=limites,
    )

    plantilla = client.V1PodTemplateSpec(
        spec=client.V1PodSpec(
            restart_policy="Never",
            containers=[contenedor],
        ),
    )

    especificacion = client.V1JobSpec(
        backoff_limit=0,
        template=plantilla,
    )

    job = client.V1Job(
        api_version="batch/v1",
        kind="Job",
        metadata=client.V1ObjectMeta(name=nombre, namespace=NAMESPACE),
        spec=especificacion,
    )

    cliente_batch().create_namespaced_job(namespace=NAMESPACE, body=job)
    return nombre


# Traduce los contadores de estado del Job a una descripción legible.
def describir_estado(status):
    activos = status.active or 0
    correctos = status.succeeded or 0
    fallidos = status.failed or 0

    if activos > 0:
        return "en ejecucion"
    if correctos > 0:
        return "completado"
    if fallidos > 0:
        return "fallido"
    return "pendiente (el Pod todavia no ha arrancado)"


# Consulta y retorna la lista de todos los Jobs en el namespace con su estado.
def listar_jobs():
    jobs = cliente_batch().list_namespaced_job(namespace=NAMESPACE)
    return [(job.metadata.name, describir_estado(job.status)) for job in jobs.items]


# Consulta y retorna la descripción del estado de un Job específico.
def consultar_estado(nombre):
    job = cliente_batch().read_namespaced_job_status(name=nombre, namespace=NAMESPACE)
    return f"{nombre}: {describir_estado(job.status)}"


# Obtiene y retorna los logs del Pod asociado a un Job determinado.
def consultar_logs(nombre):
    cargar_configuracion()
    core = client.CoreV1Api()

    pods = core.list_namespaced_pod(
        namespace=NAMESPACE,
        label_selector=f"job-name={nombre}",
    )
    if not pods.items:
        return f"El Job {nombre} todavia no tiene Pods."

    pod = pods.items[0].metadata.name

    respuesta = core.read_namespaced_pod_log(
        name=pod, namespace=NAMESPACE, _preload_content=False)
    return respuesta.data.decode("utf-8", errors="replace")


# Consulta y retorna los nombres de los Jobs que ya han finalizado.
def jobs_terminados():
    jobs = cliente_batch().list_namespaced_job(namespace=NAMESPACE)

    return [
        job.metadata.name
        for job in jobs.items
        if (job.status.active or 0) == 0
        and ((job.status.succeeded or 0) > 0 or (job.status.failed or 0) > 0)
    ]


# Elimina un Job del clúster junto con los Pods que creó.
def eliminar_job(nombre):
    cliente_batch().delete_namespaced_job(
        name=nombre,
        namespace=NAMESPACE,
        body=client.V1DeleteOptions(propagation_policy="Background"),
    )


# Gestiona la selección de parámetros, creación y confirmación de un nuevo Job.
def accion_ejecutar(catalogo):
    eleccion = seleccionar(catalogo)
    if eleccion is None:
        return

    lenguaje, tarea, complejidad, imagen, argumentos, recursos = eleccion
    nombre = nombre_job(lenguaje, tarea, complejidad)
    crear_job(nombre, imagen, argumentos, recursos)

    print(f"\nJob creado: {nombre}")
    print(f"  Imagen: {imagen}")
    print(f"  Argumentos del contenedor: {argumentos}")
    print(f"  CPU: {recursos['cpu_request']} - {recursos['cpu_limit']}")
    print(f"  Memoria: {recursos['mem_request']} - {recursos['mem_limit']}")
    print("  Revisa su estado con la opcion 2 del menu.")


# Muestra en consola la lista y el estado de todos los Jobs en el namespace.
def accion_estado():
    jobs = listar_jobs()
    if not jobs:
        print(f"\nNo hay Jobs en el namespace {NAMESPACE}.")
        return

    print(f"\nTareas en {NAMESPACE}:")
    for nombre, estado in jobs:
        print(f"  - {nombre}: {estado}")


# Permite seleccionar un Job existente y muestra los logs de su ejecución.
def accion_logs():
    jobs = listar_jobs()
    if not jobs:
        print(f"\nNo hay Jobs en el namespace {NAMESPACE}.")
        return

    nombres = [nombre for nombre, _ in jobs]
    nombre = elegir_opcion("De que tarea quieres ver los logs?", nombres)
    if nombre is None:
        return

    print(f"\nSalida de {nombre}:")
    print(consultar_logs(nombre) or "(el contenedor todavia no ha escrito nada)")


# Lista los Jobs terminados, solicita confirmación y los elimina del namespace.
def accion_limpiar():
    terminados = jobs_terminados()
    if not terminados:
        print("\nNo hay tareas terminadas que limpiar.")
        return

    print(f"\nSe eliminaran {len(terminados)} tarea(s) terminada(s):")
    for nombre in terminados:
        print(f"  - {nombre}")

    if input("Confirmas? [s/N]: ").strip().lower() not in ("s", "si"):
        print("Cancelado, no se elimino nada.")
        return

    for nombre in terminados:
        try:
            eliminar_job(nombre)
        except ApiException as error:
            if error.status != 404:
                raise
    print(f"{len(terminados)} tarea(s) eliminada(s).")


# Extrae el mensaje de error retornado por el API server de Kubernetes.
def detalle_api(error):
    try:
        return json.loads(error.body)["message"]
    except (TypeError, ValueError, KeyError):
        return error.reason


# Traduce las excepciones de Kubernetes y conexión a mensajes claros y orientativos.
def explicar_error(error):
    if isinstance(error, ConfigException):
        return (
            "No hay un cluster activo en kubeconfig. Arranca Minikube con:\n"
            "  minikube start --driver=docker --container-runtime=docker"
        )
    if isinstance(error, MaxRetryError):
        return (
            "No se pudo conectar con el cluster. Comprueba que Docker Desktop "
            "este abierto y que Minikube este encendido (minikube status)."
        )
    if isinstance(error, ApiException):
        detalle = detalle_api(error)
        if error.status in (401, 403):
            return f"Kubernetes rechazo la operacion por permisos: {detalle}"
        if error.status == 404 and "namespaces" in detalle:
            return (
                f"El namespace {NAMESPACE} no existe. Crealo con:\n"
                "  kubectl apply -f .\\k8s\\00-namespace.yaml"
            )
        if error.status == 404:
            return f"Ya no existe en el cluster: {detalle}"
        if error.status == 409:
            return (
                "Ya existe un Job con ese nombre. Espera un segundo y "
                "vuelve a intentarlo."
            )
        if error.status == 400 and "waiting to start" in detalle:
            mensaje = f"El contenedor todavia no ha arrancado: {detalle}"
            if "ErrImageNeverPull" in detalle:
                mensaje += (
                    "\nLa imagen no esta dentro de Minikube. Construyela con:\n"
                    "  .\\scripts\\preparar-imagenes.ps1"
                )
            return mensaje
        if error.status >= 500:
            return (
                f"El cluster respondio con un error interno ({error.status}): "
                f"{detalle}. Prueba de nuevo en unos segundos."
            )
        return f"Kubernetes rechazo la peticion ({error.status}): {detalle}"
    if isinstance(error, KeyError):
        return f"Falta la clave {error} en catalogo/tareas.json."
    return f"Error inesperado: {error}"


# Despliega el menú principal interactivo y procesa las opciones seleccionadas.
def menu():
    try:
        catalogo = cargar_catalogo()
    except FileNotFoundError:
        print(f"No se encontro el catalogo en {CATALOGO}.")
        return 1
    except json.JSONDecodeError as error:
        print(f"El catalogo {CATALOGO} no es un JSON valido: {error}")
        return 1

    acciones = {
        "1": ("Ejecutar una tarea nueva", lambda: accion_ejecutar(catalogo)),
        "2": ("Revisar el estado de las tareas", accion_estado),
        "3": ("Ver los logs de una tarea", accion_logs),
        "4": ("Limpiar las tareas terminadas", accion_limpiar),
    }

    while True:
        print(f"\n=== Gestor de Jobs - namespace {NAMESPACE} ===")
        for clave, (titulo, _) in acciones.items():
            print(f"  {clave}. {titulo}")
        print("  5. Salir")

        opcion = input("Opcion: ").strip()
        if opcion == "5":
            print("Hasta luego.")
            return 0
        if opcion not in acciones:
            print("Opcion no valida.")
            continue

        try:
            acciones[opcion][1]()
        except EOFError:
            raise
        except Exception as error:
            print(f"\nError: {explicar_error(error)}")


# Ejecuta el menú principal del programa y maneja la terminación por teclado.
if __name__ == "__main__":
    try:
        raise SystemExit(menu())
    except (KeyboardInterrupt, EOFError):
        print("\nInterrumpido.")
