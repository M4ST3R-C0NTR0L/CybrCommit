"""Configuration management for ai-commit."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class Config:
    """Configuration for ai-commit."""
    
    # AI Provider settings
    ai_provider: Optional[str] = None  # 'openai', 'anthropic', 'ollama', or None for rule-based
    model: Optional[str] = None
    
    # API Keys (loaded from env vars)
    openai_api_key: Optional[str] = None
    anthropic_api_key: Optional[str] = None
    ollama_host: str = "http://localhost:11434"
    
    # Behavior settings
    auto_commit: bool = False
    dry_run: bool = False
    use_emoji: bool = False
    max_diff_lines: int = 500
    default_scope: Optional[str] = None
    
    @classmethod
    def load(cls) -> Config:
        """Load configuration from environment and config files."""
        config = cls()
        
        # Load from environment variables
        config.openai_api_key = os.environ.get("OPENAI_API_KEY")
        config.anthropic_api_key = os.environ.get("ANTHROPIC_API_KEY")
        config.ollama_host = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        
        # AI provider preference from env
        config.ai_provider = os.environ.get("AI_COMMIT_PROVIDER")
        config.model = os.environ.get("AI_COMMIT_MODEL")
        
        # Behavior settings from env
        config.use_emoji = os.environ.get("AI_COMMIT_EMOJI", "").lower() in ("1", "true", "yes")
        config.auto_commit = os.environ.get("AI_COMMIT_AUTO", "").lower() in ("1", "true", "yes")
        
        max_lines = os.environ.get("AI_COMMIT_MAX_DIFF_LINES")
        if max_lines:
            try:
                config.max_diff_lines = int(max_lines)
            except ValueError:
                pass
        
        # Load from config file if exists
        config_path = cls._get_config_path()
        if config_path.exists():
            config._load_from_file(config_path)
        
        return config
    
    @staticmethod
    def _get_config_path() -> Path:
        """Get the path to the config file."""
        # Check XDG_CONFIG_HOME first, then fallback to ~/.config
        config_dir = os.environ.get("XDG_CONFIG_HOME")
        if config_dir:
            return Path(config_dir) / "ai-commit" / "config"
        return Path.home() / ".config" / "ai-commit" / "config"
    
    def _load_from_file(self, path: Path) -> None:
        """Load configuration from a file."""
        try:
            content = path.read_text()
            for line in content.strip().split("\n"):
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    
                    if key == "provider":
                        self.ai_provider = value
                    elif key == "model":
                        self.model = value
                    elif key == "emoji":
                        self.use_emoji = value.lower() in ("1", "true", "yes")
                    elif key == "auto":
                        self.auto_commit = value.lower() in ("1", "true", "yes")
                    elif key == "max_diff_lines":
                        try:
                            self.max_diff_lines = int(value)
                        except ValueError:
                            pass
                    elif key == "ollama_host":
                        self.ollama_host = value
        except Exception:
            # Silently ignore config file errors
            pass
    
    def get_api_key(self) -> Optional[str]:
        """Get the API key for the configured provider."""
        if self.ai_provider == "openai":
            return self.openai_api_key
        elif self.ai_provider == "anthropic":
            return self.anthropic_api_key
        return None
    
    def is_ai_available(self) -> bool:
        """Check if AI generation is available."""
        if self.ai_provider == "ollama":
            return True  # Ollama doesn't need an API key
        return self.get_api_key() is not None
