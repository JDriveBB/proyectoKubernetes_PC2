/* Ejecutor de tareas en C.
 *
 * Contrato, identico en las tres imagenes:
 *   entrada  : argumentos del contenedor -> <tarea> <N>
 *   salida   : logs libres en stdout; la ULTIMA linea es un JSON de una linea
 *   exit code: 0 = exito, != 0 = fallo (deja el Job en Failed)
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include <unistd.h>

static double ahora_ms(void) {
    struct timespec ts;
    clock_gettime(CLOCK_MONOTONIC, &ts);
    return ts.tv_sec * 1000.0 + ts.tv_nsec / 1e6;
}

static int cmp_ll(const void *a, const void *b) {
    long long x = *(const long long *)a, y = *(const long long *)b;
    return (x > y) - (x < y);
}

static long long fib_rec(int k) {
    return k < 2 ? k : fib_rec(k - 1) + fib_rec(k - 2);
}

int main(int argc, char *argv[]) {
    if (argc < 2) {
        fprintf(stderr, "Uso: <hola|ordenar|fib|matriz> <N>\n");
        return 2;
    }

    const char *tarea = argv[1];
    long n = argc > 2 ? atol(argv[2]) : 0;
    srand(42u);

    char host[256] = {0};
    gethostname(host, sizeof(host) - 1);
    printf("--- tarea=%s n=%ld ---\n", tarea, n);

    double t0 = ahora_ms();
    char extra[256] = {0};

    if (strcmp(tarea, "hola") == 0) {
        printf("Hola desde C (gcc %d.%d)\n", __GNUC__, __GNUC_MINOR__);
        printf("Hostname : %s\n", host);
        snprintf(extra, sizeof(extra), "\"mensaje\":\"hola mundo\",\"runtime\":\"gcc\"");

    } else if (strcmp(tarea, "ordenar") == 0) {
        printf("Generando %ld enteros aleatorios...\n", n);
        long long *v = malloc((size_t)n * sizeof(long long));
        if (!v) { fprintf(stderr, "malloc fallo para %ld elementos\n", n); return 1; }
        for (long i = 0; i < n; i++) v[i] = ((long long)rand() << 31) | rand();
        printf("Ordenando...\n");
        qsort(v, (size_t)n, sizeof(long long), cmp_ll);
        for (long i = 0; i + 1 < n; i += 997)
            if (v[i] > v[i + 1]) { fprintf(stderr, "orden incorrecto\n"); return 1; }
        snprintf(extra, sizeof(extra), "\"n\":%ld,\"primero\":%lld,\"ultimo\":%lld",
                 n, v[0], v[n - 1]);
        free(v);

    } else if (strcmp(tarea, "fib") == 0) {
        printf("Calculando fib(%ld) recursivamente, sin memoizacion...\n", n);
        long long r = fib_rec((int)n);
        snprintf(extra, sizeof(extra), "\"n\":%ld,\"fib\":%lld", n, r);

    } else if (strcmp(tarea, "matriz") == 0) {
        printf("Multiplicando dos matrices de %ldx%ld...\n", n, n);
        size_t sz = (size_t)n * (size_t)n;
        double *a = malloc(sz * sizeof(double));
        double *b = malloc(sz * sizeof(double));
        double *c = calloc(sz, sizeof(double));
        if (!a || !b || !c) { fprintf(stderr, "sin memoria para %ldx%ld\n", n, n); return 1; }
        for (size_t i = 0; i < sz; i++) {
            a[i] = rand() / (double)RAND_MAX;
            b[i] = rand() / (double)RAND_MAX;
        }
        for (long i = 0; i < n; i++) {
            for (long k = 0; k < n; k++) {
                double aik = a[i * n + k];
                for (long j = 0; j < n; j++) c[i * n + j] += aik * b[k * n + j];
            }
            if (n >= 100 && i % (n / 10 > 0 ? n / 10 : 1) == 0) printf("  fila %ld/%ld\n", i, n);
        }
        double traza = 0.0;
        for (long i = 0; i < n; i++) traza += c[i * n + i];
        snprintf(extra, sizeof(extra), "\"n\":%ld,\"traza\":%.6f", n, traza);
        free(a); free(b); free(c);

    } else {
        fprintf(stderr, "Tarea desconocida: %s\n", tarea);
        return 2;
    }

    /* Ultima linea: JSON de una sola linea. */
    printf("{\"tarea\":\"%s\",\"lenguaje\":\"c\",\"ms\":%d,%s}\n",
           tarea, (int)(ahora_ms() - t0), extra);
    return 0;
}
