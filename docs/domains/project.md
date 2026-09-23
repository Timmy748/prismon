# Project

O módulo `Project` é responsável por lidar com o contexto de um
projeto de marca. Isso inclui adicionar e remover membros do projeto,
adicionar, remover, editar e recuperar documentos e assets, além de lidar
com as permissões dos membros.

## Entidades

### Project

Representa um projeto no sistema.

Cada projeto pertence a um usuário, porém pode possuir vários usuários
como membros. Um usuário também pode possuir ou participar de vários
projetos.

Um projeto possui os seguintes atributos:

* `id`
* `public_id`
* `name`
* `description`
* `created_at`
* `updated_at`
* `owner`

A descrição de um projeto é opcional e não impacta o contexto do projeto.

### Member

Representa um membro de um projeto e seu cargo nele.

Um membro possui os seguintes atributos:

* `id`
* `project_id`
* `user_id`
* `role`
* `status`
* `created_at`
* `updated_at`

Ao adicionar um membro a um projeto, ele deve aceitar o convite para
participar do projeto.

### RBAC

Representa o conjunto de permissões associado a um cargo dentro de um
projeto.

### Document

Representa um documento relacionado à marca. Pode ser, por exemplo,
um documento de tom de voz, um guia de identidade visual ou um guia
mais específico sobre como a marca deve agir em determinada situação.

Um documento possui os seguintes atributos:

* `id`
* `file`
* `name`
* `description`
* `status`
* `created_at`
* `updated_at`

### Asset

Representa um recurso visual pertencente à marca. Pode ser um
grafismo, logo, imagem ou outro material que possa ser utilizado pela IA
como referência.

Um asset possui os seguintes atributos:

* `id`
* `file`
* `type`
* `description`
* `status`
* `created_at`
* `updated_at`

## Requisitos

* Um usuário que não pertence ao projeto não deve conseguir saber da
  existência do projeto.
* Apenas membros com cargos superiores, como `director`, `owner` ou
  `brand_strategy`, podem alterar, adicionar ou remover documentos
  livremente.
* Membros comuns podem adicionar assets e documentos, mas esses materiais
  devem ser aprovados por membros com cargos superiores.

## API pública

A API pública do módulo deve disponibilizar as seguintes operações:

### `get_documents`

Recupera os documentos de um projeto.

### `get_assets`

Recupera os assets de um projeto.

### `has_permission`

Verifica se um usuário possui determinada permissão dentro de um projeto.

## Rotas da API

### Projetos

#### `GET /projects`

Obtém os projetos dos quais o usuário participa.

#### `POST /projects`

Cria um novo projeto.

#### `PUT /projects/{public_id}`

Atualiza as informações de um projeto.

#### `DELETE /projects/{public_id}`

Remove um projeto.

### Membros

#### `GET /projects/{public_id}/members`

Obtém os membros de um projeto.

#### `POST /projects/{public_id}/members`

Adiciona um membro ao projeto.

#### `PATCH /projects/{public_id}/members`

Atualiza informações ou permissões de um membro.

#### `PATCH /projects/{public_id}/accept`

Aceita um convite para participar do projeto.

#### `PATCH /projects/{public_id}/refuse`

Recusa um convite para participar do projeto.

#### `DELETE /projects/{public_id}/members`

Remove um membro do projeto.

### Documentos

#### `GET /projects/{public_id}/documents`

Obtém os documentos de um projeto.

#### `POST /projects/{public_id}/documents`

Adiciona um documento ao projeto.

#### `PUT /projects/{public_id}/documents/{document_id}`

Atualiza um documento do projeto.

#### `DELETE /projects/{public_id}/documents/{document_id}`

Remove um documento do projeto.

### Assets

#### `GET /projects/{public_id}/assets`

Obtém os assets de um projeto.

#### `POST /projects/{public_id}/assets`

Adiciona um asset ao projeto.

#### `PUT /projects/{public_id}/assets/{asset_id}`

Atualiza um asset do projeto.

#### `DELETE /projects/{public_id}/assets/{asset_id}`

Remove um asset do projeto.

