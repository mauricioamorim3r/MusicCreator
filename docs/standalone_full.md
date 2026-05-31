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

## Arquitetura do pacote

O pacote Windows usa duas camadas dentro da mesma pasta distribuivel:

- `AudioAgentDesktop.exe`: shell desktop com Streamlit, DSP, LLMs, ingestao, banco local e interface.
- `runtime\premium\python.exe`: runtime companheiro isolado para Demucs, WhisperX, Whisper, Torch e Torchaudio.

Essa separacao evita que o PyInstaller tente congelar recursivamente todo o ecossistema de machine learning. O aplicativo continua unico para o usuario, mas os motores pesados rodam como ferramentas Python normais.

## Gerar shell desktop

Durante desenvolvimento, gere apenas o shell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_standalone_full.ps1 -Clean -SkipInstall
```

Saida esperada:

```text
dist\AudioAgentDesktop\AudioAgentDesktop.exe
```

## Preparar runtime premium portatil

Monte o runtime apenas na primeira vez ou quando mudar `requirements-premium.txt`:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\setup_premium_runtime.ps1 -Force
```

O runtime reutilizavel fica em:

```text
.runtime\premium\
```

Anexe esse runtime ao shell ja gerado sem repetir o build:

```powershell
powershell -ExecutionPolicy Bypass -File scripts\bundle_premium_runtime.ps1
```

## Gerar pacote completo em um comando

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build_standalone_full.ps1 -Clean -PreparePremiumRuntime -BundlePremiumRuntime
```

Distribua a pasta inteira:

```text
dist\AudioAgentDesktop\
├── AudioAgentDesktop.exe
├── _internal\
└── runtime\
    └── premium\
```

O log do build fica em:

```text
logs\build_standalone_full.log
```

## Observacoes importantes

- O shell e o runtime premium sao reconstruidos separadamente para reduzir tempo de manutencao.
- O runtime premium pode ocupar alguns gigabytes por causa de Torch, Torchaudio, Demucs e WhisperX.
- A primeira execucao pode demorar porque modelos podem ser baixados/carregados pelas bibliotecas.
- Em algumas maquinas, antivirus pode analisar o executavel grande por bastante tempo.
- Para outro computador, copie a pasta inteira `dist\AudioAgentDesktop`, nunca apenas o `.exe`.
- FFmpeg e buscado primeiro no `PATH`; se nao existir, o app tenta `imageio-ffmpeg`.
- Para desenvolvimento local, o app tambem aceita `AUDIOAGENT_PREMIUM_PYTHON` apontando para um Python externo com os motores instalados.
