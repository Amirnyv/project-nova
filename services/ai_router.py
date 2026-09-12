import os
import time
from dataclasses import dataclass
from threading import Lock

from openai import OpenAI


# -------------------------------------------------
# ROUTER CONFIG
# -------------------------------------------------

OPENAI_MODEL = os.getenv(
    "OPENAI_MODEL",
    "gpt-4o-mini"
)

CLOUDFLARE_MODEL = os.getenv(
    "CLOUDFLARE_MODEL",
    "@cf/openai/gpt-oss-20b"
)

OPENROUTER_MODEL = os.getenv(
    "OPENROUTER_MODEL",
    "openrouter/free"
)

NVIDIA_MODEL = os.getenv(
    "NVIDIA_MODEL",
    "openai/gpt-oss-20b"
)


# -------------------------------------------------
# PROVIDER STATE
# -------------------------------------------------

@dataclass
class ProviderState:
    name: str
    cooldown_until: float = 0.0
    failures: int = 0
    last_error: str = ""


_PROVIDER_STATES = {
    "cloudflare": ProviderState("cloudflare"),
    "openrouter": ProviderState("openrouter"),
    "nvidia": ProviderState("nvidia"),
    "openai": ProviderState("openai"),
}

_STATE_LOCK = Lock()


# -------------------------------------------------
# CLIENT BUILDERS
# -------------------------------------------------

def _build_cloudflare_client():
    account_id = os.getenv("CLOUDFLARE_ACCOUNT_ID")
    api_token = os.getenv("CLOUDFLARE_API_TOKEN")

    if not account_id or not api_token:
        return None

    return OpenAI(
        api_key=api_token,
        base_url=(
            f"https://api.cloudflare.com/client/v4/accounts/"
            f"{account_id}/ai/v1"
        ),
    )


def _build_openrouter_client():
    api_key = os.getenv("OPENROUTER_API_KEY")

    if not api_key:
        return None

    return OpenAI(
        api_key=api_key,
        base_url="https://openrouter.ai/api/v1",
        default_headers={
            "HTTP-Referer": "https://workfieldhq.com",
            "X-Title": "Nova"
        }
    )


def _build_nvidia_client():
    api_key = os.getenv("NVIDIA_API_KEY")

    if not api_key:
        return None

    return OpenAI(
        api_key=api_key,
        base_url="https://integrate.api.nvidia.com/v1"
    )


def _build_openai_client():
    api_key = os.getenv("OPENAI_API_KEY")

    if not api_key:
        return None

    return OpenAI(
        api_key=api_key
    )


# -------------------------------------------------
# PROVIDERS
# -------------------------------------------------

def _providers():
    return [
        {
            "name": "cloudflare",
            "client": _build_cloudflare_client(),
            "model": CLOUDFLARE_MODEL,
            "is_paid_fallback": False,
        },
        {
            "name": "openrouter",
            "client": _build_openrouter_client(),
            "model": OPENROUTER_MODEL,
            "is_paid_fallback": False,
        },
        {
            "name": "nvidia",
            "client": _build_nvidia_client(),
            "model": NVIDIA_MODEL,
            "is_paid_fallback": False,
        },
        {
            "name": "openai",
            "client": _build_openai_client(),
            "model": OPENAI_MODEL,
            "is_paid_fallback": True,
        },
    ]


# -------------------------------------------------
# COOLDOWN
# -------------------------------------------------

def _is_available(provider_name):
    with _STATE_LOCK:
        state = _PROVIDER_STATES[provider_name]

        return time.time() >= state.cooldown_until


def _mark_success(provider_name):
    with _STATE_LOCK:
        state = _PROVIDER_STATES[provider_name]

        state.failures = 0
        state.last_error = ""
        state.cooldown_until = 0.0


def _mark_failure(
    provider_name,
    error,
    cooldown_seconds=60
):
    with _STATE_LOCK:
        state = _PROVIDER_STATES[provider_name]

        state.failures += 1
        state.last_error = type(error).__name__

        backoff = min(
            cooldown_seconds
            * max(state.failures, 1),
            900
        )

        state.cooldown_until = (
            time.time()
            + backoff
        )


# -------------------------------------------------
# USAGE
# -------------------------------------------------

def _extract_usage(response):
    usage = getattr(
        response,
        "usage",
        None
    )

    if not usage:
        return {
            "input_tokens": 0,
            "output_tokens": 0,
            "total_tokens": 0,
        }

    input_tokens = (
        getattr(
            usage,
            "prompt_tokens",
            0
        )
        or 0
    )

    output_tokens = (
        getattr(
            usage,
            "completion_tokens",
            0
        )
        or 0
    )

    total_tokens = (
        getattr(
            usage,
            "total_tokens",
            0
        )
        or (
            input_tokens
            + output_tokens
        )
    )

    return {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "total_tokens": total_tokens,
    }


# -------------------------------------------------
# ROUTED CHAT
# -------------------------------------------------

def routed_chat_completion(
    messages,
    max_tokens=4096,
    temperature=0.7,
    allow_openai_fallback=True
):
    errors = []

    for provider in _providers():

        name = provider["name"]
        client = provider["client"]
        model = provider["model"]

        if client is None:
            continue

        if (
            provider["is_paid_fallback"]
            and not allow_openai_fallback
        ):
            continue

        if not _is_available(name):
            continue

        try:
            response = (
                client
                .chat
                .completions
                .create(
                    model=model,
                    messages=messages,
                    max_tokens=max_tokens,
                    temperature=temperature,
                )
            )

            reply = (
                response
                .choices[0]
                .message
                .content
                or ""
            )

            if not reply.strip():
                raise RuntimeError(
                    "Provider returned an empty response."
                )

            _mark_success(name)

            return {
                "reply": reply,
                "provider": name,
                "model": model,
                "usage": _extract_usage(
                    response
                ),
            }

        except Exception as error:

            _mark_failure(
                name,
                error
            )

            errors.append({
                "provider": name,
                "error": type(error).__name__,
            })

            print(
                f"Nova router provider failed: "
                f"{name} "
                f"({type(error).__name__})"
            )

    raise RuntimeError(
        "All Nova AI providers are unavailable."
    )


# -------------------------------------------------
# STATUS
# -------------------------------------------------

def get_router_status():
    now = time.time()

    result = {}

    with _STATE_LOCK:

        for name, state in (
            _PROVIDER_STATES.items()
        ):

            remaining = max(
                int(
                    state.cooldown_until
                    - now
                ),
                0
            )

            result[name] = {
                "available":
                    remaining == 0,

                "cooldown_seconds":
                    remaining,

                "failures":
                    state.failures,

                "last_error":
                    state.last_error,
            }

    return result
