"""CLI interface for CybrCommit."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path
from typing import Optional, Tuple

from cybrcommit import __version__
from cybrcommit.config import Config
from cybrcommit.diff_parser import (
    check_git_repo, get_staged_diff, get_unstaged_diff,
    parse_diff, stage_all, commit, run_git_command
)
from cybrcommit.generator import generate_commit_message


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser for CybrCommit."""
    parser = argparse.ArgumentParser(
        prog="CybrCommit",
        description="🤖 AI-powered git commit message generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  CybrCommit                    # Interactive mode (default)
  CybrCommit --auto             # Auto-commit without confirmation
  CybrCommit --dry              # Show message only, don't commit
  CybrCommit --scope api        # Specify commit scope
  CybrCommit --type feat        # Override commit type
  CybrCommit --ai openai        # Use OpenAI for generation
  CybrCommit --emoji            # Add gitmoji to commits
  CybrCommit --all              # Stage all changes first

Environment Variables:
  OPENAI_API_KEY              # OpenAI API key
  ANTHROPIC_API_KEY           # Anthropic API key
  OLLAMA_HOST                 # Ollama host URL (default: http://localhost:11434)
  AI_COMMIT_PROVIDER          # Default AI provider (openai/anthropic/ollama)
  AI_COMMIT_MODEL             # Default model to use
  AI_COMMIT_EMOJI             # Enable emoji by default (1/true/yes)
  AI_COMMIT_AUTO              # Enable auto mode by default (1/true/yes)
        """
    )
    
    parser.add_argument(
        "-v", "--version",
        action="version",
        version=f"%(prog)s {__version__}"
    )
    
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Auto-commit without confirmation"
    )
    
    parser.add_argument(
        "--dry",
        action="store_true",
        help="Show the generated message without committing"
    )
    
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Stage all changes before committing"
    )
    
    parser.add_argument(
        "--scope",
        type=str,
        metavar="SCOPE",
        help="Specify the commit scope (e.g., 'api', 'auth')"
    )
    
    parser.add_argument(
        "--type",
        type=str,
        choices=["feat", "fix", "docs", "style", "refactor", "perf", "test", "chore", "ci", "build"],
        metavar="TYPE",
        help="Override the commit type"
    )
    
    parser.add_argument(
        "--ai",
        type=str,
        choices=["openai", "anthropic", "ollama"],
        metavar="PROVIDER",
        help="Use AI provider for generation (requires API key for openai/anthropic)"
    )
    
    parser.add_argument(
        "--model",
        type=str,
        metavar="MODEL",
        help="Specify the AI model (e.g., 'gpt-4', 'claude-3-opus')"
    )
    
    parser.add_argument(
        "--emoji", "-e",
        action="store_true",
        help="Add gitmoji to the commit message"
    )
    
    parser.add_argument(
        "--no-emoji",
        action="store_true",
        help="Disable emoji even if enabled in config"
    )
    
    parser.add_argument(
        "--message", "-m",
        type=str,
        metavar="MSG",
        help="Use this message instead of generating one"
    )
    
    return parser


def print_banner() -> None:
    """Print the CybrCommit banner."""
    print("🤖 CybrCommit - AI-powered commit messages")
    print()


def print_diff_summary(summary) -> None:
    """Print a summary of the changes."""
    print(f"📁 {len(summary.files)} file{'s' if len(summary.files) != 1 else ''} changed")
    print(f"   +{summary.total_additions} additions, -{summary.total_deletions} deletions")
    
    # Show file breakdown
    if summary.files:
        print("\n   Files:")
        for f in summary.files[:10]:
            icon = "📝"
            if f.change_type.value == "added":
                icon = "➕"
            elif f.change_type.value == "deleted":
                icon = "🗑️"
            elif f.change_type.value == "renamed":
                icon = "📛"
            
            print(f"   {icon} {f.path}")
        
        if len(summary.files) > 10:
            print(f"   ... and {len(summary.files) - 10} more")
    
    print()


def edit_message(message: str) -> str:
    """Open an editor to let the user edit the message."""
    # Get editor from environment
    editor = (
        subprocess.run(["git", "var", "GIT_EDITOR"], capture_output=True, text=True).stdout.strip()
        or subprocess.run(["var", "EDITOR"], capture_output=True, text=True).stdout.strip()
        or "vim"
    )
    
    # Create temp file with message
    import tempfile
    import os
    
    with tempfile.NamedTemporaryFile(mode="w+", suffix=".txt", delete=False) as f:
        f.write(message)
        f.write("\n")
        f.write("# Edit your commit message above. Lines starting with # will be ignored.\n")
        f.write("# Save and close the editor when done.\n")
        temp_path = f.name
    
    try:
        # Open editor
        subprocess.run([editor, temp_path], check=True)
        
        # Read back the message
        with open(temp_path, "r") as f:
            lines = []
            for line in f:
                line = line.rstrip()
                if not line.startswith("#"):
                    lines.append(line)
            
            edited = "\n".join(lines).strip()
            return edited if edited else message
    
    except Exception:
        return message
    
    finally:
        try:
            os.unlink(temp_path)
        except Exception:
            pass


def interactive_commit(message: str, summary) -> Tuple[bool, str]:
    """Handle interactive commit flow.
    
    Returns (should_commit, final_message).
    """
    print("💬 Generated commit message:")
    print(f"   {message}")
    print()
    
    while True:
        try:
            response = input("Commit? [y]es, [e]dit, [r]egenerate, [n]o: ").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print("\n❌ Cancelled")
            return False, ""
        
        if response in ("y", "yes", ""):
            return True, message
        
        elif response in ("e", "edit"):
            edited = edit_message(message)
            if edited != message:
                print(f"\n💬 Edited message:\n   {edited}\n")
                message = edited
            else:
                print("\n💬 Message unchanged\n")
        
        elif response in ("r", "regenerate"):
            return None, ""  # Signal to regenerate
        
        elif response in ("n", "no", "q", "quit", "cancel"):
            print("❌ Cancelled")
            return False, ""
        
        else:
            print("Please enter: y (yes), e (edit), r (regenerate), or n (no)")


def main(args: Optional[list] = None) -> int:
    """Main entry point for CybrCommit."""
    parser = create_parser()
    parsed = parser.parse_args(args)
    
    # Load configuration
    config = Config.load()
    
    # Override config with CLI arguments
    if parsed.ai:
        config.ai_provider = parsed.ai
    if parsed.model:
        config.model = parsed.model
    if parsed.emoji:
        config.use_emoji = True
    if parsed.no_emoji:
        config.use_emoji = False
    
    # Check if we're in a git repo
    if not check_git_repo():
        print("❌ Error: Not a git repository", file=sys.stderr)
        return 1
    
    # Stage all if requested
    if parsed.all:
        print("📦 Staging all changes...")
        if not stage_all():
            print("❌ Error: Failed to stage changes", file=sys.stderr)
            return 1
    
    # Get the diff
    diff_text = get_staged_diff(max_lines=config.max_diff_lines)
    is_staged = True
    
    if not diff_text:
        # Try unstaged changes
        diff_text = get_unstaged_diff(max_lines=config.max_diff_lines)
        is_staged = False
        
        if not diff_text:
            print("ℹ️  No changes to commit")
            print("   Stage changes with 'git add' or use --all to stage everything")
            return 0
        
        print("ℹ️  Using unstaged changes (nothing staged)")
        print("   Tip: Use 'git add' to stage specific files, or --all to stage all\n")
    
    # Parse the diff
    summary = parse_diff(diff_text, staged=is_staged)
    
    # Show banner and summary
    if not parsed.auto and not parsed.dry:
        print_banner()
    
    if not parsed.auto:
        print_diff_summary(summary)
    
    # Use provided message or generate one
    if parsed.message:
        message = parsed.message
        if parsed.type:
            # Prepend type if specified
            scope_str = f"({parsed.scope})" if parsed.scope else ""
            message = f"{parsed.type}{scope_str}: {message}"
    else:
        # Generate message
        if not parsed.auto and not parsed.dry:
            print("🤔 Generating commit message...")
        
        message = generate_commit_message(
            diff_text, summary, config,
            forced_type=parsed.type,
            forced_scope=parsed.scope
        )
    
    # Dry run mode
    if parsed.dry:
        print(message)
        return 0
    
    # Auto mode
    if parsed.auto or config.auto_commit:
        print(f"📝 {message}")
    else:
        # Interactive mode
        while True:
            result = interactive_commit(message, summary)
            
            if result[0] is None:
                # Regenerate requested
                print("🤔 Regenerating...\n")
                message = generate_commit_message(
                    diff_text, summary, config,
                    forced_type=parsed.type,
                    forced_scope=parsed.scope
                )
                continue
            
            should_commit, final_message = result
            if not should_commit:
                return 0
            
            message = final_message
            break
    
    # Create the commit
    # If we used unstaged changes, stage them first
    if not is_staged and not parsed.all:
        print("📦 Staging changes...")
        if not stage_all():
            print("❌ Error: Failed to stage changes", file=sys.stderr)
            return 1
    
    success, output = commit(message)
    
    if success:
        print(f"✅ Committed: {message}")
        return 0
    else:
        print(f"❌ Commit failed: {output}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
