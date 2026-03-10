"""Commit message generator for CybrCommit.

Supports both rule-based (no API) and AI-powered generation.
"""

from __future__ import annotations

import json
import re
import subprocess
from typing import Optional, List, Dict, Any

from cybrcommit.diff_parser import (
    DiffSummary, FileChange, FileType, ChangeType,
    get_staged_diff, get_unstaged_diff, parse_diff
)
from cybrcommit.config import Config


# Gitmoji mapping for --emoji option
GITMOJI_MAP: Dict[str, str] = {
    "feat": "✨",
    "fix": "🐛",
    "docs": "📚",
    "style": "💎",
    "refactor": "♻️",
    "perf": "⚡",
    "test": "🧪",
    "chore": "🔧",
    "ci": "👷",
    "build": "📦",
    "revert": "⏪",
    "wip": "🚧",
}


def truncate_message(message: str, max_length: int = 72) -> str:
    """Truncate a commit message to fit within limits."""
    if len(message) <= max_length:
        return message
    
    # Try to truncate at a word boundary
    truncated = message[:max_length - 3].rsplit(" ", 1)[0]
    return truncated + "..."


def get_scope_from_path(path: str) -> Optional[str]:
    """Extract a likely scope from a file path."""
    parts = path.split("/")
    
    # Common scope patterns
    for part in parts:
        part_lower = part.lower()
        if part_lower in [
            "auth", "api", "ui", "cli", "core", "utils", "helpers",
            "config", "db", "models", "views", "controllers", "services",
            "middleware", "routes", "components", "hooks", "store",
            "styles", "assets", "tests", "docs", "scripts", "ci",
            "docker", "k8s", "terraform", "ansible"
        ]:
            return part_lower
    
    # Try first directory if in src/ or similar
    if len(parts) >= 2:
        if parts[0] in ["src", "lib", "app", "packages", "internal"]:
            return parts[1] if len(parts[1]) < 20 else None
    
    return None


def generate_rule_based(summary: DiffSummary, config: Config, 
                        forced_type: Optional[str] = None,
                        forced_scope: Optional[str] = None) -> str:
    """Generate a commit message using the rule-based engine.
    
    This is the zero-config mode that works without any API keys.
    """
    # Determine commit type
    commit_type = forced_type
    scope = forced_scope or config.default_scope
    
    if commit_type is None:
        commit_type = determine_commit_type(summary)
    
    # Determine scope if not provided
    if scope is None:
        scope = determine_scope(summary)
    
    # Generate description based on changes
    description = generate_description(summary, commit_type)
    
    # Build the message
    if scope:
        message = f"{commit_type}({scope}): {description}"
    else:
        message = f"{commit_type}: {description}"
    
    # Add emoji if requested
    if config.use_emoji and commit_type in GITMOJI_MAP:
        message = f"{GITMOJI_MAP[commit_type]} {message}"
    
    return truncate_message(message)


def determine_commit_type(summary: DiffSummary) -> str:
    """Determine the most appropriate commit type from changes."""
    # Priority order for type detection
    
    # Renames are usually refactor
    if summary.has_renames and len(summary.files) == 1:
        return "refactor"
    
    # Test files
    if summary.has_tests and not any(
        f.file_type != FileType.TEST for f in summary.files
    ):
        return "test"
    
    # Documentation
    if summary.has_docs and not any(
        f.file_type != FileType.DOCUMENTATION for f in summary.files
    ):
        return "docs"
    
    # Dependencies
    if summary.has_dependencies:
        return "chore"
    
    # Config changes only
    if summary.has_config and not any(
        f.file_type not in (FileType.CONFIG, FileType.CI_CD) for f in summary.files
    ):
        return "chore"
    
    # Style files (CSS, etc)
    style_files = summary.get_by_type(FileType.STYLE)
    if style_files and not any(
        f.file_type != FileType.STYLE for f in summary.files
    ):
        return "style"
    
    # Look at what was actually changed
    added_files = summary.get_by_change_type(ChangeType.ADDED)
    deleted_files = summary.get_by_change_type(ChangeType.DELETED)
    modified_files = summary.get_by_change_type(ChangeType.MODIFIED)
    
    # Pure deletions
    if deleted_files and not added_files and not modified_files:
        return "chore"
    
    # If mostly test changes along with source
    test_changes = [f for f in summary.files if f.file_type == FileType.TEST]
    source_changes = [f for f in summary.files if f.file_type == FileType.SOURCE_CODE]
    
    if test_changes and not source_changes:
        return "test"
    
    if test_changes and source_changes:
        # Mixed test and source - could be feat or fix
        # Check if tests were added (new feature) or just modified (fix)
        test_additions = sum(f.additions for f in test_changes)
        if test_additions > sum(f.deletions for f in test_changes):
            return "feat"
    
    # Check for fix-related patterns in the actual changes
    if modified_files:
        fix_keywords = ["fix", "bug", "error", "crash", "issue", "broken", "repair"]
        for f in modified_files:
            content = " ".join(f.diff_content).lower()
            if any(kw in content for kw in fix_keywords):
                return "fix"
    
    # Default to feat for additions, fix for modifications
    if added_files and not modified_files:
        return "feat"
    
    return "fix"


def determine_scope(summary: DiffSummary) -> Optional[str]:
    """Determine the scope from the changed files."""
    if not summary.files:
        return None
    
    # If all files share a common directory prefix, use it as scope
    paths = [f.path for f in summary.files]
    common_prefix = get_common_prefix(paths)
    
    if common_prefix and len(common_prefix) > 1:
        # Use the last meaningful directory
        parts = [p for p in common_prefix.split("/") if p and p not in ["src", "lib", "app"]]
        if parts:
            return parts[-1]
    
    # Try to extract scope from file paths
    scopes: Dict[str, int] = {}
    for f in summary.files:
        scope = get_scope_from_path(f.path)
        if scope:
            scopes[scope] = scopes.get(scope, 0) + f.additions + f.deletions + 1
    
    if scopes:
        # Return the most common scope
        return max(scopes.items(), key=lambda x: x[1])[0]
    
    return None


def get_common_prefix(paths: List[str]) -> str:
    """Get the common directory prefix of multiple paths."""
    if not paths:
        return ""
    
    if len(paths) == 1:
        parts = paths[0].split("/")
        return "/".join(parts[:-1]) if len(parts) > 1 else ""
    
    # Split all paths
    split_paths = [p.split("/") for p in paths]
    
    # Find common prefix
    prefix = []
    for parts in zip(*split_paths):
        if all(p == parts[0] for p in parts):
            prefix.append(parts[0])
        else:
            break
    
    return "/".join(prefix)


def generate_description(summary: DiffSummary, commit_type: str) -> str:
    """Generate a descriptive commit message based on changes."""
    added = summary.get_by_change_type(ChangeType.ADDED)
    deleted = summary.get_by_change_type(ChangeType.DELETED)
    renamed = summary.get_by_change_type(ChangeType.RENAMED)
    modified = summary.get_by_change_type(ChangeType.MODIFIED)
    
    # Handle single file operations
    if len(summary.files) == 1:
        f = summary.files[0]
        filename = Path(f.path).name
        
        if f.is_rename and f.old_path:
            old_name = Path(f.old_path).name
            return f"rename {old_name} to {filename}"
        
        if f.change_type == ChangeType.ADDED:
            if f.file_type == FileType.TEST:
                return f"add tests for {filename}"
            if f.file_type == FileType.CONFIG:
                return f"add {filename} configuration"
            return f"add {filename}"
        
        if f.change_type == ChangeType.DELETED:
            return f"remove {filename}"
        
        if f.change_type == ChangeType.MODIFIED:
            if f.file_type == FileType.DEPENDENCY:
                return f"update dependencies in {filename}"
            if f.file_type == FileType.CONFIG:
                return f"update {filename} config"
            if f.file_type == FileType.DOCUMENTATION:
                return "update documentation"
            
            # Check for specific patterns
            if f.additions > 0 and f.deletions == 0:
                return f"add content to {filename}"
            if f.deletions > 0 and f.additions == 0:
                return f"remove content from {filename}"
            
            return f"update {filename}"
    
    # Handle renames
    if renamed and len(renamed) == len(summary.files):
        if len(renamed) == 1:
            f = renamed[0]
            if f.old_path:
                old_name = Path(f.old_path).name
                new_name = Path(f.path).name
                return f"rename {old_name} to {new_name}"
        return f"reorganize {len(renamed)} files"
    
    # Multiple files - summarize
    descriptions = []
    
    if added:
        added_types = set(f.file_type for f in added)
        if FileType.TEST in added_types:
            descriptions.append(f"add {len(added)} test file{'s' if len(added) > 1 else ''}")
        elif len(added) == 1:
            descriptions.append(f"add {Path(added[0].path).name}")
        else:
            descriptions.append(f"add {len(added)} files")
    
    if deleted:
        if len(deleted) == 1:
            descriptions.append(f"remove {Path(deleted[0].path).name}")
        else:
            descriptions.append(f"remove {len(deleted)} files")
    
    if modified:
        mod_types = set(f.file_type for f in modified)
        
        if FileType.DEPENDENCY in mod_types:
            descriptions.append("update dependencies")
        elif FileType.CONFIG in mod_types and len(mod_types) == 1:
            descriptions.append("update configuration")
        elif FileType.DOCUMENTATION in mod_types and len(mod_types) == 1:
            descriptions.append("update documentation")
        elif FileType.STYLE in mod_types and len(mod_types) == 1:
            descriptions.append("update styles")
        elif commit_type == "feat":
            if len(modified) == 1:
                descriptions.append(f"add functionality to {Path(modified[0].path).name}")
            else:
                descriptions.append("add new functionality")
        elif commit_type == "fix":
            if len(modified) == 1:
                descriptions.append(f"fix issue in {Path(modified[0].path).name}")
            else:
                descriptions.append("fix issues")
        elif commit_type == "refactor":
            descriptions.append("refactor code")
        elif commit_type == "test":
            descriptions.append("update tests")
        else:
            descriptions.append("update code")
    
    if descriptions:
        # Join with " and " for two items, ", " for more
        if len(descriptions) == 1:
            return descriptions[0]
        elif len(descriptions) == 2:
            return " and ".join(descriptions)
        else:
            return ", ".join(descriptions[:-1]) + " and " + descriptions[-1]
    
    return "update files"


def generate_with_openai(diff_text: str, summary: DiffSummary, config: Config,
                         forced_type: Optional[str] = None,
                         forced_scope: Optional[str] = None) -> Optional[str]:
    """Generate commit message using OpenAI API."""
    try:
        import openai
    except ImportError:
        return None
    
    api_key = config.openai_api_key
    if not api_key:
        return None
    
    client = openai.OpenAI(api_key=api_key)
    
    model = config.model or "gpt-4o-mini"
    
    # Build the prompt
    system_prompt = build_system_prompt(summary, forced_type, forced_scope)
    user_prompt = build_user_prompt(diff_text, summary, forced_type, forced_scope)
    
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.3,
            max_tokens=100
        )
        
        message = response.choices[0].message.content.strip()
        
        # Clean up the message
        message = clean_generated_message(message)
        
        # Add emoji if requested
        if config.use_emoji:
            commit_type = forced_type or determine_commit_type(summary)
            if commit_type in GITMOJI_MAP:
                if not message.startswith(GITMOJI_MAP[commit_type]):
                    message = f"{GITMOJI_MAP[commit_type]} {message}"
        
        return truncate_message(message)
    
    except Exception:
        return None


def generate_with_anthropic(diff_text: str, summary: DiffSummary, config: Config,
                            forced_type: Optional[str] = None,
                            forced_scope: Optional[str] = None) -> Optional[str]:
    """Generate commit message using Anthropic API."""
    try:
        import anthropic
    except ImportError:
        return None
    
    api_key = config.anthropic_api_key
    if not api_key:
        return None
    
    client = anthropic.Anthropic(api_key=api_key)
    
    model = config.model or "claude-3-haiku-20240307"
    
    system_prompt = build_system_prompt(summary, forced_type, forced_scope)
    user_prompt = build_user_prompt(diff_text, summary, forced_type, forced_scope)
    
    try:
        response = client.messages.create(
            model=model,
            max_tokens=100,
            temperature=0.3,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}]
        )
        
        message = response.content[0].text.strip()
        message = clean_generated_message(message)
        
        if config.use_emoji:
            commit_type = forced_type or determine_commit_type(summary)
            if commit_type in GITMOJI_MAP:
                if not message.startswith(GITMOJI_MAP[commit_type]):
                    message = f"{GITMOJI_MAP[commit_type]} {message}"
        
        return truncate_message(message)
    
    except Exception:
        return None


def generate_with_ollama(diff_text: str, summary: DiffSummary, config: Config,
                         forced_type: Optional[str] = None,
                         forced_scope: Optional[str] = None) -> Optional[str]:
    """Generate commit message using local Ollama instance."""
    try:
        import urllib.request
        import urllib.error
    except ImportError:
        return None
    
    model = config.model or "llama3.2"
    
    system_prompt = build_system_prompt(summary, forced_type, forced_scope)
    user_prompt = build_user_prompt(diff_text, summary, forced_type, forced_scope)
    
    data = {
        "model": model,
        "prompt": f"{system_prompt}\n\n{user_prompt}",
        "stream": False,
        "options": {"temperature": 0.3}
    }
    
    try:
        req = urllib.request.Request(
            f"{config.ollama_host}/api/generate",
            data=json.dumps(data).encode(),
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        
        with urllib.request.urlopen(req, timeout=60) as response:
            result = json.loads(response.read().decode())
            message = result.get("response", "").strip()
            message = clean_generated_message(message)
            
            if config.use_emoji:
                commit_type = forced_type or determine_commit_type(summary)
                if commit_type in GITMOJI_MAP:
                    if not message.startswith(GITMOJI_MAP[commit_type]):
                        message = f"{GITMOJI_MAP[commit_type]} {message}"
            
            return truncate_message(message)
    
    except Exception:
        return None


def build_system_prompt(summary: DiffSummary, forced_type: Optional[str],
                        forced_scope: Optional[str]) -> str:
    """Build the system prompt for AI generation."""
    prompt = """You are an expert at writing git commit messages.

Follow the Conventional Commits specification:
- Format: <type>[optional scope]: <description>
- Types: feat, fix, docs, style, refactor, perf, test, chore
- Use imperative mood ("add" not "added")
- Keep descriptions under 72 characters
- Be concise but descriptive

Examples:
- feat(auth): add OAuth2 login support
- fix(api): resolve null pointer in user endpoint  
- docs(readme): update installation instructions
- test(utils): add unit tests for helper functions
"""
    
    if forced_type:
        prompt += f"\nUse commit type: {forced_type}\n"
    
    if forced_scope:
        prompt += f"\nUse scope: {forced_scope}\n"
    
    return prompt


def build_user_prompt(diff_text: str, summary: DiffSummary, 
                      forced_type: Optional[str],
                      forced_scope: Optional[str]) -> str:
    """Build the user prompt with diff information."""
    lines = ["Generate a conventional commit message for the following changes:\n"]
    
    # Add file summary
    lines.append("Files changed:")
    for f in summary.files[:20]:  # Limit files listed
        change_indicator = "M"
        if f.change_type == ChangeType.ADDED:
            change_indicator = "A"
        elif f.change_type == ChangeType.DELETED:
            change_indicator = "D"
        elif f.change_type == ChangeType.RENAMED:
            change_indicator = "R"
        
        lines.append(f"  {change_indicator} {f.path} (+{f.additions}/-{f.deletions})")
    
    if len(summary.files) > 20:
        lines.append(f"  ... and {len(summary.files) - 20} more files")
    
    lines.append(f"\nTotal: {summary.total_additions} additions, {summary.total_deletions} deletions\n")
    
    # Add the actual diff (truncated)
    lines.append("Diff:")
    lines.append("```diff")
    
    # Include diff but limit size
    diff_lines = diff_text.split("\n")[:150]
    lines.extend(diff_lines)
    
    if len(diff_text.split("\n")) > 150:
        lines.append("...")
    
    lines.append("```")
    lines.append("\nCommit message (respond with only the message, nothing else):")
    
    return "\n".join(lines)


def clean_generated_message(message: str) -> str:
    """Clean up an AI-generated commit message."""
    # Remove code fences
    message = re.sub(r'^```\w*\n?', '', message)
    message = re.sub(r'\n?```$', '', message)
    
    # Remove quotes
    message = message.strip('"\'')
    
    # Remove "Commit message:" or similar prefixes
    message = re.sub(r'^(commit message[:\-]?\s*)', '', message, flags=re.IGNORECASE)
    
    return message.strip()


def generate_commit_message(diff_text: str, summary: DiffSummary, config: Config,
                           forced_type: Optional[str] = None,
                           forced_scope: Optional[str] = None) -> str:
    """Generate a commit message using the best available method.
    
    Priority:
    1. AI provider if configured and available
    2. Rule-based engine (always works)
    """
    # Try AI if configured
    if config.ai_provider == "openai" and config.is_ai_available():
        message = generate_with_openai(diff_text, summary, config, forced_type, forced_scope)
        if message:
            return message
    
    elif config.ai_provider == "anthropic" and config.is_ai_available():
        message = generate_with_anthropic(diff_text, summary, config, forced_type, forced_scope)
        if message:
            return message
    
    elif config.ai_provider == "ollama":
        message = generate_with_ollama(diff_text, summary, config, forced_type, forced_scope)
        if message:
            return message
    
    # Fall back to rule-based engine
    return generate_rule_based(summary, config, forced_type, forced_scope)


# Import Path for use in generator
from pathlib import Path
