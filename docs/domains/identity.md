# Identity

O módulo `Identity` é responsável pelo gerenciamento da identidade dos
usuários na plataforma, incluindo criação, autenticação, atualização e
remoção de usuários.

## Entidades

### User

Representa um usuário da plataforma.

Um usuário possui os seguintes atributos:

* `id`
* `username`
* `email`
* `password_hash`
* `created_at`
* `updated_at`

O email de cada usuário deve ser único.

### Refresh Token

Representa um token utilizado para renovar a autenticação de um usuário
sem que seja necessário fornecer novamente suas credenciais.

Um refresh token possui os seguintes atributos:

* `id`
* `user_id`
* `token_hash`
* `expires_at`
* `revoked`

## Regras de negócio

* A autenticação dos usuários utiliza JWT.
* O login é limitado por um mecanismo de rate limiting baseado em
  token bucket.
* Cada usuário deve possuir um email único.
* Refresh tokens expirados não podem ser utilizados para autenticação.
* Refresh tokens revogados não podem ser utilizados para autenticação.

## API pública

A API pública do módulo deve disponibilizar as seguintes operações:

### `get_by_id`

Obtém um usuário a partir de seu identificador.

### `get_current_user`

Obtém o usuário associado ao contexto de autenticação atual.

## Rotas da API

### Usuários

#### `POST /users`

Cria um novo usuário.

#### `GET /users/{id}`

Obtém um usuário a partir de seu identificador.

#### `PUT /users`

Atualiza as informações do usuário autenticado.

#### `PATCH /users/change-password`

Altera a senha do usuário autenticado.

### Autenticação

#### `POST /login`

Autentica um usuário utilizando email e senha e retorna os tokens
necessários para autenticação.

#### `POST /refresh-token`

Renova a autenticação utilizando um refresh token válido e emite um
novo refresh token.

#### `POST /logout`

Encerra a sessão do usuário e invalida os refresh tokens associados a
ela.

### Recuperação de senha

#### `PATCH /users/forgot-password`

Inicia ou executa o processo de recuperação de senha de um usuário.
