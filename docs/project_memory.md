# AudioAgent v2 - Memoria de Projeto

Ultima consolidacao: 2026-05-26

Este documento registra o contexto acumulado do projeto AudioAgent v2 para evitar perda de memoria entre rodadas. Ele nao deve guardar senhas, tokens, client secrets ou chaves de API.

## 1. Regra central definida pelo usuario

- Nao inventar informacoes.
- Nao inferir como fato.
- Separar claramente o que foi medido, o que foi validado online, o que veio de fonte externa e o que e interpretacao de IA.
- Antes de implementar mudancas grandes, ler, entender e consolidar as analises recebidas.
- A aplicacao deve evoluir como laboratorio musical rastreavel, nao apenas como gerador de texto bonito.

## 2. Pasta e estado da aplicacao

- Pasta principal: `C:\appsMau\AppMusic`
- UI: Streamlit em `app.py`
- Core DSP preservado em `core/dsp_engine.py`
- Orquestracao de agentes em `core/agent_manager.py`
- Pipeline principal em `services/audio_pipeline.py`
- Ingestao web em `services/web_ingest.py`
- Separacao/transcricao em `services/vocals_processor.py`
- Backends LLM em `services/llm_backends.py`
- Historico tecnico em `services/history_store.py`
- Configuracoes locais em `.cache/user_settings.json`
- Historico persistente em `.cache/history`

## 3. O que a aplicacao ja faz

- Aceita upload local de audio.
- Aceita link suportado e baixa/normaliza audio via `yt-dlp` e `ffmpeg`.
- Roda analise DSP com `librosa`.
- Mede BPM, tonalidade aproximada, Camelot, energia espectral, RMS, flatness, zero crossing, largura espectral e secoes por energia.
- Roda matcher local de mashup com catalogo interno.
- Tenta separar vocal/instrumental com Demucs quando a opcao avancada esta ligada.
- Tenta transcrever vocal com WhisperX quando ha vocal separado e suporte local.
- Valida letra/faixa online com LRCLIB, Genius API e `lyricsgenius`, quando possivel.
- Gera relatorio em JSON e TXT.
- Mantem historico tecnico reservado.
- Mostra status de runtime e tempos por etapa.
- Suporta LLMs Anthropic, OpenAI e Gemini.
- Tem fallback automatico de LLM por provider e por modelo.
- Preserva analise local se a matriz de agentes falhar.
- Usa cache para ingestao, stems, transcricoes e DSP.

## 4. Correcoes importantes ja realizadas

- Imports e estrutura foram normalizados em pacotes.
- `float32`/NumPy foi tratado para nao quebrar JSON.
- Erros brutos de LLM foram suavizados.
- Falha de OpenAI `403 model_not_found` passou a acionar fallback.
- Defaults mais estaveis foram definidos:
  - OpenAI: `gpt-4o-mini`
  - Gemini: `gemini-2.5-flash`
- Modelos mais novos continuam disponiveis, mas nao devem ser presumidos como acessiveis.
- Se agentes falharem, o pipeline fecha como `completed_with_warnings` e mantem DSP/matcher/transcricao/historico.
- Cache de DSP reduziu nova tentativa da mesma musica de cerca de 117s para cerca de 0,08s no teste local.
- Primeira fatia pos-analises implementada: area de arquivos gerados, diagnostico premium e loudness/LUFS.

## 5. Pontos sensiveis e limites atuais

- Separacao de voz e real quando Demucs roda, mas pode falhar ou gerar vocal com vazamento.
- Transcricao por WhisperX e real, mas musica cantada pode sair vazia, errada ou parcial.
- O app ainda precisa expor melhor ao usuario os arquivos gerados:
  - vocal separado
  - instrumental/no vocals
  - transcricao TXT/JSON
- Atualizacao: uma aba de arquivos gerados foi adicionada para expor downloads quando esses artefatos existem.
- O DSP inicial de uma musica nova ainda pode ser pesado.
- A UI ja mostra tempos por etapa, mas ainda pode explicar melhor onde ficou lento.
- Letras online devem ser tratadas com cuidado juridico. Preferir fonte licenciada ou parafrase.
- Nunca expor credenciais Genius, OpenAI, Gemini ou Anthropic em tela/logs/exportacoes.

## 6. Evidencia por tipo de afirmacao

Toda saida futura deve tentar marcar origem e confianca:

- `medido_no_audio`: BPM, duracao, RMS, espectro, loudness, secoes, energia, picos.
- `detectado_por_modelo`: stems, voz, transcricao, possivel instrumento, tags de mood.
- `validado_online`: titulo, artista, gravadora, data, Beatport, MusicBrainz, ACRCloud, AudD, Genius, LRCLIB.
- `interpretacao_ia`: catarse, euforia, redencao, narrativa, arquétipo, funcao emocional.
- `hipotese_producao`: sidechain, shimmer, supersaw, close miking, plugin, biblioteca de samples, cortes de EQ.
- `nao_permitido_ou_restrito`: copiar letra integral protegida obtida de fontes online sem licenca.

## 7. Aprendizados das analises externas

### Like a Prayer - versao cinematica/orquestral

Aprendizados uteis:

- Relatorio deve diferenciar fato comprovavel, analise interpretativa e hipotese.
- Para faixa cinematica/orquestral, a rubrica deve falar de:
  - dramaturgia
  - arco emocional
  - coro
  - cordas
  - metais
  - percussao cinematica
  - dinamica de atos
  - contraste entre intimidade vocal e climax
- Muitas afirmacoes tecnicas sao hipoteses sem medicao:
  - Neumann U87
  - shimmer reverb de 4 a 6s
  - sidechain invisivel
  - Spitfire/EastWest
  - Cimbasso
  - sub-boom 30-40Hz
- O app deve formular isso como "hipotese de producao" quando nao houver medicao direta.

### Set Me Free - Armin van Buuren & SACHA

Arquivo citado pelo usuario:

- `C:\Users\mauri\Downloads\Armin van Buuren, Sacha - Set Me Free (Extended Mix).mp3`

Aprendizados uteis:

- Para EDM/trance, a rubrica deve ser diferente da cinematica.
- Termos estruturais importantes:
  - DJ intro
  - break vocal
  - breakdown
  - pre-build
  - build-up
  - pre-drop
  - drop
  - segundo drop
  - outro mixavel
  - tail final
- Termos de producao relevantes:
  - kick 4/4
  - rolling bassline
  - supersaw
  - vocal chops
  - sidechain/pumping
  - white noise sweeps
  - filtros low-pass/high-pass
  - snare roll
  - leads trance
- O app deve tratar esses termos como comprovaveis apenas quando houver recurso que sustente a deteccao.
- A letra deve preferir parafrase analitica quando vier de fonte online protegida.
- Se a transcricao vier do arquivo enviado pelo usuario, pode ser tratada como resultado tecnico local, mas ainda precisa de cuidado na exportacao e uso.

## 8. Ideias de evolucao aprovadas conceitualmente, ainda nao implementadas

### Rastreabilidade de afirmacoes

Criar um modelo de saida onde cada bloco venha com:

- afirmacao
- origem
- confianca
- evidencia usada
- risco de interpretacao

### Relatorio estruturado por schema

Usar Structured Outputs ou validacao JSON equivalente para produzir relatorios consistentes:

- identificacao
- audio_dna
- harmonic_dna
- rhythmic_dna
- vocal_dna
- lyrical_dna
- production_dna
- emotional_arc
- performance_map
- confidence_by_section
- uncertainties

### Rubricas por genero

Criar rubricas especializadas:

- EDM / Trance / Progressive
- Cinematic / Orchestral / Trailer
- Pop / Rock
- Gospel / Choir
- Generic fallback

### Mapa de Navegacao de Performance

Saida por tempo/seção:

- timestamp
- funcao da secao
- vocal/performance
- producao/efeitos
- instrumental/levada
- energia
- confianca
- evidencias

### Melhorias tecnicas de audio

Possiveis adicoes futuras:

- `pyloudnorm` para LUFS, Loudness Range e dinamica.
- `ffprobe` para metadados, codec, duracao, loudness quando aplicavel.
- `Essentia` para descritores profissionais e modelos de mood/instrumentacao.
- `Basic Pitch` para melodia/MIDI aproximado quando fizer sentido.
- ACRCloud ou AudD para fingerprint e identificacao musical.
- MusicBrainz para metadados abertos.
- LyricFind/Musixmatch para letras licenciadas.
- APIs comerciais de stems como Music.ai, LALAL.AI ou AudioShake como alternativa a Demucs local.

## 9. Decisoes legais e de produto pendentes

- Definir politica de uso de links YouTube/SoundCloud:
  - apenas identificacao/metadados
  - download permitido sob responsabilidade/autorizacao do usuario
  - ou bloquear download em modo comercial
- Definir politica de exibicao/exportacao de letras:
  - transcricao local
  - fonte licenciada
  - parafrase
  - trecho curto
- Definir se Genius/LRCLIB ficam apenas como validacao ou tambem como fonte de conteudo.

## 10. Proximos passos recomendados quando o usuario autorizar

1. Expor stems e transcricoes na UI com botoes de download.
2. Melhorar mensagens quando transcricao nao for gerada, mostrando motivo e caminho dos arquivos.
3. Adicionar LUFS/Loudness Range/True Peak com `pyloudnorm` e/ou `ffmpeg`.
4. Criar `evidence model` para marcar origem/confianca das afirmacoes.
5. Ajustar prompts/skills para rubricas por genero.
6. Criar mapa de performance por timeline.
7. Avaliar identificacao musical com MusicBrainz primeiro e ACRCloud/AudD como opcao paga/API.
8. Otimizar primeira execucao do DSP em musicas novas.

## 12. Fatia implementada apos consolidacao das analises

- `services/loudness_analyzer.py` calcula sample peak, RMS dBFS, crest factor, correlacao estereo, proxy de range e LUFS integrado quando `pyloudnorm` esta instalado.
- Loudness tambem possui cache local em `.cache/loudness`.
- `requirements.txt` inclui `pyloudnorm>=0.1.1`.
- O pipeline registra a etapa `loudness` e inclui o resultado no relatorio JSON/TXT.
- A UI mostra loudness na aba de metricas DSP.
- A UI ganhou aba de arquivos gerados com diagnostico de stems/transcricao/validacao e downloads de mix, vocal, instrumental e transcricao quando disponiveis.
- Foi criada a camada `Relatorio Especialista v1` em `services/specialist_report.py`, com identificacao, dados medidos, rubrica de leitura, estrutura por tempo, DNA musical/vocal/producao, veredito e matriz de evidencias.
- O relatorio especialista e deterministico e nao depende de LLM; saidas de agentes entram como `interpretacao_ia`, nao como fato medido.
- A transcricao foi ajustada para modo best-effort: se o WhisperX gerar texto mas falhar no alinhamento, o app entrega transcricao `rough` por segmentos em vez de descartar tudo.
- Cache antigo de transcricao vazia nao deve bloquear nova tentativa; cache com texto continua sendo reaproveitado.
- A aba `Arquivos Gerados` agora renderiza cards com player de audio, tamanho, status, caminho tecnico e botao de download para mix, vocal, instrumental e JSON de transcricao quando os arquivos existem no cache.
- Downloads de relatorios foram reforcados: agora sao salvos em `outputs/reports`, os botoes usam arquivos reais, chaves explicitas e `on_click="ignore"` para evitar rerun no navegador interno.

## 11. Observacoes de seguranca

- Nao registrar API keys, senhas, client secrets ou tokens neste documento.
- O Genius foi configurado localmente antes, mas os valores nao devem ser expostos.
- Se credenciais forem compartilhadas em conversa, recomendar troca de senha/chave.
