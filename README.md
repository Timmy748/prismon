# Prismon

Prismon é um sistema web que disponibiliza workflows criativos baseados em agentes de IA.

## Sobre

O objetivo do projeto é oferecer uma plataforma na qual designers possam anexar
documentos e assets de uma marca, como tom e voz, ICP, imagens, logotipo, 
guia de identidade visual, entre outros.

Esses materiais fornecem contexto para os workflows de LLMs, permitindo a 
geração de assets mais alinhados à identidade da marca e apoiando a etapa de 
exploração criativa.

A proposta é reduzir o trabalho operacional e permitir que designers tenham 
mais tempo para escolher, avaliar e refinar os materiais gerados.

## Documentação

A documentação técnica e as decisões de projeto estão em [`docs/`](./docs).

## Provedor de LLM

O Prismon usa Ollama por padrão. Para usar a OpenRouter, configure estas
variáveis no `.env`:

```dotenv
LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sua-chave
OPENROUTER_MODEL=provedor/modelo
OPENROUTER_TEMPERATURE=0.0
```

`OPENROUTER_MODEL` deve ser um identificador disponível no catálogo da
OpenRouter. A chave e o modelo são obrigatórios quando esse provedor está
selecionado. Para voltar ao Ollama, use `LLM_PROVIDER=ollama` ou remova a
configuração do provedor, que por padrão é Ollama.
