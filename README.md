# AudioAgent v2 Foundation

Pipeline local para análise musical que combina ingestão por upload ou link, DSP com Librosa, matcher de mashups, recursos premium opcionais de voz e uma matriz de agentes IA com loop de auto-correção.

## O que já entrega

- Upload de áudio local ou ingestão por URL via `yt-dlp`
- Cache determinístico para uploads, links, stems e transcrições
- Análise DSP com BPM, tonalidade, Camelot, bandas espectrais, seções e curva RMS
- Matcher local de mashups com catálogo interno e heurística Camelot/BPM
- Separação de vocais com fallback seguro quando `demucs` não estiver disponível
- Transcrição best-effort: alinhada quando possível, bruta por segmento quando o alinhamento falha
- Loudness/LUFS, pico, crest factor, correlação estéreo e dinâmica aproximada
- Relatório Especialista v1 com matriz de evidências, separando medição, validação online, interpretação IA e hipótese de produção
- Downloads persistidos em `outputs/reports` para JSON/TXT e acesso a arquivos gerados
- Matriz de agentes multi-LLM com Anthropic, OpenAI ou Gemini:
  - DNA instrumental
  - DNA lírico opcional
  - blueprint estrutural
  - prompt Suno
  - auditoria de originalidade
  - auto-correção limitada por score
  - fallback automático entre LLMs configuradas
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
├── docs/
├── outputs/           # gerado localmente e ignorado pelo Git
├── .env.example
└── requirements.txt
```

## Rodando localmente

```bash
pip install -r requirements.txt
copy .env.example .env
streamlit run app.py
```

## Notas de runtime

- O alvo principal é Windows local com CPU.
- `ffmpeg` precisa estar no `PATH` para ingestão por link.
- `demucs` e `whisperx` são opcionais; quando não estiverem disponíveis, o app continua com fallback sem quebrar o fluxo.
- `openai-whisper` pode ser usado como fallback bruto de transcrição, quando instalado.
- O matcher usa catálogo local nesta fundação. A integração com Spotify fica para uma fase posterior.
- Não suba `.env`, `.cache`, `outputs` ou arquivos de áudio para o GitHub.
