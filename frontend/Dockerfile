# DelphosFootball web app: build the Flutter release with a pinned SDK, then
# serve the static files with unprivileged nginx (ARCHITECTURE.md §8).
#
# The backend URL is compiled in (ADR-029) and also sets the CSP connect-src:
#   docker build --build-arg DELPHOS_API_URL=http://localhost:8000 frontend
# The browser calls the API from the user's machine, so the URL must be the
# one the browser can reach, not the compose-internal service name.
#
# Both base images are pinned by tag and index digest.

FROM debian:bookworm-20261104-slim@sha256:734a72b3d6142a71993b4bc580ca01d8ca687f77a2c422d96a961d3376b179bc AS build

# The SDK is cloned at its release tag and checked against the tag's commit,
# so a moved tag cannot change the toolchain silently.
ARG FLUTTER_VERSION=3.47.5
ARG FLUTTER_COMMIT=6a19cca56475dbfba1478ee68d7bd0c2ef891da1

RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl git unzip xz-utils \
 && rm -rf /var/lib/apt/lists/*

RUN git clone --depth 1 --branch "${FLUTTER_VERSION}" https://github.com/flutter/flutter.git /opt/flutter \
 && test "$(git -C /opt/flutter rev-parse HEAD)" = "${FLUTTER_COMMIT}"
ENV PATH="/opt/flutter/bin:${PATH}"
RUN flutter config --no-analytics && flutter precache --web

WORKDIR /app
COPY pubspec.yaml pubspec.lock ./
RUN flutter pub get --enforce-lockfile

COPY . .
# .gitattributes keeps the nginx files LF, but a working tree checked out
# before it existed (Windows, core.autocrlf=true) still has CRLF, and the
# sourced shell script fails on a CR. Stripping it here makes the build
# independent of the checkout. The templates become 0644 (a Windows context
# makes them 0755); the serve stage copies the cleaned files.
RUN sed -i 's/\r$//' nginx/* && chmod 0644 nginx/*.template
# Declared here so a URL change rebuilds only the compile step.
ARG DELPHOS_API_URL=http://localhost:8000
# --no-web-resources-cdn serves CanvasKit from this origin (ADR-026);
# --csp keeps dart2js from emitting eval, which the CSP forbids.
RUN flutter build web --release --no-web-resources-cdn --csp \
    --dart-define=DELPHOS_API_URL="${DELPHOS_API_URL}"

FROM nginxinc/nginx-unprivileged:1.30.6-alpine@sha256:f5116ed4606f3eb015dd4a8e28cb9b351476dc0ad4bc6e9f93b19cec130cdf03

# The runtime default matches the compiled URL; compose passes the same
# value, and 15-delphos-api-origin.envsh turns it into the CSP connect-src.
ARG DELPHOS_API_URL=http://localhost:8000
ENV DELPHOS_API_URL=${DELPHOS_API_URL}

COPY --from=build /app/nginx/default.conf.template /app/nginx/security-headers.inc.template /etc/nginx/templates/
COPY --from=build --chmod=0755 /app/nginx/15-delphos-api-origin.envsh /docker-entrypoint.d/
COPY --from=build /app/build/web /usr/share/nginx/html

EXPOSE 8080
