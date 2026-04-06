"""Init command implementation — scaffold a new project."""

from __future__ import annotations

import shutil
from pathlib import Path

import typer

from agentmodelctl.reporter import console

TEMPLATES_DIR = Path(__file__).parent / "templates"
VALID_TEMPLATES = ["customer-support", "productivity", "sales", "custom"]

# Map CLI template names to directory names
TEMPLATE_DIR_MAP = {
    "customer-support": "customer_support",
    "productivity": "productivity",
    "sales": "sales",
    "custom": None,
}


def run_init(template: str = "custom") -> None:
    """Scaffold a new agentmodelctl project."""
    if template not in VALID_TEMPLATES:
        console.print(f"[red]✗[/red] Unknown template '{template}'.")
        console.print(f"  Available: {', '.join(VALID_TEMPLATES)}")
        raise typer.Exit(code=1)

    project_root = Path.cwd()

    # Check if project already exists
    if (project_root / "agentmodelctl.yaml").exists():
        console.print("[yellow]⚠[/yellow] agentmodelctl.yaml already exists in this directory.")
        if not typer.confirm("Overwrite existing project?", default=False):
            raise typer.Exit()

    # Create directories
    agents_dir = project_root / "agents"
    evals_dir = project_root / "evals"
    agents_dir.mkdir(exist_ok=True)
    evals_dir.mkdir(exist_ok=True)

    # Copy shared template files
    _copy_template(TEMPLATES_DIR / "agentmodelctl.yaml", project_root / "agentmodelctl.yaml")
    _copy_template(TEMPLATES_DIR / "models.yaml", project_root / "models.yaml")
    _copy_template(TEMPLATES_DIR / "env.example", project_root / ".env.example")

    # Create .gitignore (append if exists)
    _ensure_gitignore(project_root)

    # Copy template-specific agent
    template_dir_name = TEMPLATE_DIR_MAP.get(template)
    if template_dir_name:
        template_dir = TEMPLATES_DIR / template_dir_name
        if template_dir.exists():
            agent_src = template_dir / "agent.yaml"
            if agent_src.exists():
                agent_name = template.replace("-", "_")
                _copy_template(agent_src, agents_dir / f"{template.replace('_', '-')}.yaml")

            eval_src = template_dir / "eval.yaml"
            if eval_src.exists():
                eval_agent_dir = evals_dir / template.replace("_", "-")
                eval_agent_dir.mkdir(exist_ok=True)
                _copy_template(eval_src, eval_agent_dir / "basics.yaml")

    # Print success
    console.print(f"\n[green]✓[/green] Created agentmodelctl project ({template} template):\n")
    console.print("  ├── agentmodelctl.yaml")
    console.print("  ├── models.yaml")
    console.print("  ├── .env.example        ← copy to .env and add your API keys")
    console.print("  ├── .gitignore           ← .env already excluded")
    console.print("  └── agents/")
    if template_dir_name:
        console.print(f"      └── {template}.yaml")

    console.print("\n[bold]Next steps:[/bold]")
    console.print("  1. cp .env.example .env && edit .env")
    console.print("  2. agentmodelctl eval --auto-generate")
    console.print("  3. agentmodelctl switch reasoning gpt-4o --dry-run")


def _copy_template(src: Path, dest: Path) -> None:
    """Copy a template file if it exists."""
    if src.exists():
        shutil.copy2(src, dest)
    else:
        # Write a minimal placeholder if template doesn't exist yet
        dest.touch()


def _ensure_gitignore(project_root: Path) -> None:
    """Ensure .gitignore exists and contains .env entries."""
    gitignore_path = project_root / ".gitignore"
    gitignore_template = TEMPLATES_DIR / "gitignore"

    required_entries = {".env", ".env.local", ".env.*.local", "__pycache__/"}

    if gitignore_path.exists():
        existing = gitignore_path.read_text()
        existing_lines = set(existing.strip().splitlines())
        missing = required_entries - existing_lines
        if missing:
            with open(gitignore_path, "a") as f:
                f.write("\n# Added by agentmodelctl\n")
                for entry in sorted(missing):
                    f.write(f"{entry}\n")
    elif gitignore_template.exists():
        shutil.copy2(gitignore_template, gitignore_path)
    else:
        gitignore_path.write_text(
            "# agentmodelctl\n"
            ".env\n"
            ".env.local\n"
            ".env.*.local\n"
            "__pycache__/\n"
        )
