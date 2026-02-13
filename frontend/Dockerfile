FROM node:20-alpine

WORKDIR /app

COPY package.json ./
# npm install (not ci) because no lockfile is committed yet
RUN npm install

COPY . .

EXPOSE 3000

CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]
