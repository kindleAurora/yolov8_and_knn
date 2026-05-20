FROM node:20-alpine

ARG APK_MIRROR_HOST=mirrors.aliyun.com
ARG NPM_REGISTRY=https://registry.npmmirror.com

WORKDIR /app

COPY code/web/package.json ./package.json
RUN sed -i "s|https\\?://dl-cdn.alpinelinux.org/alpine|https://${APK_MIRROR_HOST}/alpine|g" /etc/apk/repositories \
    && npm config set registry ${NPM_REGISTRY} \
    && npm install

COPY code/web/ ./

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]
