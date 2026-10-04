/* Ejecutor de tareas en Java.
 *
 * Contrato, identico en las tres imagenes:
 *   entrada  : argumentos del contenedor -> <tarea> <N>
 *   salida   : logs libres en stdout; la ULTIMA linea es un JSON de una linea
 *   exit code: 0 = exito, != 0 = fallo (deja el Job en Failed)
 *
 * La JVM tarda notablemente mas en arrancar que Python o un binario de C.
 * Comparen la tarea "hola" en los tres lenguajes: es un argumento real sobre
 * cuando conviene cada runtime para cargas efimeras.
 */
import java.util.Arrays;
import java.util.Random;

public class Tareas {

    static long fib(int k) {
        return k < 2 ? k : fib(k - 1) + fib(k - 2);
    }

    public static void main(String[] args) {
        if (args.length < 1) {
            System.err.println("Uso: <hola|ordenar|fib|matriz> <N>");
            System.exit(2);
        }

        String tarea = args[0];
        int n = args.length > 1 ? Integer.parseInt(args[1]) : 0;
        Random rnd = new Random(42);

        System.out.printf("--- tarea=%s n=%d ---%n", tarea, n);
        long t0 = System.currentTimeMillis();
        String extra;

        switch (tarea) {
            case "hola" -> {
                System.out.println("Hola desde Java " + System.getProperty("java.version"));
                System.out.println("VM        : " + System.getProperty("java.vm.name"));
                System.out.println("Procesadores visibles: "
                        + Runtime.getRuntime().availableProcessors());
                System.out.println("Memoria max JVM      : "
                        + Runtime.getRuntime().maxMemory() / (1024 * 1024) + " MiB");
                extra = "\"mensaje\":\"hola mundo\",\"runtime\":\"java "
                        + System.getProperty("java.version") + "\"";
            }
            case "ordenar" -> {
                System.out.printf("Generando %d enteros aleatorios...%n", n);
                long[] v = new long[n];
                for (int i = 0; i < n; i++) v[i] = rnd.nextLong();
                System.out.println("Ordenando...");
                Arrays.sort(v);
                for (int i = 0; i + 1 < n; i += 997)
                    if (v[i] > v[i + 1]) {
                        System.err.println("orden incorrecto");
                        System.exit(1);
                    }
                extra = String.format("\"n\":%d,\"primero\":%d,\"ultimo\":%d", n, v[0], v[n - 1]);
            }
            case "fib" -> {
                System.out.printf("Calculando fib(%d) recursivamente, sin memoizacion...%n", n);
                extra = String.format("\"n\":%d,\"fib\":%d", n, fib(n));
            }
            case "matriz" -> {
                System.out.printf("Multiplicando dos matrices de %dx%d...%n", n, n);
                double[][] a = new double[n][n], b = new double[n][n], c = new double[n][n];
                for (int i = 0; i < n; i++)
                    for (int j = 0; j < n; j++) {
                        a[i][j] = rnd.nextDouble();
                        b[i][j] = rnd.nextDouble();
                    }
                for (int i = 0; i < n; i++) {
                    for (int k = 0; k < n; k++) {
                        double aik = a[i][k];
                        for (int j = 0; j < n; j++) c[i][j] += aik * b[k][j];
                    }
                    if (n >= 100 && i % Math.max(1, n / 10) == 0)
                        System.out.printf("  fila %d/%d%n", i, n);
                }
                double traza = 0;
                for (int i = 0; i < n; i++) traza += c[i][i];
                extra = String.format("\"n\":%d,\"traza\":%.6f", n, traza);
            }
            default -> {
                System.err.println("Tarea desconocida: " + tarea);
                System.exit(2);
                return;
            }
        }

        // Ultima linea: JSON de una sola linea.
        System.out.printf("{\"tarea\":\"%s\",\"lenguaje\":\"java\",\"ms\":%d,%s}%n",
                tarea, System.currentTimeMillis() - t0, extra);
    }
}
