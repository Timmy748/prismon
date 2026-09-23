# Arquitetura

O Prismon é organizado como um **monólito modular**, no qual cada módulo
representa um domínio e possui responsabilidades e entidades próprias.

Essa organização busca permitir que o projeto cresça de forma organizada,
mantendo os domínios isolados e reduzindo o acoplamento e a complexidade
do sistema.

## Domínios

Atualmente, o Prismon é composto pelos seguintes domínios:

* **Identity**
* **Projects**
* **Agents**

## Comunicação entre domínios

Cada domínio deve expor uma **API pública**, definida no arquivo
`public_api.py` do respectivo módulo.

Quando um domínio precisar utilizar a API pública de outro domínio,
deverá fazê-lo por meio de um **client** próprio.

O client é responsável por:

* consumir a API pública do domínio;
* converter os dados recebidos em DTOs do próprio domínio.

Os clients devem estar localizados na pasta `clients/` e seguir a
convenção:

`client_<entity_name>.py`

Essa abordagem busca reduzir o acoplamento direto entre os domínios e
evitar que detalhes internos de um domínio sejam utilizados por outro.

## Comunicação entre camadas

Cada módulo deve possuir uma pasta `dtos/` contendo os objetos
utilizados na comunicação entre suas camadas.

Os DTOs são responsáveis por transportar dados entre componentes, como:

```text
Routes → Use Cases → Repositories
```

## Persistência de dados

Cada módulo deve possuir uma pasta `repositories/`, responsável pelo
acesso e persistência dos dados.

As demais camadas do módulo devem interagir com a persistência por meio
dos repositories, evitando que detalhes específicos da implementação do
banco de dados se espalhem pelo domínio.

```text
Use Case → Repository → Database
```

## Rotas da API

As rotas de cada módulo devem ser encapsuladas em uma função responsável
por:

1. receber ou injetar as dependências necessárias;
2. definir as rotas do módulo;
3. configurar os handlers;
4. retornar o router.

O router do módulo será posteriormente incluído na API principal,
definida em:

```text
src/main.py
```

Essa camada é responsável por lidar com as informações relacionadas ao
protocolo HTTP, incluindo:

* requisições;
* parâmetros;
* autenticação relacionada à requisição;
* serialização;
* códigos de status;
* respostas HTTP.

A camada de rotas não deve conter regras de negócio.

## Use Cases

Os use cases são responsáveis por executar os casos de uso da aplicação
e aplicar as regras de negócio necessárias para realizá-los.

Eles podem depender de:

* repositories, para persistência e acesso à base de dados;
* clients, para comunicação com outros domínios.

Os use cases recebem DTOs e outras informações fornecidas pelas camadas
externas, processam os dados e retornam os resultados necessários.

```text
Route
  ↓
Use Case
  ↓
Repository / Client
```

A camada de use cases não deve depender de detalhes relacionados ao
protocolo HTTP.

## Testes

Cada módulo possui sua própria pasta `tests/`.

Os testes devem ser organizados de acordo com o módulo ao qual pertencem,
mantendo os testes próximos ao contexto que estão validando.

## Estrutura de um módulo

```text
src/
└── module_name/
    ├── public_api.py
    ├── dtos/
    ├── routes/
    ├── use_cases/
    ├── repositories/
    ├── clients/
    └── tests/
```

