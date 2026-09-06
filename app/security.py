import re
from groq import Groq

from .config import GROQ_API_KEY

client = Groq(api_key=GROQ_API_KEY)

MAX_MESSAGE_LENGTH = 2000

INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above)\s+instructions",
    r"forget\s+(all\s+)?(previous|prior|above)",
    r"disregard\s+(all\s+)?(previous|prior|above)",
    r"reveal\s+(your\s+)?(system|hidden|internal)\s+(prompt|instructions)",
    r"show\s+(me\s+)?(your\s+)?(system|hidden|internal)\s+(prompt|instructions)",
    r"print\s+(your\s+)?(system|hidden|internal)\s+(prompt|instructions)",
    r"reveal\s+(the\s+)?api\s*key",
    r"show\s+(the\s+)?api\s*key",
    r"reveal\s+(your\s+)?credentials",
    r"developer\s+message",
    r"system\s+message",
    r"jailbreak",
    r"do\s+anything\s+now",
    r"act\s+as\s+(an?\s+)?unrestricted",
    r"pretend\s+you\s+have\s+no\s+rules"
]


def obvious_injection(message: str) -> bool:
    normalized = re.sub(r"\s+", " ", message.lower())

    return any(
        re.search(pattern, normalized)
        for pattern in INJECTION_PATTERNS
    )


def check_input(message: str):
    if not isinstance(message, str):
        return False, "Invalid message."

    message = message.strip()

    if not message:
        return False, "Please enter a message."

    if len(message) > MAX_MESSAGE_LENGTH:
        return False, "Please keep your message under 2,000 characters."

    if obvious_injection(message):
        return False, (
            "I'm here to help with questions about the business. "
            "I can't help with requests to change my instructions "
            "or reveal internal information."
        )

    try:
        result = client.chat.completions.create(
            model="meta-llama/llama-prompt-guard-2-86m",
            messages=[
                {
                    "role": "user",
                    "content": message
                }
            ],
            max_tokens=20
        )

        output = result.choices[0].message.content.lower()

        attack_words = [
            "malicious",
            "injection",
            "jailbreak",
            "attack"
        ]

        if any(word in output for word in attack_words):
            return False, (
                "I'm here to help with questions about the business. "
                "Please ask me about our services, prices, appointments "
                "or other business information."
            )

    except Exception:
        pass

    return True, None