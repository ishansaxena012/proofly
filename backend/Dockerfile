# ── build ────────────────────────────────────────────────────────────────────
# The official Maven image is used rather than ./mvnw so the build does not have
# to download a Maven distribution on every cache miss; mvnw stays committed for
# local development.
FROM maven:3.9-eclipse-temurin-21 AS build
WORKDIR /build

# Resolve dependencies in their own layer so source-only changes reuse the cache.
COPY pom.xml ./
RUN mvn -B -ntp dependency:go-offline

COPY src ./src
RUN mvn -B -ntp clean package -DskipTests \
    && mv target/proofly-backend-*.jar target/app.jar

# ── runtime ──────────────────────────────────────────────────────────────────
FROM eclipse-temurin:21-jre-alpine AS runtime

RUN addgroup -S proofly && adduser -S proofly -G proofly \
    && apk add --no-cache curl

WORKDIR /app
COPY --from=build --chown=proofly:proofly /build/target/app.jar /app/app.jar

USER proofly
EXPOSE 8080

ENV JAVA_OPTS="-XX:MaxRAMPercentage=75.0"

HEALTHCHECK --interval=15s --timeout=5s --start-period=45s --retries=5 \
    CMD curl -fsS http://localhost:8080/actuator/health || exit 1

ENTRYPOINT ["sh", "-c", "exec java $JAVA_OPTS -jar /app/app.jar"]
