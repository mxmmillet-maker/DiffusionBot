import json
import logging

import anthropic

from adapters.base import ContentType, PlatformConstraints

logger = logging.getLogger("diffusionbot.reformulator")


class ContentReformulator:
    """Reformule le contenu via Claude API pour chaque plateforme."""

    SYSTEM_PROMPT = (
        "Tu es un redacteur SEO expert. Tu reformules du contenu pour le publier "
        "sur differentes plateformes web. Le contenu doit etre UNIQUE (pas de duplicate "
        "content), naturel, et contenir un lien retour vers l'URL source de maniere "
        "organique. Ne copie jamais mot pour mot. Adapte le ton et la longueur. "
        "Reponds UNIQUEMENT en JSON valide, sans markdown ni commentaire."
    )

    def __init__(self, api_key: str, model: str = "claude-sonnet-4-20250514"):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model

    def reformulate(
        self,
        original_title: str,
        original_body: str,
        target_url: str,
        keywords: list[str],
        constraints: PlatformConstraints,
        content_type: ContentType,
        platform_name: str,
        tone: str = "professionnel",
    ) -> dict:
        """Retourne {"title": str, "body": str, "tags": list[str]}."""
        body_preview = original_body[:3000] if len(original_body) > 3000 else original_body
        content_format = (
            "HTML" if constraints.supports_html
            else "Markdown" if constraints.supports_markdown
            else "Texte brut"
        )

        user_prompt = f"""Reformule ce contenu pour publication sur {platform_name}.

CONTRAINTES PLATEFORME:
- Type: {content_type.value}
- Titre max: {constraints.max_title_length} caracteres
- Corps max: {constraints.max_body_length} caracteres
- Format: {content_format}
- Max liens dans le corps: {constraints.max_links_in_body}
- Max tags: {constraints.max_tags}

CONTENU ORIGINAL:
Titre: {original_title}
Corps: {body_preview}

URL A LINKER (backlink): {target_url}
Mots-cles cibles: {", ".join(keywords) if keywords else "aucun"}
Ton souhaite: {tone}

INSTRUCTIONS:
1. Reformule completement (contenu unique, pas de copier-coller)
2. Integre le lien vers {target_url} de maniere naturelle dans le texte
3. Adapte la longueur au type de plateforme
4. Genere des tags pertinents
5. Le titre doit etre accrocheur et optimise SEO

Reponds UNIQUEMENT en JSON: {{"title": "...", "body": "...", "tags": ["...", ...]}}"""

        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=self.SYSTEM_PROMPT,
                messages=[{"role": "user", "content": user_prompt}],
            )
            raw = response.content[0].text.strip()
            # Nettoyer si Claude enveloppe dans ```json
            if raw.startswith("```"):
                raw = raw.split("\n", 1)[1]
                raw = raw.rsplit("```", 1)[0]
            result = json.loads(raw)

            # Valider les champs attendus
            if "title" not in result or "body" not in result:
                raise ValueError(f"Champs manquants dans la reponse: {list(result.keys())}")

            result.setdefault("tags", [])
            result["tags"] = result["tags"][: constraints.max_tags]

            logger.info(
                f"Reformulation OK pour {platform_name}: "
                f"titre={len(result['title'])}c, corps={len(result['body'])}c, "
                f"tags={len(result['tags'])}"
            )
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Erreur parsing JSON depuis Claude: {e}")
            raise
        except anthropic.APIError as e:
            logger.error(f"Erreur API Anthropic: {e}")
            raise
