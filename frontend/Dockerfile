FROM node:20-alpine

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm ci

ARG NEXT_PUBLIC_GRAPHQL_URL=http://localhost:8000/graphql
ENV NEXT_PUBLIC_GRAPHQL_URL=$NEXT_PUBLIC_GRAPHQL_URL

COPY . .
RUN npm run build

EXPOSE 3000
CMD ["npm", "start"]
