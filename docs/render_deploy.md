# Deploy no Render

Este projeto esta preparado para deploy Git-backed no Render usando Blueprint.

## Arquivos importantes

- `render.yaml`: define o Web Service no Render.
- `requirements-render.txt`: dependencias leves para cloud, sem Demucs/WhisperX/Torch.
- `.python-version`: fixa Python `3.11.11` para evitar incompatibilidades com pacotes de audio.
- `.env.example`: lista as variaveis que podem ser configuradas no painel do Render.

## Por que existe `requirements-render.txt`

O app local pode usar Demucs, WhisperX, Torch e Torchaudio para separacao/transcricao premium. Esses pacotes sao pesados para deploy cloud simples e podem quebrar o build em planos pequenos. No Render, a versao cloud mantém:

- upload de audio;
- ingestao por link com `yt-dlp`;
- FFmpeg via `imageio-ffmpeg`;
- DSP com Librosa;
- loudness/LUFS;
- matcher local;
- relatorios JSON/TXT;
- LLMs Anthropic, OpenAI e Gemini;
- validacao Genius/LRCLIB quando configurada.

A separacao premium local continua como recurso do ambiente Windows/local.

## Como criar pelo Render

1. Acesse o Render Dashboard.
2. Crie um novo Blueprint.
3. Conecte o repositório `mauricioamorim3r/MusicCreator`.
4. Confirme o `render.yaml`.
5. Configure as variaveis secretas desejadas:
   - `OPENAI_API_KEY`
   - `ANTHROPIC_API_KEY`
   - `GEMINI_API_KEY` ou `GOOGLE_API_KEY`
   - `GENIUS_ACCESS_TOKEN`
6. Faça o deploy.

## Comandos usados pelo Render

Build:

```bash
pip install --upgrade pip && pip install -r requirements-render.txt
```

Start:

```bash
streamlit run app.py --server.address 0.0.0.0 --server.port $PORT --server.headless true --server.enableCORS false --server.enableXsrfProtection false
```

## Observacoes

- O filesystem do Render e efemero em servicos sem disco persistente. Relatorios e caches existem durante o ciclo do container, mas nao devem ser tratados como armazenamento definitivo.
- Para processamento pesado de voz/stems na nuvem, crie uma versao separada com worker, disco persistente e plano maior, ou use uma API externa de stems/transcricao.
- Links de plataformas externas devem respeitar direitos de uso e autorizacao do usuario.
