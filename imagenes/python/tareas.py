#!/usr/bin/env python3
"""Ejecutor de tareas en Python.

Contrato, identico en las tres imagenes:
  entrada  : argumentos del contenedor -> <tarea> <N>
  salida   : logs libres en stdout; la ULTIMA linea es un JSON de una linea
  exit code: 0 = exito, != 0 = fallo (deja el Job en Failed)
"""
import json
import math
import os
import platform
import random
import sys
import time


def hola(_n):
    print(f"Hola desde Python {sys.version.split()[0]}")
    print(f"Hostname   : {platform.node()}")
    print(f"CPUs vistas: {os.cpu_count()}")
    return {"mensaje": "hola mundo", "runtime": f"python {sys.version.split()[0]}"}


def ordenar(n):
    print(f"Generando {n} enteros aleatorios...")
    datos = [random.randint(0, 2**31) for _ in range(n)]
    print("Ordenando...")
    datos.sort()
    # Verificacion: nunca reportar exito sin comprobar el resultado.
    assert all(datos[i] <= datos[i + 1] for i in range(0, len(datos) - 1, 997))
    return {"n": n, "primero": datos[0], "ultimo": datos[-1]}


def fib(n):
    # Recursivo a proposito: sin memoizacion satura una CPU.
    def f(k):
        return k if k < 2 else f(k - 1) + f(k - 2)

    sys.setrecursionlimit(10000)
    print(f"Calculando fib({n}) de forma recursiva, sin memoizacion...")
    return {"n": n, "fib": f(n)}


def matriz(n):
    print(f"Multiplicando dos matrices de {n}x{n} con triple bucle...")
    a = [[random.random() for _ in range(n)] for _ in range(n)]
    b = [[random.random() for _ in range(n)] for _ in range(n)]
    c = [[0.0] * n for _ in range(n)]
    for i in range(n):
        fila_a, fila_c = a[i], c[i]
        for k in range(n):
            aik, fila_b = fila_a[k], b[k]
            for j in range(n):
                fila_c[j] += aik * fila_b[j]
        if n >= 100 and i % max(1, n // 10) == 0:
            print(f"  fila {i}/{n}")
    return {"n": n, "traza": round(sum(c[i][i] for i in range(n)), 6)}


def primos(n):
    print(f"Criba de Eratostenes hasta {n}...")
    criba = bytearray([1]) * (n + 1)  # un byte por numero: la memoria crece con N
    criba[:2] = b"\x00\x00"[: n + 1]
    for i in range(2, math.isqrt(n) + 1):
        if criba[i]:
            criba[i * i :: i] = bytes(len(range(i * i, n + 1, i)))
    total = criba.count(1)
    mayor = criba.rfind(1)
    # Verificacion: el mayor primo encontrado se comprueba por division de prueba.
    assert mayor < 2 or all(mayor % d for d in range(2, math.isqrt(mayor) + 1))
    return {"n": n, "primos": total, "mayor": mayor}


TAREAS = {
    "hola": hola,
    "ordenar": ordenar,
    "fib": fib,
    "matriz": matriz,
    "primos": primos,
}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in TAREAS:
        print(f"Uso: <{'|'.join(TAREAS)}> <N>", file=sys.stderr)
        return 2

    tarea = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    random.seed(42)

    print(f"--- tarea={tarea} n={n} ---")
    inicio = time.time()
    resultado = TAREAS[tarea](n)
    ms = int((time.time() - inicio) * 1000)

    # La ultima linea DEBE ser el JSON de una sola linea.
    print(json.dumps({"tarea": tarea, "lenguaje": "python", "ms": ms, **resultado}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
