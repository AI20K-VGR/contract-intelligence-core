# =============================================================================
# Custom Keycloak image — adds the Phase Two "keycloak-events" extension JAR.
#
# We do NOT compile Java here. The main project is Python; the Keycloak
# extension is consumed as a pre-built, shaded JAR from Maven Central and
# dropped into /opt/keycloak/providers/ where the Quarkus distribution
# auto-discovers and registers EventListener providers on startup.
#
# Extension:    https://github.com/p2-inc/keycloak-events
# Provider IDs: ext-event-http       (raw HttpSender)
#               ext-event-webhook    (managed webhook subscriptions + REST API)
#               ext-event-script     (JS-based scripted listeners)
#               ext-event-mdc-logger-store (structured MDC event store)
#
# This JAR is a "fat" shaded jar that bundles all of its transitive
# dependencies. It was compiled by the upstream maintainers against
# Keycloak 26.6.3 (keycloak.version in their pom.xml), so it is API-
# compatible with the Quarkus-based Keycloak 26.x series used below.
#
# Build:
#   docker build -t ci-keycloak:26 -f keycloak/Dockerfile keycloak
#
# =============================================================================

# ----------------------------------------------------------------------------
# STAGE 1 — fetcher
# The Keycloak 26 base image is a stripped-down runtime: no curl, no wget,
# no rpm, no package manager at all. We download + checksum-verify the JAR
# in this dedicated stage (curlimages/curl is ~6MB and purpose-built for this)
# then COPY the verified artifact into the Keycloak stage.
# ----------------------------------------------------------------------------
FROM curlimages/curl:8.10.1 AS fetcher

ARG PHASETWO_EVENTS_VERSION=0.62
ARG PHASETWO_EVENTS_URL=https://repo1.maven.org/maven2/io/phasetwo/keycloak/keycloak-events/${PHASETWO_EVENTS_VERSION}/keycloak-events-${PHASETWO_EVENTS_VERSION}.jar
# Maven Central publishes .sha1 (and .md5) but NOT .sha256 for this artifact.
# .sha1 is the standard checksum convention; PGP signature (.asc) is the
# stronger tampering defense if you need it.
ARG PHASETWO_EVENTS_SHA1_URL=https://repo1.maven.org/maven2/io/phasetwo/keycloak/keycloak-events/${PHASETWO_EVENTS_VERSION}/keycloak-events-${PHASETWO_EVENTS_VERSION}.jar.sha1

WORKDIR /tmp

RUN set -eux; \
    curl -fsSL -o "keycloak-events-${PHASETWO_EVENTS_VERSION}.jar" \
        "${PHASETWO_EVENTS_URL}"; \
    curl -fsSL -o "keycloak-events-${PHASETWO_EVENTS_VERSION}.jar.sha1" \
        "${PHASETWO_EVENTS_SHA1_URL}"; \
    echo "$(cat keycloak-events-${PHASETWO_EVENTS_VERSION}.jar.sha1)  keycloak-events-${PHASETWO_EVENTS_VERSION}.jar" \
        | sha1sum -c -; \
    rm -f "keycloak-events-${PHASETWO_EVENTS_VERSION}.jar.sha1"; \
    ls -lh "keycloak-events-${PHASETWO_EVENTS_VERSION}.jar"

# ----------------------------------------------------------------------------
# STAGE 2 — runtime
# Pin a specific Keycloak 26.x patch so the SPI API matches what was used
# when the upstream JAR was compiled (Keycloak 26.6.3 according to
# p2-inc/keycloak-events v0.62 pom.xml).
# ----------------------------------------------------------------------------
FROM quay.io/keycloak/keycloak:26.7.4

# Build args are scoped per stage — redeclare so --build-arg reaches COPY/LABEL.
ARG PHASETWO_EVENTS_VERSION=0.62

# Keycloak providers dir; the Quarkus distribution auto-loads every JAR
# placed here on startup. Providers advertise themselves through the
# standard java.util.ServiceLoader mechanism (META-INF/services/) so no
# additional wiring is required.
ENV KEYCLOAK_PROVIDERS_DIR=/opt/keycloak/providers
ENV KEYCLOAK_EVENTS_JAR=keycloak-events-${PHASETWO_EVENTS_VERSION}.jar

# Drop the verified JAR into the providers dir. Switch briefly to root
# (the base image's USER keycloak can't write to /opt/keycloak/providers/),
# then drop back.
USER root
COPY --from=fetcher /tmp/keycloak-events-${PHASETWO_EVENTS_VERSION}.jar ${KEYCLOAK_PROVIDERS_DIR}/${KEYCLOAK_EVENTS_JAR}
RUN chown -R keycloak:keycloak "${KEYCLOAK_PROVIDERS_DIR}" \
    && ls -lh "${KEYCLOAK_PROVIDERS_DIR}/${KEYCLOAK_EVENTS_JAR}"
USER keycloak

# ------------------------------------------------------------------
# 3) Metadata
# ------------------------------------------------------------------
LABEL maintainer="Contract Intelligence Team" \
      description="Keycloak 26 with Phase Two keycloak-events extension (HTTP/webhook/script listeners)" \
      org.opencontainers.image.source="https://github.com/p2-inc/keycloak-events" \
      org.opencontainers.image.version="${PHASETWO_EVENTS_VERSION}"

# Default entrypoint inherited from base image: ["bin/kc.sh"]
# The compose file passes the actual start command via `command:`.
