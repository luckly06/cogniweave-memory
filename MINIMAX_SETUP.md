# MiniMax 配置说明

当前工程的 `cogniweave_full/core/llm.py` 使用的是 OpenAI SDK 兼容方式，因此应使用下面这组配置：

- Provider: `minimax_openai_compat`
- Base URL: `https://api.minimaxi.com`
- Endpoint: `/v1/chat/completions`
- Model: `MiniMax-M2.7`

不要把 `MINIMAX_BASE_URL` 配成 `https://api.minimaxi.com/anthropic`，那是另一套兼容入口。

## Miniconda

创建环境：

```bash
cd /home/dd/dev/lab/03/process-accep/cogniweave_layered_impl/cogniweave_layered_impl
/home/dd/miniconda3/bin/conda env create -f environment.miniconda.yml
/home/dd/miniconda3/bin/conda init bash
source /home/dd/miniconda3/etc/profile.d/conda.sh
conda activate cogniweave-minimax
```

## 环境变量

项目根目录已经准备好 `.env`，直接加载即可。

如果你想手工检查：

```bash
cd /home/dd/dev/lab/03/process-accep/cogniweave_layered_impl/cogniweave_layered_impl
grep -E 'COGNIWEAVE_LLM_PROVIDER|MINIMAX_BASE_URL|MINIMAX_MODEL' .env
```

## 快速验证

```bash
cd /home/dd/dev/lab/03/process-accep/cogniweave_layered_impl/cogniweave_layered_impl
source /home/dd/miniconda3/etc/profile.d/conda.sh
conda activate cogniweave-minimax
python3 demo.py
```
