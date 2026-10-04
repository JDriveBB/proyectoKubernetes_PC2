FROM eclipse-temurin:21-jdk-alpine AS build
WORKDIR /app
COPY Tareas.java .
RUN javac Tareas.java

FROM eclipse-temurin:21-jre-alpine
WORKDIR /app
COPY --from=build /app/Tareas.class .
ENTRYPOINT ["java", "Tareas"]
