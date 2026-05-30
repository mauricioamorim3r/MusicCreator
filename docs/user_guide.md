# Guia rápido do AudioAgent

## Configuração de LLM

- `Provider`: escolhe qual IA vai escrever as análises textuais, como DNA, Blueprint, Prompt Suno e Auditoria.
- `Modelo`: define qual versão do provider será usada.
- `API Key`: é a chave da sua conta nesse provider.

### As configurações ficam salvas?

- `Provider`, `Modelo`, `Gerar análises com IA`, `Separação de voz e transcrição avançada`, `Nível de detalhe da estrutura` e campos de pesquisa ficam salvos localmente neste computador.
- A `API Key` só fica persistente se você marcar a opção para salvar localmente.

## Referências musicais e letra online

O `Mashup Matcher` cruza o BPM, a tonalidade e a chave Camelot da música analisada com um catálogo de músicas candidatas.

O campo `Fontes de pesquisa de músicas` serve para você registrar onde costuma buscar referências, por exemplo:

- playlists próprias
- canais de DJs
- blogs ou sites
- catálogos internos
- nomes de gravadoras ou labels

Essas fontes entram no relatório para documentar o contexto da análise e podem ser consideradas pelos agentes ao comentar os mashups.

## Copiloto Musical

O `Copiloto Musical` é um campo de perguntas dentro da aplicação. Ele usa a LLM configurada e pode trabalhar em quatro modos:

- `Responder sobre a análise atual`: explica métricas, estrutura, letra capturada, matcher e relatório aberto
- `Consultar histórico local`: procura análises antigas por música, artista, link ou ID
- `Comparar análises salvas`: compara até três rodadas selecionadas pelo usuário
- `Orientação musical geral`: responde dúvidas de produção, composição, canto e fluxo de trabalho

As conversas ficam salvas somente no banco local desta instalação.

### Captura de tela e arquivos

Dentro do Copiloto você também pode:

- clicar em `Capturar tela agora` para fotografar explicitamente a tela do computador
- revisar o preview antes de enviar a pergunta
- anexar imagens de telas do Suno, DAWs ou outras aplicações
- anexar TXT, Markdown, JSON, CSV, PDF, DOCX e XLSX para leitura orientada pela sua pergunta

A captura nunca acontece sozinha. Antes de enviar, feche ou oculte informações pessoais que não devem ser compartilhadas com o provider de LLM configurado.

### Limites de segurança

- O copiloto não executa comandos do computador.
- O copiloto não recebe acesso livre ao banco de dados: ele usa apenas consultas controladas pela aplicação.
- O copiloto não afirma que pesquisou na internet. Pesquisa web profunda com fontes verificáveis será adicionada como integração separada.
- Arquivos anexados são tratados como dados para análise, não como instruções executáveis.

## Token da API do Genius

O campo do Genius é opcional. Ele serve para melhorar a verificação online da letra quando o app tenta confirmar se a música encontrada realmente existe em uma base pública de letras.

Além do token, o app também aceita:

- `Genius Client ID`
- `Genius Client Secret`

Esses dois campos deixam a aplicação preparada para uma integração mais oficial com OAuth ou chamadas diretas futuras da API. Para a validação simples de letra que fazemos hoje, o item mais útil continua sendo o `Client Access Token`.

### Quando vale usar

- quando a validação automática por metadados não for suficiente
- quando você quiser uma segunda fonte de confirmação para letra e faixa
- quando a música tiver título muito genérico ou variações de nome

### Como obter

1. Abra o portal de developers do Genius.
2. Crie um `API Client`.
3. Gere um `Client Access Token`.
4. Cole esse token no campo do app.

Ao criar esse `API Client`, o Genius também mostra o `Client ID` e o `Client Secret` do seu app.

Links úteis:

- Developers: [https://genius.com/developers](https://genius.com/developers)
- Docs da API: [https://docs.genius.com/](https://docs.genius.com/)

Você não precisa implementar login completo no app para esse uso atual. O token já atende a nossa verificação de letra.

## Nível de detalhe da estrutura

O campo `Nível de detalhe da estrutura` controla em quantos blocos a música será dividida para leitura estrutural.

- `4 a 6`: visão mais geral, mais simples e mais rápida
- `8`: ponto de equilíbrio recomendado para a maioria das músicas
- `10 a 16`: visão mais detalhada, útil para arranjos com muitas transições

Em termos simples, quanto maior esse número, mais “fatiada” a música fica para o sistema tentar entender intro, build, drop, break e final.

## O que a separação de voz e transcrição avançada faz

Quando ativada, essa opção tenta usar dois recursos extras:

- `Demucs`: tenta separar a música em partes, como vocal, bateria, baixo e resto
- `WhisperX`: tenta transcrever a voz com marcação de tempo
- `Whisper` fallback: quando disponível, tenta gerar uma transcrição bruta mesmo sem alinhamento

Na prática isso ajuda em:

- entender melhor a letra
- melhorar a leitura de prosódia
- enriquecer o contexto para DNA, Blueprint e Prompt

Se esses recursos não estiverem disponíveis neste computador, o app faz fallback e continua sem quebrar.
Quando a transcrição sair como `rough`, leia como rascunho: ela pode ajudar no estudo e na prosódia, mas não deve ser tratada como letra oficial sem revisão.

## Tradução rápida dos blocos técnicos

- `DSP`: leitura matemática do áudio
- `DNA Instrumental`: descrição técnica do som, groove, peso, timbre e energia
- `Relatório Especialista`: leitura padronizada que separa medição, validação online, interpretação IA, hipótese de produção e incerteza
- `Blueprint`: mapa estrutural da música, seção por seção
- `Prompt Suno`: texto pronto para orientar geração musical no Suno
- `Auditoria`: checagem preventiva de originalidade e risco criativo
- `DAW & Mix`: orientações de mixagem e pós-produção

## Fluxo recomendado de uso

1. Carregue um arquivo ou cole um link.
2. Escolha se quer usar só análise local ou também agentes IA.
3. Se houver voz importante na música, teste com `Separação de voz e transcrição avançada`.
4. Comece com `8` em `Nível de detalhe da estrutura`.
5. Revise o relatório, o TXT e a verificação de letra antes de usar o resultado como base criativa.
