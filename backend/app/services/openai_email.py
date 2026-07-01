import hashlib
import json
from pathlib import Path

from openai import AsyncOpenAI

from app.core.config import Settings
from app.domain.email import EmailTriageResult

SYSTEM_PROMPT = (Path(__file__).resolve().parents[2] / "prompts" / "email_triage.md").read_text(
    encoding="utf-8"
)


class OpenAIEmailService:
    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def triage_and_draft(
        self,
        *,
        subject: str,
        sender_email: str,
        sender_name: str | None,
        body_text: str,
        is_existing_client: bool,
        recent_thread_context: str,
        business_name: str,
        reply_signature: str,
        whatsapp_link: str,
    ) -> tuple[EmailTriageResult, str]:
        input_payload = {
            "subject": subject,
            "sender_name": sender_name,
            "body": body_text[:20_000],
            "is_existing_client": is_existing_client,
            "recent_thread_context": recent_thread_context[-8_000:],
        }
        response = await self._client.responses.parse(
            model=self._settings.openai_model,
            instructions=SYSTEM_PROMPT.format(
                business_name=business_name,
                signature_block=reply_signature,
                whatsapp_link=whatsapp_link,
            ),
            input=json.dumps(input_payload, ensure_ascii=False),
            reasoning={"effort": "low"},
            text_format=EmailTriageResult,
            verbosity="low",
            store=False,
            safety_identifier=hashlib.sha256(sender_email.lower().encode()).hexdigest()[:64],
        )
        if response.output_parsed is None:
            raise RuntimeError("OpenAI returned no triage output")
        return response.output_parsed, response.id

    async def close(self) -> None:
        await self._client.close()
