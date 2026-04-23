"""Constants for the Morning Brief integration."""

from __future__ import annotations

DOMAIN = "morning_brief"
NAME = "Morning Brief"
PLATFORMS = ["sensor"]

SERVICE_GENERATE = "generate"

CONF_ZAI_API_KEY = "zai_api_key"
CONF_ZAI_BASE_URL = "zai_base_url"
CONF_ZAI_MODEL = "zai_model"
CONF_ELEVENLABS_API_KEY = "elevenlabs_api_key"
CONF_RSS_LOOKBACK_DAYS = "rss_lookback_days"
CONF_CACHE_ENABLED = "cache_enabled"
CONF_CACHE_TTL_MINUTES = "cache_ttl_minutes"
CONF_SYSTEM_PROMPT = "system_prompt"
CONF_TOPICS = "topics"

CONF_TOPIC_NAME = "name"
CONF_TOPIC_PROMPT = "topic_prompt"
CONF_TOPIC_FEEDS = "feeds"

ATTR_SPEAKER_ENTITY_ID = "speaker_entity_id"
ATTR_ELEVENLABS_VOICE_ID = "elevenlabs_voice_id"
ATTR_ELEVENLABS_MODEL = "elevenlabs_model"

DATA_CACHE_DIR = "cache_dir"
DATA_SERVICE_REGISTERED = "service_registered"
DATA_STATIC_REGISTERED = "static_registered"

SENSOR_LATEST_BRIEF_KEY = "latest_brief"
SENSOR_LATEST_BRIEF_NAME = "Latest Brief"

DEFAULT_ZAI_BASE_URL = "https://api.z.ai/api/paas/v4"
DEFAULT_ZAI_MODEL = "glm-5.1"
DEFAULT_RSS_LOOKBACK_DAYS = 1
DEFAULT_CACHE_ENABLED = True
DEFAULT_CACHE_TTL_MINUTES = 60
DEFAULT_SYSTEM_PROMPT = (
    "Tu es un redacteur radio francophone. Assemble les resumes par sujet en un "
    "brief matinal fluide, naturel et concis, pret a etre lu a voix haute. "
    "Reste factuel, cite les sujets importants, et termine avec une transition "
    "courte et elegante."
)

DEFAULT_PLAYBACK_TIMEOUT_SECONDS = 1800
DEFAULT_WAIT_STEP_SECONDS = 1
DEFAULT_HTTP_TIMEOUT_SECONDS = 90.0
FEED_ITEM_WORD_LIMIT = 100
MAX_ITEMS_PER_FEED = 5
TTS_LANGUAGE_CODE = "fr"
GENERATED_AUDIO_CONTENT_TYPE = "music"

STATIC_CACHE_PATH = f"/api/{DOMAIN}/cache"
TEMP_AUDIO_PREFIX = "morning_brief_"
