FROM gcc:14 AS build
WORKDIR /app
COPY tareas.c .
# -static: el binario se compila con glibc pero corre sobre Alpine (musl).
# Sin enlace estatico el contenedor fallaria al arrancar con "not found".
RUN gcc -O2 -static -o tareas tareas.c

FROM alpine:3.21
COPY --from=build /app/tareas /usr/local/bin/tareas
ENTRYPOINT ["/usr/local/bin/tareas"]
