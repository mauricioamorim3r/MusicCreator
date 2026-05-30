# AudioAgent v2 Foundation

Pipeline local para análise musical que combina ingestão por upload ou link, DSP com Librosa, matcher de mashups, recursos premium opcionais de voz e uma matriz de agentes IA com loop de auto-correção.

## O que já entrega

- Upload de áudio local ou ingestão por URL via `yt-dlp`
- Cache determinístico para uploads, links, stems e transcrições
- Análise DSP com BPM, tonalidade, Camelot, bandas espectrais, seções e curva RMS
- Matcher local de mashups com catálogo interno e heurística Camelot/BPM
- Separação de vocais com fallback seguro quando `demucs` não estiver disponível
- Transcrição alinhada com fallback seguro quando `whisperx` não estiver disponível
- Matriz de agentes multi-LLM com fallback entre OpenAI, Gemini e Anthropic:
  - DNA instrumental
  - DNA lírico opcional
  - blueprint estrutural
  - prompt Suno
  - auditoria de originalidade
  - auto-correção limitada por score
  - guia técnico de Suno/DAW

## Estrutura

```text
AppMusic/
├── app.py
├── core/
│   ├── agent_manager.py
│   ├── dsp_engine.py
│   └── matcher.py
├── services/
│   ├── audio_pipeline.py
│   ├── config.py
│   ├── models.py
│   ├── vocals_processor.py
│   └── web_ingest.py
├── knowledge_base/
│   ├── mashup_catalog.json
│   └── skills_templates.json
├── outputs/
├── .env.example
└── requirements.txt
```

## Rodando localmente

```bash
pip install -r requirements.txt
copy .env.example .env
streamlit run app.py
```

## Versão standalone completa

O projeto inclui preparação para executável Windows completo, com banco SQLite local em `%LOCALAPPDATA%\AudioAgent`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_desktop_source.ps1
```

Para gerar o executável:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_standalone_full.ps1 -Clean
```

Veja [docs/standalone_full.md](docs/standalone_full.md).

## Copiloto Musical

O painel `Copiloto Musical` permite conversar com a LLM configurada e executar ações seguras dentro da aplicação:

- explicar a análise aberta
- consultar o histórico SQLite local por título, artista, link ou ID
- comparar até três análises salvas
- responder dúvidas gerais de produção musical
- capturar a tela localmente após clique explícito do usuário
- analisar imagens, TXT, Markdown, JSON, CSV, PDF, DOCX e XLSX anexados

O copiloto não executa comandos do sistema nem SQL arbitrário. A captura de tela nunca ocorre automaticamente. Pesquisa web profunda com fontes verificáveis deve ser adicionada como integração externa separada.

## Deploy no Render

O repositório inclui um Blueprint `render.yaml` para deploy no Render:

```bash
pip install --upgrade pip && pip install -r requirements-render.txt
streamlit run app.py --server.address 0.0.0.0 --server.port $PORT --server.headless true
```

Use `requirements-render.txt` no Render para evitar instalar a pilha premium pesada (`demucs`, `whisperx`, `torch`, `torchaudio`) em um Web Service simples. Veja [docs/render_deploy.md](docs/render_deploy.md).

## Notas de runtime

- O alvo principal é Windows local com CPU.
- `ffmpeg` precisa estar no `PATH` para ingestão por link.
- `demucs` e `whisperx` são opcionais; quando não estiverem disponíveis, o app continua com fallback sem quebrar o fluxo.
- O matcher usa catálogo local nesta fundação. A integração com Spotify fica para uma fase posterior.
