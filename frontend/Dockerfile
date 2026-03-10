FROM node:20-alpine AS build

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .
RUN npm run build

# Imagen final: solo contiene los archivos estaticos del build
FROM alpine:3.19

COPY --from=build /app/dist /dist

# Al iniciar, copia dist al volumen compartido y espera indefinidamente
CMD ["sh", "-c", "cp -r /dist/. /srv/ && echo 'Frontend build copied to /srv' && sleep infinity"]
