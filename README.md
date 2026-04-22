# Morning Brief

Morning Brief is a Home Assistant custom integration that builds a French spoken news brief from RSS feeds, summarizes it with z.ai, synthesizes audio with ElevenLabs, and plays it on a Home Assistant media player.

This repository is structured for HACS as an `Integration` repository.

## Features

- Config flow support from Home Assistant UI
- YAML import support from `configuration.yaml`
- Per-topic RSS feed groups with custom prompts
- Two-pass z.ai summarization flow
- ElevenLabs voice and model selection at service-call time
- Single-slot audio cache with TTL
- Media player pause / play / resume handling

## Installation with HACS

1. Open HACS in Home Assistant.
2. Open the top-right menu and choose `Custom repositories`.
3. Add this repository URL.
4. Choose repository type `Integration`.
5. Install `Morning Brief`.
6. Restart Home Assistant.
7. Go to `Settings` -> `Devices & services` -> `Add integration`.
8. Search for `Morning Brief`.

If the integration does not appear immediately after restart, clear the browser cache and reload Home Assistant.

## Manual installation

1. Copy `custom_components/morning_brief` into your Home Assistant `custom_components` directory.
2. Restart Home Assistant.
3. Add the integration from `Settings` -> `Devices & services`.

## Configuration

You can configure the integration from the UI, or import an initial configuration from `configuration.yaml`.

Example YAML import:

```yaml
morning_brief:
  zai_api_key: !secret zai_api_key
  zai_base_url: "https://api.z.ai/api/paas/v4"
  zai_model: "glm-5.1"
  elevenlabs_api_key: !secret elevenlabs_api_key
  rss_lookback_days: 1
  cache_enabled: true
  cache_ttl_minutes: 60
  system_prompt: >-
    Tu es un redacteur radio francophone. Assemble les resumes par sujet en un
    brief matinal fluide, naturel et concis, pret a etre lu a voix haute.
  topics:
    - name: "Tech"
      topic_prompt: >-
        Fais un resume clair et vivant des nouvelles tech en francais.
      feeds:
        - "https://example.com/tech.rss"
    - name: "Finance"
      topic_prompt: >-
        Priorise les mouvements de marche, les entreprises majeures et le contexte.
      feeds:
        - "https://example.com/finance.rss"
```

## Service

The integration registers the `morning_brief.generate` action.

Example automation action:

```yaml
action:
  - service: morning_brief.generate
    data:
      speaker_entity_id: media_player.salon
      elevenlabs_voice_id: "your_voice_id"
      elevenlabs_model: "eleven_multilingual_v2"
```

## Notes

- The generated audio is cached in Home Assistant's temp directory and is not persistent across restarts.
- Audio playback requires Home Assistant to have a reachable internal or external URL configured so media players can fetch the generated file.
- RSS, z.ai, ElevenLabs, and media-player failures are logged to Home Assistant logs.

## Development

This repository includes:

- `hacs.json` for HACS metadata
- a HACS validation workflow
- a Hassfest validation workflow

## Support

Open an issue in this repository if setup or playback is not behaving as expected.

