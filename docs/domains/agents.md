# Agents

O módulo `Agents` é responsável por lidar com chats de conversa,
enfileiramento de mensagens, workflows de IA e engenharia de contexto.

## Entidades

### Workflow

Representa um workflow de IA.

Um workflow possui os seguintes atributos:

* `id`
* `name`
* `description`
* `picture`
* `created_at`
* `updated_at`

Cada workflow deve possuir um nome único, pois será identificado pelo
nome no código.

### Chat

Representa uma conversa associada a um projeto.

Um chat possui os seguintes atributos:

* `id`
* `project_id`
* `title`
* `owner`
* `created_at`
* `updated_at`

### Message

Representa uma mensagem enviada durante uma conversa.

Uma mensagem possui os seguintes atributos:

* `id`
* `content`
* `sender_name`
* `sender_type`
* `created_at`
* `updated_at`
* `metadata`

Os metadados podem conter informações como quantidade de tokens
utilizados, workflow e modelo utilizado.

## Requisitos

* O sistema deve possuir observabilidade sobre os workflows, incluindo
  tokens utilizados, custos e tempo de execução.
* O sistema deve ser capaz de enviar respostas em tempo real.
* O sistema deve informar em qual etapa do workflow a execução se encontra.
* O sistema deve permitir a colaboração de humanos durante a execução
  do workflow (`human-in-the-loop`).

## API pública

A API pública do módulo deve disponibilizar as seguintes operações:

### `get_chats_by_project`

Recupera os chats associados a um projeto.

## Rotas da API

### Workflows

#### `GET /workflows`

Obtém os workflows disponíveis.

### Chats

#### `GET /chats/{id}/messages`

Obtém as mensagens de um chat.

#### `POST /chats/{id}/messages`
