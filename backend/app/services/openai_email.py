import hashlib
import json
from pathlib import Path
from typing import Any

import httpx
from openai import AsyncOpenAI
from pydantic import ValidationError

from app.core.config import Settings
from app.domain.email import EmailTriageResult

SYSTEM_PROMPT = (Path(__file__).resolve().parents[2] / "prompts" / "email_triage.md").read_text(
    encoding="utf-8"
)


class OpenAIEmailService:
    """Provider-switched AI service kept under the old name for API compatibility."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client = (
            AsyncOpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None
        )
        self._http = httpx.AsyncClient(timeout=settings.replicate_timeout_seconds)

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
        business_policy_instructions: str,
    ) -> tuple[EmailTriageResult, str]:
        input_payload = {
            "subject": subject,
            "sender_name": sender_name,
            "body": body_text[:20_000],
            "is_existing_client": is_existing_client,
            "recent_thread_context": recent_thread_context[-8_000:],
        }
        instructions = SYSTEM_PROMPT.format(
            business_name=business_name,
            signature_block=reply_signature,
            whatsapp_link=whatsapp_link,
            business_policy_instructions=business_policy_instructions.strip()
            or "Follow the default BeoOS business policy.",
        )
        if self._settings.ai_provider == "replicate":
            return await self._triage_with_replicate(
                instructions=instructions,
                input_payload=input_payload,
                sender_email=sender_email,
            )
        if self._client is None:
            raise RuntimeError("OpenAI API key is not configured")
        response = await self._client.responses.parse(
            model=self._settings.openai_model,
            instructions=instructions,
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

    async def _triage_with_replicate(
        self,
        *,
        instructions: str,
        input_payload: dict[str, Any],
        sender_email: str,
    ) -> tuple[EmailTriageResult, str]:
        if not self._settings.replicate_api_token:
            raise RuntimeError("Replicate API token is not configured")
        prompt = (
            f"{instructions}\n\n"
            "Return only valid JSON matching this schema. Do not wrap it in markdown.\n"
            f"{json.dumps(EmailTriageResult.model_json_schema(), ensure_ascii=False)}\n\n"
            "Message payload:\n"
            f"{json.dumps(input_payload, ensure_ascii=False)}"
        )
        prediction = await self._create_replicate_prediction(
            prompt=prompt,
            sender_email=sender_email,
        )
        output = await self._wait_for_replicate_prediction(str(prediction["id"]))
        text = self._stringify_replicate_output(output)
        try:
            parsed = EmailTriageResult.model_validate_json(text)
        except ValidationError:
            start = text.find("{")
            end = text.rfind("}") + 1
            if start < 0 or end <= start:
                raise RuntimeError("Replicate returned invalid triage JSON") from None
            parsed = EmailTriageResult.model_validate_json(text[start:end])
        return parsed, f"replicate:{prediction['id']}"

    async def _create_replicate_prediction(
        self,
        *,
        prompt: str,
        sender_email: str,
    ) -> dict[str, Any]:
        owner, model = self._settings.replicate_model.split("/", maxsplit=1)
        response = await self._http.post(
            f"https://api.replicate.com/v1/models/{owner}/{model}/predictions",
            headers={
                "Authorization": f"Bearer {self._settings.replicate_api_token}",
                "Content-Type": "application/json",
                "Prefer": "wait=10",
            },
            json={
                "input": {
                    "prompt": prompt,
                    "system_prompt": "You are BeoOS, a structured sales operations AI.",
                    "temperature": 0.1,
                },
                "metadata": {
                    "safety_identifier": hashlib.sha256(
                        sender_email.lower().encode()
                    ).hexdigest()[:64],
                },
            },
        )
        response.raise_for_status()
        return response.json()

    async def _wait_for_replicate_prediction(self, prediction_id: str) -> Any:
        attempts = max(1, self._settings.replicate_timeout_seconds // 3)
        for _ in range(attempts):
            response = await self._http.get(
                f"https://api.replicate.com/v1/predictions/{prediction_id}",
                headers={"Authorization": f"Bearer {self._settings.replicate_api_token}"},
            )
            response.raise_for_status()
            prediction = response.json()
            if prediction.get("status") == "succeeded":
                return prediction.get("output")
            if prediction.get("status") in {"failed", "canceled"}:
                raise RuntimeError(f"Replicate prediction {prediction.get('status')}")
        raise RuntimeError("Replicate prediction timed out")

    def _stringify_replicate_output(self, output: Any) -> str:
        if isinstance(output, str):
            return output
        if isinstance(output, list):
            return "".join(str(part) for part in output)
        return json.dumps(output, ensure_ascii=False)

    async def close(self) -> None:
        if self._client is not None:
            await self._client.close()
        await self._http.aclose()
