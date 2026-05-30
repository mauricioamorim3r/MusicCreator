# AudioAgent Desktop Full

Esta versao standalone foi preparada para Windows com todos os recursos do ambiente local:

- Streamlit embutido em um launcher desktop.
- DSP com Librosa.
- Ingestao por link com `yt-dlp` e FFmpeg.
- Separacao premium com Demucs.
- Transcricao premium com WhisperX.
- Fallback bruto com `openai-whisper`, quando instalado.
- Torch e Torchaudio.
- LLMs Anthropic, OpenAI e Gemini.
- Genius/LRCLIB.
- Banco local SQLite.
- Historico, configuracoes, cache, relatorios e arquivos gerados em pasta persistente.

## Pasta local de dados

Quando executado como desktop, o app usa:

```text
%LOCALAPPDATA%\AudioAgent
├── audioagent.db
├── .cache\
├── outputs\
└── logs\
```

O banco `audioagent.db` guarda:

- configuracoes do usuario;
- indice das analises;
- payload completo de cada analise;
- caminhos de relatorios e arquivos gerados.

Os arquivos pesados continuam no filesystem, e o banco guarda seus caminhos e metadados.

## Rodar em modo desktop pelo codigo-fonte

```powershell
powershell -ExecutionPolicy Bypass -File scripts\run_desktop_source.ps1
```

## Gerar executavel completo

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_standalone_full.ps1 -Clean
```

Saida esperada:

```text
dist\AudioAgentDesktop\AudioAgentDesktop.exe
```

O log do build fica em:

```text
logs\build_standalone_full.log
```

## Observacoes importantes

- O build completo pode ser muito grande por causa de Torch, Torchaudio, Demucs e WhisperX.
- A primeira execucao pode demorar porque modelos podem ser baixados/carregados pelas bibliotecas.
- Em algumas maquinas, antivirus pode analisar o executavel grande por bastante tempo.
- Se quiser distribuir para outro computador, teste a pasta inteira `dist\AudioAgentDesktop`, nao apenas o `.exe`, porque este spec usa modo `onedir` para reduzir riscos com bibliotecas pesadas.
- FFmpeg e buscado primeiro no `PATH`; se nao existir, o app tenta `imageio-ffmpeg`.
- Se o PyInstaller ficar travado coletando Torch/WhisperX por muitas horas, interrompa e rode novamente. O spec foi ajustado para coletar pacotes pesados de forma mais conservadora.
