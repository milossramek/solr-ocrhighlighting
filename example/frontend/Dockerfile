
FROM node:14-alpine as builder
ARG CFG_IMAGE_API_BASE
ARG CFG_LIBRARY_NAME
ARG CFG_SERVER_URL
ARG CFG_SNIPPET_SCALING
RUN echo "Building  with CFG_IMAGE_API_BASE=$CFG_IMAGE_API_BASE"
RUN echo "Building  with CFG_LIBRARY_NAME=$CFG_LIBRARY_NAME"
RUN echo "Building  with CFG_SERVER_URL=$CFG_SERVER_URL"
RUN echo "Building  with CFG_SNIPPET_SCALING=$CFG_SNIPPET_SCALING"

COPY . /build

RUN apk add git &&\
    cd /build &&\
    npm install &&\
    sed -i "s#__CFG_IMAGE_API_BASE__#$CFG_IMAGE_API_BASE#" index.js &&\
    sed -i "s#__CFG_LIBRARY_NAME__#$CFG_LIBRARY_NAME__#" index.js &&\
    sed -i "s#__CFG_SERVER_URL__#$CFG_SERVER_URL__#" index.js &&\
    sed -i "s#__CFG_SNIPPET_SCALING__#$CFG_SNIPPET_SCALING#" index.js &&\
    npm run build &&\
    rm -rf build/sw.js

FROM nginx:alpine

COPY --from=builder /build/build /usr/share/nginx/html
RUN mkdir /usr/share/nginx/html/viewer
COPY ./vhost.conf /etc/nginx/conf.d/default.conf
COPY ./viewer.html /usr/share/nginx/html/viewer/index.html

