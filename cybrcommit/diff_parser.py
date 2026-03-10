"""Intelligent git diff parser for CybrCommit."""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import List, Optional, Tuple


class ChangeType(Enum):
    """Types of file changes."""
    ADDED = "added"
    DELETED = "deleted"
    MODIFIED = "modified"
    RENAMED = "renamed"
    COPIED = "copied"
    TYPE_CHANGED = "type_changed"
    UNMERGED = "unmerged"
    UNKNOWN = "unknown"


class FileType(Enum):
    """Categories of files for intelligent analysis."""
    SOURCE_CODE = "source"
    TEST = "test"
    CONFIG = "config"
    DOCUMENTATION = "docs"
    STYLE = "style"
    DEPENDENCY = "dependency"
    BUILD = "build"
    CI_CD = "ci"
    ASSET = "asset"
    OTHER = "other"


@dataclass
class FileChange:
    """Represents a single file change in a diff."""
    path: str
    change_type: ChangeType
    additions: int = 0
    deletions: int = 0
    old_path: Optional[str] = None
    is_binary: bool = False
    diff_content: List[str] = field(default_factory=list)
    
    @property
    def file_type(self) -> FileType:
        """Determine the type of file based on its path and name."""
        path_lower = self.path.lower()
        name = Path(self.path).name.lower()
        
        # Test files
        if any(pattern in path_lower for pattern in [
            "test", "tests", "spec", "__tests__", 
            ".test.", ".spec.", "_test.", "_spec.",
            "test_", "conftest", "pytest", "jest"
        ]):
            return FileType.TEST
        
        # Dependencies (check before documentation to catch requirements.txt, etc)
        if any(name.endswith(ext) for ext in [
            "requirements.txt", "package.json", "yarn.lock",
            "package-lock.json", "Cargo.toml", "Cargo.lock",
            "Gemfile", "Gemfile.lock", "composer.json", "composer.lock",
            "go.mod", "go.sum", "pom.xml", "build.gradle",
            "poetry.lock", "Pipfile.lock"
        ]):
            return FileType.DEPENDENCY
        
        # Documentation files
        if any(pattern in name for pattern in [
            "readme", "changelog", "license", "contributing",
            "authors", "history", "news", "notice"
        ]) or name.endswith((".md", ".rst", ".txt", ".adoc")):
            return FileType.DOCUMENTATION
        
        # Config files
        if any(pattern in name for pattern in [
            ".env", ".ini", ".cfg", ".conf", ".yaml", ".yml",
            ".json", ".toml", "config", ".editorconfig", ".gitignore",
            ".dockerignore", ".npmignore", ".flake8", ".pylintrc",
            ".prettierrc", ".eslintrc", ".babelrc", "tsconfig",
            "jsconfig", "vite.config", "webpack.config", "rollup.config",
            ".pre-commit-config", ".github", ".gitlab-ci", ".travis.yml",
            "Makefile", "Dockerfile", "docker-compose", "tox.ini",
            "setup.cfg", "pyproject.toml", "package.json", "Cargo.toml",
            "composer.json", "Gemfile", "requirements", "Pipfile",
            "poetry.lock", "yarn.lock", "package-lock.json"
        ]):
            return FileType.CONFIG
        
        # Style files
        if name.endswith((".css", ".scss", ".sass", ".less", ".styl")):
            return FileType.STYLE
        
        # Build files
        if any(pattern in name for pattern in [
            "Makefile", "CMakeLists.txt", "setup.py", "setup.cfg",
            "build.sh", "build.py", "configure", "configure.ac",
            "meson.build", "build.gradle", "pom.xml"
        ]):
            return FileType.BUILD
        
        # CI/CD files
        if any(pattern in path_lower for pattern in [
            ".github/workflows", ".gitlab-ci", ".travis.yml",
            ".circleci", "jenkins", ".drone.yml", "azure-pipelines",
            ".buildkite", "appveyor.yml"
        ]):
            return FileType.CI_CD
        
        # Asset files (images, fonts, etc)
        if any(name.endswith(ext) for ext in [
            ".png", ".jpg", ".jpeg", ".gif", ".svg", ".ico",
            ".woff", ".woff2", ".ttf", ".otf", ".eot",
            ".mp3", ".mp4", ".wav", ".avi", ".mov",
            ".pdf", ".zip", ".tar", ".gz", ".rar"
        ]):
            return FileType.ASSET
        
        return FileType.SOURCE_CODE
    
    @property
    def extension(self) -> Optional[str]:
        """Get the file extension."""
        path = Path(self.path)
        if path.suffix:
            return path.suffix.lstrip(".").lower()
        return None
    
    @property
    def is_rename(self) -> bool:
        """Check if this is a rename operation."""
        return self.change_type == ChangeType.RENAMED and self.old_path is not None


@dataclass
class DiffSummary:
    """Summary of a git diff."""
    files: List[FileChange] = field(default_factory=list)
    total_additions: int = 0
    total_deletions: int = 0
    is_staged: bool = True
    
    def get_by_type(self, file_type: FileType) -> List[FileChange]:
        """Get all files of a specific type."""
        return [f for f in self.files if f.file_type == file_type]
    
    def get_by_change_type(self, change_type: ChangeType) -> List[FileChange]:
        """Get all files with a specific change type."""
        return [f for f in self.files if f.change_type == change_type]
    
    @property
    def has_tests(self) -> bool:
        """Check if any test files were changed."""
        return any(f.file_type == FileType.TEST for f in self.files)
    
    @property
    def has_docs(self) -> bool:
        """Check if any documentation files were changed."""
        return any(f.file_type == FileType.DOCUMENTATION for f in self.files)
    
    @property
    def has_config(self) -> bool:
        """Check if any config files were changed."""
        return any(f.file_type == FileType.CONFIG for f in self.files)
    
    @property
    def has_dependencies(self) -> bool:
        """Check if any dependency files were changed."""
        return any(f.file_type == FileType.DEPENDENCY for f in self.files)
    
    @property
    def has_renames(self) -> bool:
        """Check if any files were renamed."""
        return any(f.is_rename for f in self.files)
    
    @property
    def primary_languages(self) -> List[str]:
        """Detect primary programming languages from file extensions."""
        extensions: dict[str, int] = {}
        for f in self.files:
            if f.extension and f.file_type == FileType.SOURCE_CODE:
                ext = f.extension
                extensions[ext] = extensions.get(ext, 0) + 1
        
        # Sort by frequency
        sorted_exts = sorted(extensions.items(), key=lambda x: x[1], reverse=True)
        return [ext for ext, _ in sorted_exts[:3]]


def run_git_command(args: List[str], cwd: Optional[str] = None) -> Tuple[int, str, str]:
    """Run a git command and return (returncode, stdout, stderr)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            cwd=cwd
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return 1, "", "git command not found"
    except Exception as e:
        return 1, "", str(e)


def check_git_repo(cwd: Optional[str] = None) -> bool:
    """Check if we're in a git repository."""
    returncode, _, _ = run_git_command(["rev-parse", "--git-dir"], cwd=cwd)
    return returncode == 0


def get_staged_diff(cwd: Optional[str] = None, max_lines: Optional[int] = None) -> Optional[str]:
    """Get the staged diff. Returns None if no staged changes."""
    returncode, stdout, stderr = run_git_command(
        ["diff", "--staged", "--no-color"], 
        cwd=cwd
    )
    
    if returncode != 0:
        return None
    
    if not stdout.strip():
        return None
    
    if max_lines:
        lines = stdout.split("\n")
        if len(lines) > max_lines:
            # Keep header info and truncate
            return "\n".join(lines[:max_lines]) + "\n\n[... diff truncated ...]"
    
    return stdout


def get_unstaged_diff(cwd: Optional[str] = None, max_lines: Optional[int] = None) -> Optional[str]:
    """Get the unstaged diff. Returns None if no unstaged changes."""
    returncode, stdout, stderr = run_git_command(
        ["diff", "--no-color"],
        cwd=cwd
    )
    
    if returncode != 0:
        return None
    
    if not stdout.strip():
        return None
    
    if max_lines:
        lines = stdout.split("\n")
        if len(lines) > max_lines:
            return "\n".join(lines[:max_lines]) + "\n\n[... diff truncated ...]"
    
    return stdout


def get_diff_stats(cwd: Optional[str] = None, staged: bool = True) -> Optional[str]:
    """Get diff statistics (--stat)."""
    args = ["diff", "--stat"]
    if staged:
        args.append("--staged")
    
    returncode, stdout, _ = run_git_command(args, cwd=cwd)
    if returncode == 0:
        return stdout
    return None


def stage_all(cwd: Optional[str] = None) -> bool:
    """Stage all changes (git add -A)."""
    returncode, _, _ = run_git_command(["add", "-A"], cwd=cwd)
    return returncode == 0


def parse_diff(diff_text: str, staged: bool = True) -> DiffSummary:
    """Parse a git diff into a structured summary."""
    summary = DiffSummary(is_staged=staged)
    
    if not diff_text:
        return summary
    
    lines = diff_text.split("\n")
    current_file: Optional[FileChange] = None
    in_diff_content = False
    
    # Regex patterns for parsing
    diff_header_pattern = re.compile(r'^diff --git a/(.+) b/(.+)$')
    index_pattern = re.compile(r'^index [a-f0-9]+\.\.[a-f0-9]+')
    new_file_pattern = re.compile(r'^new file mode')
    deleted_file_pattern = re.compile(r'^deleted file mode')
    rename_from_pattern = re.compile(r'^rename from (.+)$')
    rename_to_pattern = re.compile(r'^rename to (.+)$')
    similarity_pattern = re.compile(r'^similarity index (\d+)%')
    old_mode_pattern = re.compile(r'^old mode')
    new_mode_pattern = re.compile(r'^new mode')
    binary_pattern = re.compile(r'^Binary files (.+) and (.+) differ$')
    
    i = 0
    while i < len(lines):
        line = lines[i]
        
        # Start of a new file diff
        match = diff_header_pattern.match(line)
        if match:
            # Save previous file if exists
            if current_file:
                summary.files.append(current_file)
            
            old_path = match.group(1)
            new_path = match.group(2)
            
            current_file = FileChange(
                path=new_path,
                change_type=ChangeType.MODIFIED,
                old_path=old_path if old_path != new_path else None
            )
            in_diff_content = False
            i += 1
            continue
        
        if current_file is None:
            i += 1
            continue
        
        # Binary file detection
        binary_match = binary_pattern.match(line)
        if binary_match:
            current_file.is_binary = True
            i += 1
            continue
        
        # New file
        if new_file_pattern.match(line):
            current_file.change_type = ChangeType.ADDED
            i += 1
            continue
        
        # Deleted file
        if deleted_file_pattern.match(line):
            current_file.change_type = ChangeType.DELETED
            i += 1
            continue
        
        # Rename detection
        rename_from = rename_from_pattern.match(line)
        if rename_from:
            current_file.old_path = rename_from.group(1)
            current_file.change_type = ChangeType.RENAMED
            i += 1
            continue
        
        rename_to = rename_to_pattern.match(line)
        if rename_to:
            i += 1
            continue
        
        # Similarity index (rename)
        similarity = similarity_pattern.match(line)
        if similarity:
            # High similarity usually means rename
            i += 1
            continue
        
        # Mode changes (skip)
        if old_mode_pattern.match(line) or new_mode_pattern.match(line):
            i += 1
            continue
        
        # Skip index lines
        if index_pattern.match(line):
            i += 1
            continue
        
        # Skip --- and +++ lines
        if line.startswith("--- ") or line.startswith("+++ "):
            in_diff_content = True
            i += 1
            continue
        
        # Parse hunk headers and content
        if in_diff_content and line.startswith("@@"):
            # Hunk header - count actual changes
            i += 1
            while i < len(lines) and not lines[i].startswith("@@") and not lines[i].startswith("diff "):
                content_line = lines[i]
                if content_line.startswith("+") and not content_line.startswith("+++"):
                    current_file.additions += 1
                    summary.total_additions += 1
                    current_file.diff_content.append(content_line[1:])
                elif content_line.startswith("-") and not content_line.startswith("---"):
                    current_file.deletions += 1
                    summary.total_deletions += 1
                i += 1
            continue
        
        i += 1
    
    # Don't forget the last file
    if current_file:
        summary.files.append(current_file)
    
    return summary


def get_file_status(cwd: Optional[str] = None) -> List[Tuple[str, str]]:
    """Get file status using git status --porcelain.
    
    Returns list of (status, path) tuples.
    """
    returncode, stdout, _ = run_git_command(
        ["status", "--porcelain", "-u"],
        cwd=cwd
    )
    
    if returncode != 0:
        return []
    
    files = []
    for line in stdout.strip().split("\n"):
        if not line:
            continue
        # Format: XY PATH or XY ORIG_PATH -> PATH
        if len(line) >= 3:
            status = line[:2]
            path_part = line[3:]
            files.append((status, path_part))
    
    return files


def commit(message: str, cwd: Optional[str] = None) -> Tuple[bool, str]:
    """Create a git commit with the given message.
    
    Returns (success, error_message).
    """
    returncode, stdout, stderr = run_git_command(
        ["commit", "-m", message],
        cwd=cwd
    )
    
    if returncode == 0:
        return True, stdout
    else:
        return False, stderr or stdout
