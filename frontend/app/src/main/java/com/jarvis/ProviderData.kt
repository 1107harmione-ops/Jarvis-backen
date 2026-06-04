package com.jarvis

import com.google.gson.annotations.SerializedName

enum class ApiFormat(val label: String) {
    @SerializedName("openai_compat") OPENAI_COMPAT("OpenAI Compatible"),
    @SerializedName("anthropic") ANTHROPIC("Anthropic (Claude)"),
    @SerializedName("google") GOOGLE("Google (Gemini)"),
    @SerializedName("local") LOCAL("Local (Offline)"),
    @SerializedName("cohere") COHERE("Cohere"),
    @SerializedName("replicate") REPLICATE("Replicate"),
    @SerializedName("huggingface") HUGGINGFACE("HuggingFace"),
}

data class Model(
    val id: String,
    val name: String,
    val isFree: Boolean = false,
    val description: String = "",
)

data class AiProvider(
    val id: String,
    val name: String,
    @SerializedName("api_format") val apiFormat: ApiFormat,
    @SerializedName("base_url") val baseUrl: String,
    @SerializedName("default_model") val defaultModel: String,
    val models: List<Model>,
    var apiKey: String = "",
    var enabled: Boolean = false,
    @SerializedName("is_custom") val isCustom: Boolean = false,
)

object ProviderDefaults {
    val PRESETS: List<AiProvider> = listOf(
        // ── OpenAI-Compatible Providers ──
        AiProvider("openai", "OpenAI", ApiFormat.OPENAI_COMPAT,
            "https://api.openai.com/v1", "gpt-4o", listOf(
            Model("gpt-4o", "GPT-4o", description = "Most capable GPT-4 model"),
            Model("gpt-4o-mini", "GPT-4o Mini", description = "Fast, affordable GPT-4"),
            Model("gpt-4-turbo", "GPT-4 Turbo", description = "Previous gen GPT-4"),
            Model("gpt-3.5-turbo", "GPT-3.5 Turbo", isFree = true, description = "Fast & cheap"),
            Model("o1", "o1", description = "Reasoning model"),
            Model("o1-mini", "o1 Mini", description = "Fast reasoning model"),
            Model("o3-mini", "o3 Mini", description = "Latest reasoning"),
        )),
        AiProvider("groq", "Groq", ApiFormat.OPENAI_COMPAT,
            "https://api.groq.com/openai/v1", "llama-3.3-70b-versatile", listOf(
            Model("llama-3.3-70b-versatile", "Llama 3.3 70B", isFree = true, description = "Fastest Llama"),
            Model("llama-3.1-8b-instant", "Llama 3.1 8B", isFree = true, description = "Ultra fast"),
            Model("mixtral-8x7b-32768", "Mixtral 8x7B", isFree = true, description = "Mistral MoE"),
            Model("gemma2-9b-it", "Gemma 2 9B", isFree = true, description = "Google open model"),
            Model("deepseek-r1-distill-llama-70b", "DeepSeek R1 70B", isFree = true, description = "Reasoning"),
        )),
        AiProvider("openrouter", "OpenRouter", ApiFormat.OPENAI_COMPAT,
            "https://openrouter.ai/api/v1", "auto", listOf(
            Model("auto", "Auto (Cheapest)", isFree = true, description = "Routes to cheapest model"),
            Model("openai/gpt-4o", "GPT-4o", description = "OpenAI via OpenRouter"),
            Model("openai/gpt-4o-mini", "GPT-4o Mini", isFree = true, description = "Cheap GPT-4"),
            Model("anthropic/claude-3.5-sonnet", "Claude 3.5 Sonnet", description = "Best for coding"),
            Model("google/gemini-2.0-flash-001", "Gemini 2.0 Flash", isFree = true, description = "Fast Google"),
            Model("meta-llama/llama-3.3-70b-instruct", "Llama 3.3 70B", isFree = true, description = "Meta open model"),
            Model("deepseek/deepseek-r1", "DeepSeek R1", description = "Reasoning model"),
            Model("mistralai/mistral-large", "Mistral Large", description = "Mistral flagship"),
            Model("qwen/qwen-2.5-72b-instruct", "Qwen 2.5 72B", isFree = true, description = "Alibaba open model"),
        )),
        AiProvider("together", "Together AI", ApiFormat.OPENAI_COMPAT,
            "https://api.together.xyz/v1", "meta-llama/Llama-3.3-70B-Instruct-Turbo", listOf(
            Model("meta-llama/Llama-3.3-70B-Instruct-Turbo", "Llama 3.3 70B", description = "Meta flagship"),
            Model("meta-llama/Llama-3.2-11B-Vision-Instruct-Turbo", "Llama 3.2 11B Vision", description = "Vision model"),
            Model("mistralai/Mixtral-8x22B-Instruct-v0.1", "Mixtral 8x22B", description = "Mistral MoE"),
            Model("deepseek-ai/DeepSeek-R1", "DeepSeek R1", description = "Reasoning"),
            Model("Qwen/Qwen2.5-72B-Instruct-Turbo", "Qwen 2.5 72B", description = "Alibaba"),
        )),
        AiProvider("deepseek", "DeepSeek", ApiFormat.OPENAI_COMPAT,
            "https://api.deepseek.com/v1", "deepseek-chat", listOf(
            Model("deepseek-chat", "DeepSeek V3", description = "Latest chat model"),
            Model("deepseek-reasoner", "DeepSeek R1", description = "Reasoning model"),
        )),
        AiProvider("fireworks", "Fireworks AI", ApiFormat.OPENAI_COMPAT,
            "https://api.fireworks.ai/inference/v1", "accounts/fireworks/models/llama-v3p3-70b-instruct", listOf(
            Model("accounts/fireworks/models/llama-v3p3-70b-instruct", "Llama 3.3 70B", description = "Meta open"),
            Model("accounts/fireworks/models/llama-v3p2-90b-vision-instruct", "Llama 3.2 90B Vision", description = "Vision"),
            Model("accounts/fireworks/models/deepseek-r1", "DeepSeek R1", description = "Reasoning"),
            Model("accounts/fireworks/models/mixtral-8x22b-instruct", "Mixtral 8x22B", description = "Mistral"),
        )),
        AiProvider("perplexity", "Perplexity", ApiFormat.OPENAI_COMPAT,
            "https://api.perplexity.ai", "sonar-pro", listOf(
            Model("sonar-pro", "Sonar Pro", description = "With web search"),
            Model("sonar", "Sonar", description = "Fast with web search"),
            Model("sonar-deep-research", "Sonar Deep Research", description = "Deep research"),
        )),
        AiProvider("xai", "xAI (Grok)", ApiFormat.OPENAI_COMPAT,
            "https://api.x.ai/v1", "grok-2", listOf(
            Model("grok-2", "Grok 2", description = "Latest Grok"),
            Model("grok-2-mini", "Grok 2 Mini", description = "Fast Grok"),
        )),
        AiProvider("mistral", "Mistral AI", ApiFormat.OPENAI_COMPAT,
            "https://api.mistral.ai/v1", "mistral-large-latest", listOf(
            Model("mistral-large-latest", "Mistral Large", description = "Flagship model"),
            Model("mistral-small-latest", "Mistral Small", isFree = true, description = "Fast & cheap"),
            Model("codestral-latest", "Codestral", description = "Code generation"),
            Model("open-mistral-nemo", "Mistral Nemo", isFree = true, description = "Open model"),
        )),
        AiProvider("deepinfra", "DeepInfra", ApiFormat.OPENAI_COMPAT,
            "https://api.deepinfra.com/v1/openai", "meta-llama/Llama-3.3-70B-Instruct-Turbo", listOf(
            Model("meta-llama/Llama-3.3-70B-Instruct-Turbo", "Llama 3.3 70B", isFree = true, description = "Meta open"),
            Model("mistralai/Mixtral-8x22B-Instruct-v0.1", "Mixtral 8x22B", description = "Mistral"),
            Model("deepseek-ai/DeepSeek-R1", "DeepSeek R1", description = "Reasoning"),
            Model("Qwen/Qwen2.5-72B-Instruct", "Qwen 2.5 72B", description = "Alibaba"),
        )),
        AiProvider("lepton", "Lepton AI", ApiFormat.OPENAI_COMPAT,
            "https://api.lepton.ai/v1", "llama3-70b", listOf(
            Model("llama3-70b", "Llama 3 70B", description = "Meta model"),
            Model("mixtral-8x22b", "Mixtral 8x22B", description = "Mistral"),
        )),
        AiProvider("octoai", "OctoAI", ApiFormat.OPENAI_COMPAT,
            "https://text.octoai.run/v1", "meta-llama-3.1-70b-instruct", listOf(
            Model("meta-llama-3.1-70b-instruct", "Llama 3.1 70B", description = "Meta"),
            Model("mistral-7b-instruct", "Mistral 7B", isFree = true, description = "Fast small model"),
        )),
        AiProvider("azure", "Azure OpenAI", ApiFormat.OPENAI_COMPAT,
            "https://YOUR_RESOURCE.openai.azure.com", "gpt-4o", listOf(
            Model("gpt-4o", "GPT-4o", description = "OpenAI via Azure"),
            Model("gpt-4o-mini", "GPT-4o Mini", description = "Cheaper GPT-4"),
            Model("gpt-4", "GPT-4", description = "Previous gen"),
        )),

        // ── Anthropic ──
        AiProvider("anthropic", "Anthropic (Claude)", ApiFormat.ANTHROPIC,
            "https://api.anthropic.com/v1", "claude-sonnet-4-20250514", listOf(
            Model("claude-sonnet-4-20250514", "Claude Sonnet 4", description = "Latest Claude"),
            Model("claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet", description = "Best for coding"),
            Model("claude-3-5-haiku-20241022", "Claude 3.5 Haiku", description = "Fast Claude"),
            Model("claude-3-opus-20240229", "Claude 3 Opus", description = "Most capable Claude 3"),
        )),

        // ── Google ──
        AiProvider("google", "Google Gemini", ApiFormat.GOOGLE,
            "https://generativelanguage.googleapis.com", "gemini-2.0-flash", listOf(
            Model("gemini-2.0-flash", "Gemini 2.0 Flash", isFree = true, description = "Fastest Gemini"),
            Model("gemini-2.0-flash-lite", "Gemini 2.0 Flash Lite", isFree = true, description = "Cheapest Gemini"),
            Model("gemini-1.5-pro", "Gemini 1.5 Pro", description = "Most capable Gemini 1.5"),
            Model("gemini-1.5-flash", "Gemini 1.5 Flash", isFree = true, description = "Fast Gemini 1.5"),
            Model("gemini-2.5-pro-exp-03-25", "Gemini 2.5 Pro", description = "Latest reasoning"),
        )),

        // ── Cohere ──
        AiProvider("cohere", "Cohere", ApiFormat.COHERE,
            "https://api.cohere.ai/v1", "command-r-plus", listOf(
            Model("command-r-plus", "Command R+", description = "Best for RAG"),
            Model("command-r", "Command R", description = "Balanced"),
            Model("command-r7b", "Command R 7B", isFree = true, description = "Lightweight"),
        )),

        // ── Replicate ──
        AiProvider("replicate", "Replicate", ApiFormat.REPLICATE,
            "https://api.replicate.com/v1", "meta/meta-llama-3-70b-instruct", listOf(
            Model("meta/meta-llama-3-70b-instruct", "Llama 3 70B", description = "Meta via Replicate"),
            Model("mistralai/mixtral-8x22b-instruct-v0.1", "Mixtral 8x22B", description = "Mistral"),
            Model("deepseek-ai/deepseek-r1", "DeepSeek R1", description = "Reasoning"),
        )),

        // ── HuggingFace ──
        AiProvider("huggingface", "HuggingFace Inference", ApiFormat.HUGGINGFACE,
            "https://api-inference.huggingface.co/models", "meta-llama/Llama-3.3-70B-Instruct", listOf(
            Model("meta-llama/Llama-3.3-70B-Instruct", "Llama 3.3 70B", isFree = true, description = "Meta via HF"),
            Model("mistralai/Mixtral-8x22B-Instruct-v0.1", "Mixtral 8x22B", isFree = true, description = "Mistral"),
            Model("Qwen/Qwen2.5-72B-Instruct", "Qwen 2.5 72B", isFree = true, description = "Alibaba"),
            Model("google/gemma-2-27b-it", "Gemma 2 27B", isFree = true, description = "Google"),
        )),

        // ── AWS Bedrock ──
        AiProvider("aws-bedrock", "AWS Bedrock", ApiFormat.OPENAI_COMPAT,
            "https://bedrock-runtime.YOUR_REGION.amazonaws.com", "anthropic.claude-3-5-sonnet", listOf(
            Model("anthropic.claude-3-5-sonnet-20241022-v2:0", "Claude 3.5 Sonnet v2", description = "Via AWS"),
            Model("anthropic.claude-3-opus-20240229-v1:0", "Claude 3 Opus", description = "Via AWS"),
            Model("meta.llama3-70b-instruct-v1:0", "Llama 3 70B", description = "Via AWS"),
        )),

        // ── GCP Vertex AI ──
        AiProvider("gcp-vertex", "GCP Vertex AI", ApiFormat.GOOGLE,
            "https://YOUR_PROJECT.REGION.aiplatform.googleapis.com", "gemini-1.5-pro", listOf(
            Model("gemini-1.5-pro", "Gemini 1.5 Pro", description = "Via GCP"),
            Model("gemini-1.5-flash", "Gemini 1.5 Flash", description = "Via GCP"),
            Model("claude-3-5-sonnet@20241022", "Claude 3.5 Sonnet", description = "Via GCP"),
        )),

        // ── Additional OpenAI-Compatible ──
        AiProvider("ai21", "AI21 Labs", ApiFormat.OPENAI_COMPAT,
            "https://api.ai21.com/studio/v1", "jamba-1.5-large", listOf(
            Model("jamba-1.5-large", "Jamba 1.5 Large", description = "AI21 flagship"),
            Model("jamba-1.5-mini", "Jamba 1.5 Mini", description = "Fast AI21"),
        )),
        AiProvider("nvidia", "NVIDIA NIM", ApiFormat.OPENAI_COMPAT,
            "https://integrate.api.nvidia.com/v1", "meta/llama-3.3-70b-instruct", listOf(
            Model("meta/llama-3.3-70b-instruct", "Llama 3.3 70B", description = "Via NVIDIA"),
            Model("mistralai/mixtral-8x22b-instruct-v0.1", "Mixtral 8x22B", description = "Via NVIDIA"),
        )),
        AiProvider("sambanova", "SambaNova", ApiFormat.OPENAI_COMPAT,
            "https://api.sambanova.ai/v1", "Meta-Llama-3.3-70B-Instruct", listOf(
            Model("Meta-Llama-3.3-70B-Instruct", "Llama 3.3 70B", isFree = true, description = "Fast inference"),
            Model("Qwen2.5-72B-Instruct", "Qwen 2.5 72B", isFree = true, description = "Alibaba"),
        )),
        AiProvider("inferless", "Inferless", ApiFormat.OPENAI_COMPAT,
            "https://api.inferless.com/v1", "meta-llama-3-70b-instruct", listOf(
            Model("meta-llama-3-70b-instruct", "Llama 3 70B", description = "Serverless"),
        )),
        AiProvider("anyscale", "Anyscale", ApiFormat.OPENAI_COMPAT,
            "https://api.endpoints.anyscale.com/v1", "meta-llama/Llama-3.3-70B-Instruct", listOf(
            Model("meta-llama/Llama-3.3-70B-Instruct", "Llama 3.3 70B", description = "Via Anyscale"),
        )),
        AiProvider("modal", "Modal", ApiFormat.OPENAI_COMPAT,
            "https://YOUR_MODAL--modal-labs-api-server.modal.run/v1", "llama3-70b", listOf(
            Model("llama3-70b", "Llama 3 70B", description = "Self-hosted on Modal"),
        )),
        AiProvider("runpod", "RunPod", ApiFormat.OPENAI_COMPAT,
            "https://YOUR_POD_ID-5000.proxy.runpod.net/v1", "llama3-70b", listOf(
            Model("llama3-70b", "Llama 3 70B", description = "Self-hosted on RunPod"),
        )),
        AiProvider("togetherai", "Together (Free)", ApiFormat.OPENAI_COMPAT,
            "https://api.together.xyz/v1", "meta-llama/Llama-3.2-3B-Instruct-Turbo", listOf(
            Model("meta-llama/Llama-3.2-3B-Instruct-Turbo", "Llama 3.2 3B", isFree = true, description = "Tiny & free"),
            Model("mistralai/Mistral-7B-Instruct-v0.3", "Mistral 7B", isFree = true, description = "Open model"),
        )),

        // ── Free / Community Models ──
        AiProvider("free-local", "Local (Offline)", ApiFormat.LOCAL,
            "", "local-default", listOf(
            Model("local-default", "Default Local", isFree = true, description = "Canned responses + KB"),
            Model("local-reasoning", "Local Reasoning", isFree = true, description = "Pattern matching + RAG"),
        )),

        // ── More OpenAI-Compatible: Smaller / Regional ──
        AiProvider("forefront", "Forefront", ApiFormat.OPENAI_COMPAT,
            "https://forefront.com/api/v1", "gpt-4o-mini", listOf(
            Model("gpt-4o-mini", "GPT-4o Mini", description = "Via Forefront"),
            Model("gpt-4o", "GPT-4o", description = "Via Forefront"),
        )),
        AiProvider("natdev", "NativeDevelop", ApiFormat.OPENAI_COMPAT,
            "https://api.nat.dev/v1", "gpt-4o-mini", listOf(
            Model("gpt-4o-mini", "GPT-4o Mini", description = "Via Nat.dev"),
        )),
        AiProvider("shuttle", "Shuttle AI", ApiFormat.OPENAI_COMPAT,
            "https://api.shuttle.ai/v1", "gpt-4o-mini", listOf(
            Model("gpt-4o-mini", "GPT-4o Mini", description = "Via Shuttle"),
        )),

        // ── Self-Hosted Options ──
        AiProvider("vllm-local", "vLLM (Local)", ApiFormat.OPENAI_COMPAT,
            "http://127.0.0.1:8000/v1", "local-model", listOf(
            Model("local-model", "Custom vLLM model", isFree = true, description = "Self-hosted vLLM"),
        )),
        AiProvider("ollama-local", "Ollama (Local)", ApiFormat.OPENAI_COMPAT,
            "http://127.0.0.1:11434/v1", "llama3.2", listOf(
            Model("llama3.2", "Llama 3.2", isFree = true, description = "Local via Ollama"),
            Model("llama3.1", "Llama 3.1", isFree = true, description = "Local via Ollama"),
            Model("mistral", "Mistral", isFree = true, description = "Local via Ollama"),
            Model("gemma2", "Gemma 2", isFree = true, description = "Local via Ollama"),
            Model("deepseek-r1", "DeepSeek R1", isFree = true, description = "Local via Ollama"),
            Model("qwen2.5", "Qwen 2.5", isFree = true, description = "Local via Ollama"),
        )),
        AiProvider("lmstudio-local", "LM Studio (Local)", ApiFormat.OPENAI_COMPAT,
            "http://127.0.0.1:1234/v1", "local-model", listOf(
            Model("local-model", "LM Studio model", isFree = true, description = "Local via LM Studio"),
        )),
        AiProvider("localai", "LocalAI", ApiFormat.OPENAI_COMPAT,
            "http://127.0.0.1:8080/v1", "ggml-gpt4", listOf(
            Model("ggml-gpt4", "GPT-4 (quantized)", isFree = true, description = "LocalAI model"),
        )),
        AiProvider("text-gen-ui", "TextGen WebUI", ApiFormat.OPENAI_COMPAT,
            "http://127.0.0.1:5000/v1", "local-model", listOf(
            Model("local-model", "Oobabooga model", isFree = true, description = "Self-hosted"),
        )),
        AiProvider("koboldcpp", "KoboldCPP", ApiFormat.OPENAI_COMPAT,
            "http://127.0.0.1:5001/v1", "local-model", listOf(
            Model("local-model", "KoboldCPP model", isFree = true, description = "Self-hosted CPP"),
        )),

        // ── Additional Cloud Providers ──
        AiProvider("greptile", "Greptile", ApiFormat.OPENAI_COMPAT,
            "https://api.greptile.com/v1", "gpt-4o", listOf(
            Model("gpt-4o", "GPT-4o", description = "via Greptile"),
        )),
        AiProvider("writer", "Writer", ApiFormat.OPENAI_COMPAT,
            "https://api.writer.com/v1", "palmyra-x-004", listOf(
            Model("palmyra-x-004", "Palmyra X 004", description = "Writer flagship"),
        )),

        // ── More Providers for 50+ total ──
        AiProvider("yi-01ai", "01.AI (Yi)", ApiFormat.OPENAI_COMPAT,
            "https://api.lingyiwanwu.com/v1", "yi-lightning", listOf(
            Model("yi-lightning", "Yi Lightning", isFree = true, description = "Fast Yi model"),
            Model("yi-large", "Yi Large", description = "Flagship Yi model"),
        )),
        AiProvider("abacus", "Abacus AI", ApiFormat.OPENAI_COMPAT,
            "https://api.abacus.ai/api/v1", "gpt-4o", listOf(
            Model("gpt-4o", "GPT-4o", description = "Via Abacus"),
            Model("claude-3-5-sonnet", "Claude 3.5 Sonnet", description = "Via Abacus"),
        )),
        AiProvider("cloudflare", "Cloudflare Workers AI", ApiFormat.OPENAI_COMPAT,
            "https://api.cloudflare.com/client/v4/accounts/YOUR_ACCOUNT/ai/v1", "@cf/meta/llama-3.3-70b-instruct", listOf(
            Model("@cf/meta/llama-3.3-70b-instruct", "Llama 3.3 70B", isFree = true, description = "Via Cloudflare"),
            Model("@hf/mistral/mistral-7b-instruct-v0.3", "Mistral 7B", isFree = true, description = "Via Cloudflare"),
        )),
        AiProvider("databricks", "Databricks", ApiFormat.OPENAI_COMPAT,
            "https://WORKSPACE.cloud.databricks.com/serving-endpoints", "databricks-meta-llama-3-3-70b-instruct", listOf(
            Model("databricks-meta-llama-3-3-70b-instruct", "Llama 3.3 70B", description = "Via Databricks"),
            Model("databricks-dbrx-instruct", "DBRX Instruct", description = "Databricks model"),
        )),
        AiProvider("gooey", "Gooey AI", ApiFormat.OPENAI_COMPAT,
            "https://api.gooey.ai/v2", "gpt-4o", listOf(
            Model("gpt-4o", "GPT-4o", description = "Via Gooey"),
            Model("claude-3-sonnet", "Claude 3 Sonnet", description = "Via Gooey"),
        )),
        AiProvider("jina", "Jina AI", ApiFormat.OPENAI_COMPAT,
            "https://api.jina.ai/v1", "gpt-4o-mini", listOf(
            Model("gpt-4o-mini", "GPT-4o Mini", description = "Via Jina"),
        )),
        AiProvider("minimax", "MiniMax", ApiFormat.OPENAI_COMPAT,
            "https://api.minimax.chat/v1/text/chatcompletion", "MiniMax-Text-01", listOf(
            Model("MiniMax-Text-01", "MiniMax Text 01", description = "MiniMax flagship"),
        )),
        AiProvider("novita", "Novita AI", ApiFormat.OPENAI_COMPAT,
            "https://api.novita.ai/v3/openai", "meta-llama/llama-3.3-70b-instruct", listOf(
            Model("meta-llama/llama-3.3-70b-instruct", "Llama 3.3 70B", description = "Via Novita"),
        )),
        AiProvider("portkey", "Portkey", ApiFormat.OPENAI_COMPAT,
            "https://api.portkey.ai/v1", "gpt-4o", listOf(
            Model("gpt-4o", "GPT-4o", description = "Via Portkey gateway"),
        )),
        AiProvider("rapidapi", "RapidAPI", ApiFormat.OPENAI_COMPAT,
            "https://openai80.p.rapidapi.com/v1", "gpt-4o-mini", listOf(
            Model("gpt-4o-mini", "GPT-4o Mini", description = "Via RapidAPI"),
        )),
        AiProvider("spark", "SparkLLM (iFlytek)", ApiFormat.OPENAI_COMPAT,
            "https://spark-api.xf-yun.com/v3.5/chat", "spark-3.5", listOf(
            Model("spark-3.5", "Spark 3.5", description = "iFlytek model"),
        )),
        AiProvider("vectara", "Vectara", ApiFormat.OPENAI_COMPAT,
            "https://api.vectara.io/v1", "gpt-4o", listOf(
            Model("gpt-4o", "GPT-4o", description = "Via Vectara"),
        )),
        AiProvider("akash", "Akash Network", ApiFormat.OPENAI_COMPAT,
            "https://chatapi.akash.network/api/v1", "akash-llama-3-3-70b", listOf(
            Model("akash-llama-3-3-70b", "Akash Llama 3.3 70B", isFree = true, description = "Decentralized GPU"),
        )),
        AiProvider("mancer", "Mancer", ApiFormat.OPENAI_COMPAT,
            "https://ai.mancer.xyz/v1", "gpt-4o-mini", listOf(
            Model("gpt-4o-mini", "GPT-4o Mini", description = "Via Mancer"),
        )),
        AiProvider("stability", "Stability AI", ApiFormat.OPENAI_COMPAT,
            "https://api.stability.ai/v1", "stable-diffusion-xl", listOf(
            Model("stable-diffusion-xl", "Stable Diffusion XL", description = "Image generation"),
        )),
    )
    val totalPresets: Int get() = PRESETS.size

    fun findById(id: String): AiProvider? = PRESETS.find { it.id == id }

    /** Total count including all preset models */
    val totalModelCount: Int get() = PRESETS.sumOf { it.models.size }
    val freeModelCount: Int get() = PRESETS.sumOf { it.models.count { m -> m.isFree } }
}
