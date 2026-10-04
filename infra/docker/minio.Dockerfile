FROM golang:1.25-bookworm AS build
WORKDIR /src
RUN git clone --depth 1 --branch RELEASE.2025-10-15T17-29-55Z https://github.com/minio/minio.git . \
    && test "$(git rev-parse refs/tags/RELEASE.2025-10-15T17-29-55Z)" = "9e49d5e7a648f00e26f2246f4dc28e6b07f8c84a"
RUN CGO_ENABLED=0 go build -mod=readonly -trimpath -o /out/minio .

FROM alpine:3.22
RUN apk add --no-cache ca-certificates \
    && adduser -D -u 10001 minio && mkdir /data && chown minio:minio /data
COPY --from=build /out/minio /usr/local/bin/minio
COPY --from=build /src/LICENSE /usr/share/licenses/minio/LICENSE
USER minio
EXPOSE 9000 9001
ENTRYPOINT ["minio"]
