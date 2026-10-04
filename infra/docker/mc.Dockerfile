FROM golang:1.25-bookworm AS build
WORKDIR /src
RUN git clone --depth 1 --branch RELEASE.2025-08-13T08-35-41Z https://github.com/minio/mc.git . \
    && test "$(git rev-parse refs/tags/RELEASE.2025-08-13T08-35-41Z)" = "d6541ea280b73a834b64d4097e21f2be77676104"
RUN CGO_ENABLED=0 go build -mod=readonly -trimpath -o /out/mc .

FROM alpine:3.22
RUN apk add --no-cache ca-certificates
COPY --from=build /out/mc /usr/local/bin/mc
COPY --from=build /src/LICENSE /usr/share/licenses/mc/LICENSE
ENTRYPOINT ["mc"]
