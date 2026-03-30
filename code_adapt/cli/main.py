"""code-adapt CLI — Typer application with all commands."""

from __future__ import annotations

import json as json_mod
import logging
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

logger = logging.getLogger(__name__)

import typer
from rich import print as rprint
from rich.console import Console
from rich.table import Table

from ..errors import (
    AdaptError,
    AdaptationNotFoundError,
    AuthError,
    NotInitializedError,
    RepoNotFoundError,
    ValidationError,
)
from ..models import (
    Adaptation,
    AdaptationStatus,
    Analysis,
    Classification,
    ContributionRules,
    ContributionSplit,
    DiffStats,
    LearningRecord,
    Observation,
    Plan,
    PlanStep,
    Policy,
    Profile,
    RelevanceScore,
    Repository,
    RiskScore,
    Strategy,
    SuggestedAction,
)
from ..services.assessor import assess_relevance
from ..services.auth import get_github_token, get_token
from ..services.classifier import (
    classify_change,
    extract_intent,
    extract_modules,
    generate_summary,
)
from ..services.github import (
    fetch_commit_diff,
    fetch_commits,
    fetch_pr_diff,
    fetch_pull_requests,
    fetch_release_info,
    fetch_releases,
)
from ..services.gitee import GiteeClient
from ..services.gitlab import GitLabClient
from ..services.provider import Provider, api_base_url, detect_provider
from ..services.provider import parse_repo_url as provider_parse_repo_url
from ..services.id_generator import generate_id
from ..storage import (
    ensure_dir,
    get_adapt_dir,
    is_initialized,
    parse_duration,
    read_json,
    read_yaml,
    write_json,
    write_yaml,
)

app = typer.Typer(
    name="code-adapt",
    help="Observe. Adapt. Contribute. — CLI for the Adaptation Lifecycle",
    no_args_is_help=True,
)
console = Console()

# Global option
JSON_OPTION = Annotated[bool, typer.Option("--json", help="Output results as JSON")]


# ── Helpers ──────────────────────────────────────────────────────────────────


def _require_init() -> None:
    if not is_initialized():
        raise NotInitializedError()


def _output(data: object, *, as_json: bool = False) -> None:
    if as_json:
        if hasattr(data, "model_dump"):
            rprint(json_mod.dumps(data.model_dump(), indent=2, default=str))  # type: ignore[union-attr]
        else:
            rprint(json_mod.dumps(data, indent=2, default=str))
    else:
        rprint(data)


def _output_table(headers: list[str], rows: list[list[str]]) -> None:
    table = Table()
    for h in headers:
        table.add_column(h)
    for row in rows:
        table.add_row(*row)
    console.print(table)


def _load_repos() -> list[Repository]:
    data = read_yaml(get_adapt_dir() / "repos.yaml")
    if not data:
        return []
    return [Repository(**r) for r in data]


def _save_repos(repos: list[Repository]) -> None:
    write_yaml(get_adapt_dir() / "repos.yaml", [r.model_dump() for r in repos])


def _load_all_adaptations() -> list[Adaptation]:
    adp_dir = get_adapt_dir() / "adaptations"
    if not adp_dir.exists():
        return []
    adaptations = []
    for entry in adp_dir.iterdir():
        if not entry.is_dir():
            continue
        yaml_path = entry / "adaptation.yaml"
        if yaml_path.exists():
            try:
                adaptations.append(Adaptation(**read_yaml(yaml_path)))
            except Exception as exc:
                logger.debug("Failed to load adaptation from %s: %s", yaml_path, exc)
    return adaptations


def _load_all_observations() -> list[Observation]:
    analyses_dir = get_adapt_dir() / "analyses"
    if not analyses_dir.exists():
        return []
    observations = []
    for f in sorted(analyses_dir.glob("obs_*.json")):
        try:
            observations.append(Observation(**read_json(f)))
        except Exception as exc:
            logger.debug("Failed to load observation from %s: %s", f, exc)
    return observations


def _find_analysis(source_ref: str) -> Analysis | None:
    analyses_dir = get_adapt_dir() / "analyses"
    if not analyses_dir.exists():
        return None
    for f in analyses_dir.glob("ana_*.json"):
        try:
            a = Analysis(**read_json(f))
            if a.source_ref == source_ref:
                return a
        except Exception as exc:
            logger.debug("Failed to load analysis from %s: %s", f, exc)
    return None


def _parse_reference(ref: str) -> tuple[str, str]:
    """Parse 'pr-123', 'commit-abc', 'release-v1.0' → (type, id)."""
    if ref.startswith("pr-"):
        num = ref[3:]
        if not num.isdigit():
            raise ValidationError(f'Invalid PR reference: "{ref}". Expected format: pr-<number>')
        return "pr", num
    if ref.startswith("commit-"):
        sha = ref[7:]
        if len(sha) < 4:
            raise ValidationError(f'Invalid commit reference: "{ref}". SHA is too short.')
        return "commit", sha
    if ref.startswith("release-"):
        tag = ref[8:]
        if not tag:
            raise ValidationError(f'Invalid release reference: "{ref}". Tag cannot be empty.')
        return "release", tag
    raise ValidationError(
        f'Invalid reference format: "{ref}". Use pr-<number>, commit-<sha>, or release-<tag>.'
    )


def _detect_remote_branch(url: str) -> str:
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--symref", url, "HEAD"],
            capture_output=True,
            text=True,
            timeout=15,
        )
        m = re.search(r"ref:\s+refs/heads/(\S+)\s+HEAD", result.stdout)
        if m:
            return m.group(1)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return "main"


def _detect_local_branch() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.stdout.strip() or "main"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return "main"


def _error_exit(err: AdaptError) -> None:
    rprint(f"[red]Error:[/red] {err}")
    raise typer.Exit(code=err.code)


# ── init ─────────────────────────────────────────────────────────────────────


@app.command()
def init(
    profile: Annotated[Optional[str], typer.Option(help="Use profile template")] = None,
    json: JSON_OPTION = False,
) -> None:
    """Initialize a new code-adapt project."""
    if is_initialized():
        rprint("[yellow]Project is already initialized.[/yellow]")
        raise typer.Exit(1)

    adapt_dir = get_adapt_dir()
    project_name = Path.cwd().name

    for sub in ("cache", "context", "analyses", "adaptations", "reports", "logs", "state"):
        ensure_dir(adapt_dir / sub)

    write_yaml(adapt_dir / "config.yaml", {"version": "1.0"})
    write_yaml(adapt_dir / "repos.yaml", [])
    write_yaml(adapt_dir / "policies.yaml", Policy().model_dump())
    write_yaml(adapt_dir / "profile.yaml", Profile(name=profile or project_name).model_dump())
    write_json(adapt_dir / "state" / "counter.json", {"obs": 0, "ana": 0, "adp": 0, "plan": 0})

    if json:
        _output({"initialized": True, "directory": str(adapt_dir)}, as_json=True)
    else:
        rprint(f"[green]Initialized adapt project in {adapt_dir}[/green]")


# ── repo ─────────────────────────────────────────────────────────────────────

repo_app = typer.Typer(help="Manage upstream and downstream repositories")
app.add_typer(repo_app, name="repo")


@repo_app.command("add")
def repo_add(
    type_: Annotated[str, typer.Argument(metavar="TYPE", help="upstream or downstream")],
    name: str,
    url: str,
    json: JSON_OPTION = False,
) -> None:
    """Add an upstream or downstream repository."""
    _require_init()
    if type_ not in ("upstream", "downstream"):
        _error_exit(AdaptError('Type must be "upstream" or "downstream".'))

    repos = _load_repos()
    if any(r.name == name for r in repos):
        rprint(f'[red]Repository "{name}" is already registered.[/red]')
        raise typer.Exit(1)

    if type_ == "downstream" and url == ".":
        resolved_url = str(Path.cwd())
        default_branch = _detect_local_branch()
        provider = Provider.UNKNOWN.value
    else:
        resolved_url = url
        default_branch = _detect_remote_branch(url)
        provider = detect_provider(url).value

    repo = Repository(
        name=name, url=resolved_url, type=type_, default_branch=default_branch,  # type: ignore[arg-type]
        provider=provider,
    )
    repos.append(repo)
    _save_repos(repos)

    if json:
        _output(repo.model_dump(), as_json=True)
    else:
        rprint(f'[green]Added {type_} repository "{name}" ({resolved_url})[/green]')


@repo_app.command("list")
def repo_list(json: JSON_OPTION = False) -> None:
    """List all registered repositories."""
    _require_init()
    repos = _load_repos()
    if json:
        _output([r.model_dump() for r in repos], as_json=True)
        return
    if not repos:
        rprint('No repositories registered. Use "code-adapt repo add" to add one.')
        return
    _output_table(
        ["Name", "Type", "URL", "Branch"],
        [[r.name, r.type, r.url, r.default_branch] for r in repos],
    )


@repo_app.command("show")
def repo_show(name: str, json: JSON_OPTION = False) -> None:
    """Show details for a single repository."""
    _require_init()
    repos = _load_repos()
    repo = next((r for r in repos if r.name == name), None)
    if not repo:
        rprint(f'[red]Repository "{name}" not found.[/red]')
        raise typer.Exit(1)
    if json:
        _output(repo.model_dump(), as_json=True)
    else:
        rprint(f"Name:           {repo.name}")
        rprint(f"Type:           {repo.type}")
        rprint(f"URL:            {repo.url}")
        rprint(f"Default Branch: {repo.default_branch}")
        rprint(f"License:        {repo.license or 'unknown'}")
        rprint(f"Tech Stack:     {', '.join(repo.tech_stack) if repo.tech_stack else 'none'}")
        rprint(f"Added At:       {repo.added_at}")


# ── observe ──────────────────────────────────────────────────────────────────


@app.command()
def observe(
    repo_name: str,
    since: Annotated[Optional[str], typer.Option(help="Duration e.g. 7d, 2w, 1m")] = None,
    prs: Annotated[bool, typer.Option("--prs", help="Only observe PRs")] = False,
    commits: Annotated[bool, typer.Option("--commits", help="Only observe commits")] = False,
    releases: Annotated[bool, typer.Option("--releases", help="Only observe releases")] = False,
    json: JSON_OPTION = False,
) -> None:
    """Observe upstream changes for a tracked repository.

    Accepts a registered repo name or a URL. When given a URL that is not yet
    registered, the repository is auto-registered as upstream.
    """
    _require_init()

    repos = _load_repos()
    repo = next((r for r in repos if r.name == repo_name), None)

    # Auto-register if a URL was given instead of a registered name
    if not repo and ("/" in repo_name and ("." in repo_name or ":" in repo_name)):
        url = repo_name
        owner, slug = provider_parse_repo_url(url)
        name = slug
        if any(r.name == name for r in repos):
            repo = next(r for r in repos if r.name == name)
        else:
            provider = detect_provider(url).value
            default_branch = _detect_remote_branch(url)
            repo = Repository(
                name=name, url=url, type="upstream",
                default_branch=default_branch, provider=provider,
            )
            repos.append(repo)
            _save_repos(repos)
            rprint(f'[dim]Auto-registered upstream repo "{name}"[/dim]')

    if not repo:
        _error_exit(RepoNotFoundError(repo_name))
        return  # unreachable, for type checker

    # Determine since date
    since_date: datetime | None = None
    since_label: str | None = None
    if since:
        since_date = parse_duration(since)
        since_label = since
    else:
        for obs in reversed(_load_all_observations()):
            if obs.repo_name == repo_name:
                since_date = datetime.fromisoformat(obs.timestamp)
                since_label = obs.timestamp
                break

    fetch_all = not prs and not commits and not releases

    # Route to correct API client based on provider
    try:
        repo_provider = Provider(repo.provider)
    except ValueError:
        rprint(f"[red]Unknown provider '{repo.provider}' for '{repo.name}'. Valid: {', '.join(p.value for p in Provider)}[/red]")
        raise typer.Exit(code=1)
    owner, repo_slug = provider_parse_repo_url(repo.url)

    if repo_provider in (Provider.GITLAB, Provider.GITCODE):
        token = get_token(repo_provider)
        base = api_base_url(repo_provider, repo.url)
        gl = GitLabClient(base, token)
        with console.status(f"Observing changes in {repo_name}..."):
            obs_commits = gl.fetch_commits(owner, repo_slug, since_date) if (fetch_all or commits) else []
            obs_prs = gl.fetch_merge_requests(owner, repo_slug, since_date) if (fetch_all or prs) else []
            obs_releases = gl.fetch_releases(owner, repo_slug, since_date) if (fetch_all or releases) else []
    elif repo_provider == Provider.GITEE:
        token = get_token(repo_provider)
        base = api_base_url(repo_provider, repo.url)
        ge = GiteeClient(base, token)
        with console.status(f"Observing changes in {repo_name}..."):
            obs_commits = ge.fetch_commits(owner, repo_slug, since_date) if (fetch_all or commits) else []
            obs_prs = ge.fetch_pull_requests(owner, repo_slug, since_date) if (fetch_all or prs) else []
            obs_releases = ge.fetch_releases(owner, repo_slug, since_date) if (fetch_all or releases) else []
    else:
        token = get_github_token()
        with console.status(f"Observing changes in {repo_name}..."):
            obs_commits = fetch_commits(token, owner, repo_slug, since_date) if (fetch_all or commits) else []
            obs_prs = fetch_pull_requests(token, owner, repo_slug, since_date) if (fetch_all or prs) else []
            obs_releases = fetch_releases(token, owner, repo_slug, since_date) if (fetch_all or releases) else []

    observation = Observation(
        id=generate_id("obs"),
        repo_name=repo_name,
        since=since_label,
        commits=obs_commits,
        pull_requests=obs_prs,
        releases=obs_releases,
    )

    write_json(get_adapt_dir() / "analyses" / f"{observation.id}.json", observation.model_dump())

    total = len(observation.commits) + len(observation.pull_requests) + len(observation.releases)

    if json:
        _output(observation.model_dump(), as_json=True)
        return

    if total == 0:
        suffix = f" since {since_label}" if since_label else ""
        rprint(f"[yellow]No changes observed{suffix}.[/yellow]")
        rprint(f"Observation saved: {observation.id}")
        return

    rprint(f"[green]Observation {observation.id} saved.[/green]")
    if since_label:
        rprint(f"  Since: {since_label}")
    rprint(f"  Commits:        {len(observation.commits)}")
    rprint(f"  Pull Requests:  {len(observation.pull_requests)}")
    rprint(f"  Releases:       {len(observation.releases)}")

    if observation.commits:
        rprint("\nRecent commits:")
        for c in observation.commits[:10]:
            rprint(f"  {c.sha[:7]} {c.message}")
        if len(observation.commits) > 10:
            rprint(f"  ... and {len(observation.commits) - 10} more")

    if observation.pull_requests:
        rprint("\nPull requests:")
        for pr in observation.pull_requests[:10]:
            rprint(f"  #{pr.number} {pr.title} ({pr.state})")
        if len(observation.pull_requests) > 10:
            rprint(f"  ... and {len(observation.pull_requests) - 10} more")

    if observation.releases:
        rprint("\nReleases:")
        for r in observation.releases[:10]:
            rprint(f"  {r.tag} — {r.name}")

    # Auto-sync observation to cloud
    try:
        from pioneers_cli.cloud import require_cloud, sync_adaptation, CloudError
        api_url, cloud_token = require_cloud()
        sync_adaptation(
            api_url, cloud_token,
            source_repo=f"{owner}/{repo_slug}",
            source_ref=observation.id,
            status="observed",
            summary=f"{len(observation.commits)} commits, {len(observation.pull_requests)} PRs, {len(observation.releases)} releases",
            data={
                "since": since_label,
                "commits": len(observation.commits),
                "pull_requests": len(observation.pull_requests),
                "releases": len(observation.releases),
                "repo_url": repo.url,
            },
        )
        rprint(f"\n[dim]Synced to cloud.[/dim]")
    except ImportError:
        pass
    except Exception as exc:
        rprint(f"\n[yellow]Cloud sync skipped: {exc}[/yellow]")


# ── analyze ──────────────────────────────────────────────────────────────────


@app.command()
def analyze(
    reference: str,
    repo: Annotated[Optional[str], typer.Option("--repo", help="Upstream repository name")] = None,
    json: JSON_OPTION = False,
) -> None:
    """Analyze a specific upstream change (pr-N, commit-SHA, release-TAG)."""
    _require_init()
    ref_type, ref_id = _parse_reference(reference)

    repos = _load_repos()
    upstreams = [r for r in repos if r.type == "upstream"]
    if repo:
        target = next((r for r in repos if r.name == repo), None)
        if not target:
            _error_exit(RepoNotFoundError(repo))
            return
    elif len(upstreams) == 1:
        target = upstreams[0]
    elif not upstreams:
        _error_exit(ValidationError('No upstream repositories. Add one with "code-adapt repo add upstream <name> <url>".'))
        return
    else:
        _error_exit(ValidationError("Multiple upstream repos. Use --repo <name>."))
        return

    # Route to correct API client based on provider
    try:
        target_provider = Provider(target.provider)
    except ValueError:
        rprint(f"[red]Unknown provider '{target.provider}' for '{target.name}'. Valid: {', '.join(p.value for p in Provider)}[/red]")
        raise typer.Exit(code=1)
    owner, repo_slug = provider_parse_repo_url(target.url)

    if target_provider in (Provider.GITLAB, Provider.GITCODE):
        token = get_token(target_provider)
        base = api_base_url(target_provider, target.url)
        gl = GitLabClient(base, token)
        with console.status(f"Fetching {ref_type} {ref_id}..."):
            if ref_type == "pr":
                diff = gl.fetch_mr_diff(owner, repo_slug, int(ref_id))
            elif ref_type == "commit":
                diff = gl.fetch_commit_diff(owner, repo_slug, ref_id)
            else:
                # GitLab releases don't have a direct diff — use empty diff with release name
                diff = {"files": [], "additions": 0, "deletions": 0, "message": f"Release {ref_id}"}
    elif target_provider == Provider.GITEE:
        token = get_token(target_provider)
        base = api_base_url(target_provider, target.url)
        ge = GiteeClient(base, token)
        with console.status(f"Fetching {ref_type} {ref_id}..."):
            if ref_type == "pr":
                diff = ge.fetch_pr_diff(owner, repo_slug, int(ref_id))
            elif ref_type == "commit":
                diff = ge.fetch_commit_diff(owner, repo_slug, ref_id)
            else:
                diff = {"files": [], "additions": 0, "deletions": 0, "message": f"Release {ref_id}"}
    else:
        token = get_github_token()
        with console.status(f"Fetching {ref_type} {ref_id}..."):
            if ref_type == "pr":
                diff = fetch_pr_diff(token, owner, repo_slug, int(ref_id))
            elif ref_type == "commit":
                diff = fetch_commit_diff(token, owner, repo_slug, ref_id)
            else:
                info = fetch_release_info(token, owner, repo_slug, ref_id)
                diff = {"files": [], "additions": 0, "deletions": 0, "message": info["message"]}

    files = diff["files"]
    additions = diff["additions"]
    deletions = diff["deletions"]
    message = diff["message"]

    classification = classify_change(message, files, additions, deletions)
    modules = extract_modules(files)
    diff_stats = DiffStats(additions=additions, deletions=deletions, files_changed=len(files))
    summary = generate_summary(message, classification, diff_stats)
    intent = extract_intent(message)

    analysis_obj = Analysis(
        id=generate_id("ana"),
        source_ref=reference,
        source_ref_type=ref_type,  # type: ignore[arg-type]
        repo_name=target.name,
        summary=summary,
        classification=classification,
        intent=intent,
        affected_files=files,
        affected_modules=modules,
        diff_stats=diff_stats,
    )

    write_json(
        get_adapt_dir() / "analyses" / f"{analysis_obj.id}.json", analysis_obj.model_dump()
    )

    if json:
        _output(analysis_obj.model_dump(), as_json=True)
    else:
        rprint(f"[green]Analysis {analysis_obj.id} saved.[/green]")
        rprint(f"  Reference:      {reference}")
        rprint(f"  Repository:     {target.name}")
        rprint(f"  Classification: {classification.value}")
        rprint(f"  Summary:        {summary}")
        rprint(f"  Intent:         {intent}")
        rprint(f"  Files changed:  {diff_stats.files_changed}")
        rprint(f"  Additions:      +{diff_stats.additions}")
        rprint(f"  Deletions:      -{diff_stats.deletions}")
        if modules:
            rprint(f"  Modules:        {', '.join(modules)}")
        if files:
            rprint("\nAffected files:")
            for f in files[:20]:
                rprint(f"  {f}")
            if len(files) > 20:
                rprint(f"  ... and {len(files) - 20} more")


# ── assess ───────────────────────────────────────────────────────────────────


@app.command()
def assess(
    reference: str,
    against: Annotated[str, typer.Option(help="Downstream project to assess against")],
    json: JSON_OPTION = False,
) -> None:
    """Assess relevance of an analyzed change."""
    _require_init()

    source_ref = reference
    if not (source_ref.startswith("pr-") or source_ref.startswith("commit-") or source_ref.startswith("release-")):
        _error_exit(ValidationError(f'Invalid reference format: "{reference}".'))
        return

    analysis = _find_analysis(source_ref)
    if not analysis:
        _error_exit(ValidationError(f'No analysis found for "{source_ref}". Run "code-adapt analyze {source_ref}" first.'))
        return

    adapt_dir = get_adapt_dir()
    profile = Profile(**read_yaml(adapt_dir / "profile.yaml"))
    policy = Policy(**read_yaml(adapt_dir / "policies.yaml"))

    repos = _load_repos()
    downstream = next((r for r in repos if r.name == against), None)
    if not downstream:
        rprint(f'[yellow]Downstream "{against}" not found. Proceeding with current profile/policy.[/yellow]')

    result = assess_relevance(analysis, profile, policy)

    ref_type: str = "pr" if source_ref.startswith("pr-") else "commit" if source_ref.startswith("commit-") else "release"

    now = datetime.now().isoformat()
    adaptation = Adaptation(
        id=generate_id("adp"),
        source_repo=analysis.repo_name,
        source_ref=source_ref,
        source_ref_type=ref_type,  # type: ignore[arg-type]
        analysis_id=analysis.id,
        status=AdaptationStatus.ASSESSED,
        relevance=result.relevance,
        risk_score=result.risk_score,
        suggested_action=result.suggested_action,
        target_modules=analysis.affected_modules,
        created_at=now,
        updated_at=now,
    )

    adp_dir = adapt_dir / "adaptations" / adaptation.id
    ensure_dir(adp_dir)
    write_yaml(adp_dir / "adaptation.yaml", adaptation.model_dump())

    if json:
        out = adaptation.model_dump()
        out["strategic_value"] = result.strategic_value
        _output(out, as_json=True)
    else:
        rprint(f"[green]Assessment {adaptation.id} saved.[/green]")
        rprint(f"  Reference:        {source_ref}")
        rprint(f"  Repository:       {analysis.repo_name}")
        rprint(f"  Against:          {against}")
        rprint(f"  Relevance:        {result.relevance.value}")
        rprint(f"  Risk:             {result.risk_score.value}")
        rprint(f"  Suggested Action: {result.suggested_action.value}")
        rprint(f"  Strategic Value:  {result.strategic_value}")
        rprint(f"  Classification:   {analysis.classification.value}")
        rprint(f"  Affected Modules: {', '.join(analysis.affected_modules) or 'none'}")


# ── plan ─────────────────────────────────────────────────────────────────────


def _auto_select_strategy(analysis: Analysis) -> Strategy:
    if analysis.classification == Classification.SECURITY:
        return Strategy.DIRECT_ADOPTION
    if analysis.diff_stats.additions > 200:
        return Strategy.PARTIAL_REIMPLEMENTATION
    if analysis.classification == Classification.REFACTOR:
        return Strategy.IMPROVED_IMPLEMENTATION
    return Strategy.DIRECT_ADOPTION


@app.command()
def plan(
    adaptation_id: str,
    strategy: Annotated[Optional[str], typer.Option(help="Override strategy")] = None,
    json: JSON_OPTION = False,
) -> None:
    """Generate an adaptation plan."""
    _require_init()

    adapt_dir = get_adapt_dir()
    adp_dir = adapt_dir / "adaptations" / adaptation_id
    adp_path = adp_dir / "adaptation.yaml"

    if not adp_path.exists():
        _error_exit(AdaptationNotFoundError(adaptation_id))
        return

    adaptation = Adaptation(**read_yaml(adp_path))

    from ..models import can_transition
    if not can_transition(adaptation.status, AdaptationStatus.PLANNED):
        _error_exit(ValidationError(
            f'Adaptation "{adaptation_id}" is in status "{adaptation.status.value}" and cannot be planned.'
        ))
        return

    if not adaptation.analysis_id:
        _error_exit(ValidationError(f'Adaptation "{adaptation_id}" has no associated analysis.'))
        return

    analysis_path = adapt_dir / "analyses" / f"{adaptation.analysis_id}.json"
    if not analysis_path.exists():
        _error_exit(ValidationError(f'Analysis "{adaptation.analysis_id}" not found.'))
        return

    analysis = Analysis(**read_json(analysis_path))

    valid_strategies = [s.value for s in Strategy]
    if strategy:
        if strategy not in valid_strategies:
            _error_exit(ValidationError(f'Invalid strategy: "{strategy}". Valid: {", ".join(valid_strategies)}.'))
            return
        chosen_strategy = Strategy(strategy)
    else:
        chosen_strategy = _auto_select_strategy(analysis)

    # Generate steps
    steps: list[PlanStep] = []
    order = 1
    for f in analysis.affected_files:
        steps.append(PlanStep(order=order, description=f"Apply upstream changes to {f}", target_file=f, type="modify"))
        order += 1
    for mod in analysis.affected_modules:
        steps.append(PlanStep(order=order, description=f"Add/update tests for module {mod}", target_file=f"tests/{mod}.test.py", type="test"))
        order += 1

    # Contribution split
    policy_path = adapt_dir / "policies.yaml"
    policy = Policy(**read_yaml(policy_path)) if policy_path.exists() else Policy()

    contrib_split = None
    if policy.contribution_rules.enabled:
        upstream_files = []
        internal_files = []
        for f in analysis.affected_files:
            excluded = any(
                re.match(
                    "^" + p.replace(".", r"\.").replace("**", ".*").replace("*", "[^/]*") + "$", f
                )
                for p in policy.contribution_rules.exclude_patterns
            )
            if excluded:
                internal_files.append(f)
            else:
                upstream_files.append(f)
        contrib_split = ContributionSplit(upstream=upstream_files, internal=internal_files)

    plan_id = f"plan_{adaptation_id}"
    plan_obj = Plan(
        id=plan_id,
        adaptation_id=adaptation_id,
        strategy=chosen_strategy.value,
        target_modules=analysis.affected_modules,
        steps=steps,
        dependencies=list(analysis.affected_modules),
        suggested_tests=[f"Verify {mod} module after adaptation" for mod in analysis.affected_modules],
        contribution_split=contrib_split,
    )

    write_yaml(adp_dir / "plan.yaml", plan_obj.model_dump())

    updated = adaptation.transition(AdaptationStatus.PLANNED)
    updated = updated.model_copy(update={"strategy": chosen_strategy, "plan_id": plan_id})
    write_yaml(adp_path, updated.model_dump())

    if json:
        _output(plan_obj.model_dump(), as_json=True)
    else:
        rprint(f"[green]Plan {plan_id} created.[/green]")
        rprint(f"  Adaptation: {adaptation_id}")
        rprint(f"  Strategy:   {chosen_strategy.value}")
        rprint(f"  Steps:      {len(steps)}")
        rprint(f"  Modules:    {', '.join(plan_obj.target_modules) or 'none'}")
        if plan_obj.dependencies:
            rprint(f"  Dependencies: {', '.join(plan_obj.dependencies)}")
        if plan_obj.suggested_tests:
            rprint("\nSuggested tests:")
            for t in plan_obj.suggested_tests:
                rprint(f"  - {t}")
        if steps:
            rprint()
            _output_table(
                ["#", "Type", "Target File", "Description"],
                [[str(s.order), s.type, s.target_file, s.description] for s in steps],
            )


# ── implement ────────────────────────────────────────────────────────────────


@app.command()
def implement(
    adaptation_id: str,
    branch: Annotated[bool, typer.Option("--branch", help="Create a git branch")] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Show changes without applying")] = False,
    open_pr: Annotated[bool, typer.Option("--open-pr", help="Create draft PR")] = False,
    json: JSON_OPTION = False,
) -> None:
    """Implement the adaptation."""
    _require_init()

    adapt_dir = get_adapt_dir()
    adp_dir = adapt_dir / "adaptations" / adaptation_id
    adp_path = adp_dir / "adaptation.yaml"

    if not adp_path.exists():
        _error_exit(AdaptationNotFoundError(adaptation_id))
        return

    adaptation = Adaptation(**read_yaml(adp_path))
    plan_path = adp_dir / "plan.yaml"
    if not plan_path.exists():
        _error_exit(ValidationError(f'No plan found for "{adaptation_id}". Run "code-adapt plan" first.'))
        return

    plan_obj = Plan(**read_yaml(plan_path))

    def execute_step(step: PlanStep, is_dry: bool) -> str:
        resolved = Path.cwd() / step.target_file
        if is_dry:
            if step.type in ("create", "test"):
                return f"Would create: {step.target_file}"
            elif step.type == "modify":
                return f"Would modify: {step.target_file}" if resolved.exists() else f"Would create (missing): {step.target_file}"
            return f"Would mark for deletion: {step.target_file}"

        if step.type == "create" or step.type == "test":
            resolved.parent.mkdir(parents=True, exist_ok=True)
            comment = f"# TODO: Implement adaptation {adaptation_id}\n"
            resolved.write_text(comment, encoding="utf-8")
            return f"Created stub: {step.target_file}"
        elif step.type == "modify":
            if resolved.exists():
                existing = resolved.read_text(encoding="utf-8")
                resolved.write_text(f"# TODO: Apply adaptation {adaptation_id}\n{existing}", encoding="utf-8")
                return f"Added TODO to: {step.target_file}"
            else:
                resolved.parent.mkdir(parents=True, exist_ok=True)
                resolved.write_text(f"# TODO: Implement adaptation {adaptation_id}\n", encoding="utf-8")
                return f"Created stub (missing): {step.target_file}"
        return f"Marked for deletion: {step.target_file}"

    if dry_run:
        results = [execute_step(s, True) for s in plan_obj.steps]
        if json:
            _output({"adaptation_id": adaptation_id, "dry_run": True, "steps": results}, as_json=True)
        else:
            rprint("[yellow]Dry run — no changes will be made.[/yellow]")
            _output_table(
                ["#", "Type", "Target", "Action"],
                [[str(s.order), s.type, s.target_file, results[i]] for i, s in enumerate(plan_obj.steps)],
            )
        return

    # Create branch
    branch_name = None
    if branch:
        branch_name = f"adapt/{adaptation_id}"
        try:
            subprocess.run(["git", "checkout", "-b", branch_name], capture_output=True, check=True)
        except subprocess.CalledProcessError as e:
            _error_exit(ValidationError(f'Failed to create branch "{branch_name}": {e.stderr}'))
            return

    results = [execute_step(s, False) for s in plan_obj.steps]

    updated = adaptation.transition(AdaptationStatus.IMPLEMENTED)
    updated = updated.model_copy(update={"branch": branch_name or adaptation.branch})
    write_yaml(adp_path, updated.model_dump())

    pr_url = None
    if open_pr:
        try:
            result = subprocess.run(
                ["gh", "pr", "create", "--draft", "--title", f"adapt: {adaptation_id}", "--body", f"Adaptation {adaptation_id}"],
                capture_output=True, text=True, check=True,
            )
            pr_url = result.stdout.strip()
        except (FileNotFoundError, subprocess.CalledProcessError) as e:
            rprint(f"[yellow]Failed to create PR: {e}[/yellow]")

    if json:
        _output({"adaptation_id": adaptation_id, "status": "implemented", "branch": branch_name, "steps": results, "pr_url": pr_url}, as_json=True)
    else:
        rprint(f"[green]Adaptation {adaptation_id} implemented.[/green]")
        rprint(f"  Steps: {len(results)} executed")
        if branch_name:
            rprint(f"  Branch: {branch_name}")
        if pr_url:
            rprint(f"  PR: {pr_url}")
        rprint()
        _output_table(
            ["#", "Type", "Target", "Result"],
            [[str(s.order), s.type, s.target_file, results[i]] for i, s in enumerate(plan_obj.steps)],
        )


# ── validate ─────────────────────────────────────────────────────────────────


@app.command()
def validate(
    adaptation_id: str,
    branch: Annotated[Optional[str], typer.Option(help="Branch to validate")] = None,
    json: JSON_OPTION = False,
) -> None:
    """Validate an implemented adaptation."""
    _require_init()

    adapt_dir = get_adapt_dir()
    adp_dir = adapt_dir / "adaptations" / adaptation_id
    adp_path = adp_dir / "adaptation.yaml"

    if not adp_path.exists():
        _error_exit(AdaptationNotFoundError(adaptation_id))
        return

    adaptation = Adaptation(**read_yaml(adp_path))
    plan_path = adp_dir / "plan.yaml"
    if not plan_path.exists():
        _error_exit(ValidationError(f'No plan for "{adaptation_id}".'))
        return

    plan_obj = Plan(**read_yaml(plan_path))
    policy_path = adapt_dir / "policies.yaml"
    policy = Policy(**read_yaml(policy_path)) if policy_path.exists() else Policy()

    config_path = adapt_dir / "config.yaml"
    config = read_yaml(config_path) if config_path.exists() else {}

    checks: list[dict] = []

    # Policy compliance
    policy_issues = []
    for step in plan_obj.steps:
        for pp in policy.protected_paths:
            if step.target_file.startswith(pp):
                policy_issues.append(f'Step {step.order}: "{step.target_file}" targets protected path "{pp}"')
    checks.append({"name": "Policy compliance", "passed": len(policy_issues) == 0, "issues": policy_issues})

    # Architecture conformance
    arch_issues = []
    step_files = [s.target_file for s in plan_obj.steps]
    for mod in plan_obj.target_modules:
        if not any(mod in f for f in step_files):
            arch_issues.append(f'Module "{mod}" has no matching plan step')
    checks.append({"name": "Architecture conformance", "passed": len(arch_issues) == 0, "issues": arch_issues})

    # Lint
    lint_cmd = config.get("lintCommand") if config else None
    if lint_cmd:
        try:
            subprocess.run(lint_cmd, shell=True, capture_output=True, check=True)
            checks.append({"name": "Lint check", "passed": True, "issues": []})
        except subprocess.CalledProcessError as e:
            checks.append({"name": "Lint check", "passed": False, "issues": [f"Lint failed: {e}"]})
    else:
        checks.append({"name": "Lint check", "passed": True, "issues": ["Skipped: no lintCommand configured"]})

    # Tests
    test_cmd = config.get("testCommand") if config else None
    if test_cmd:
        try:
            subprocess.run(test_cmd, shell=True, capture_output=True, check=True)
            checks.append({"name": "Test check", "passed": True, "issues": []})
        except subprocess.CalledProcessError as e:
            checks.append({"name": "Test check", "passed": False, "issues": [f"Tests failed: {e}"]})
    else:
        checks.append({"name": "Test check", "passed": True, "issues": ["Skipped: no testCommand configured"]})

    all_passed = all(c["passed"] for c in checks)

    if all_passed:
        updated = adaptation.transition(AdaptationStatus.VALIDATED)
        write_yaml(adp_path, updated.model_dump())

    if json:
        _output({"adaptation_id": adaptation_id, "overall": "pass" if all_passed else "fail", "checks": checks}, as_json=True)
    else:
        if all_passed:
            rprint(f"[green]Validation passed for {adaptation_id}.[/green]")
        else:
            rprint(f"[yellow]Validation failed for {adaptation_id}.[/yellow]")
        _output_table(
            ["Check", "Status", "Issues"],
            [[c["name"], "PASS" if c["passed"] else "FAIL", "; ".join(c["issues"]) or "-"] for c in checks],
        )
        if all_passed:
            rprint('\nAdaptation status updated to "validated".')


# ── contribute ───────────────────────────────────────────────────────────────


@app.command()
def contribute(
    adaptation_id: str,
    split: Annotated[bool, typer.Option("--split", help="Split into multiple PRs")] = False,
    draft_pr: Annotated[bool, typer.Option("--draft-pr", help="Create draft PR upstream")] = False,
    json: JSON_OPTION = False,
) -> None:
    """Prepare upstream contribution."""
    _require_init()

    adapt_dir = get_adapt_dir()
    adp_dir = adapt_dir / "adaptations" / adaptation_id
    adp_path = adp_dir / "adaptation.yaml"

    if not adp_path.exists():
        _error_exit(AdaptationNotFoundError(adaptation_id))
        return

    adaptation = Adaptation(**read_yaml(adp_path))
    plan_path = adp_dir / "plan.yaml"
    if not plan_path.exists():
        _error_exit(ValidationError(f'No plan for "{adaptation_id}".'))
        return

    plan_obj = Plan(**read_yaml(plan_path))

    if plan_obj.contribution_split:
        upstream_files = list(plan_obj.contribution_split.upstream)
    else:
        upstream_files = [s.target_file for s in plan_obj.steps]

    policy_path = adapt_dir / "policies.yaml"
    policy = Policy(**read_yaml(policy_path)) if policy_path.exists() else Policy()
    exclude = policy.contribution_rules.exclude_patterns

    if exclude:
        upstream_files = [
            f for f in upstream_files
            if not any(
                re.match("^" + p.replace(".", r"\.").replace("**", ".*").replace("*", "[^/]*") + "$", f)
                for p in exclude
            )
        ]

    if not upstream_files:
        rprint("[yellow]Nothing to contribute upstream.[/yellow]")
        if json:
            _output({"adaptation_id": adaptation_id, "upstream_files": []}, as_json=True)
        return

    pr_url = None
    if draft_pr:
        repos = _load_repos()
        upstream_repo = next(
            (r for r in repos if r.type == "upstream" and r.name == adaptation.source_repo), None
        )
        if upstream_repo:
            try:
                result = subprocess.run(
                    ["gh", "pr", "create", "--draft", "--repo", upstream_repo.url,
                     "--title", f"adapt: {adaptation_id} contribution",
                     "--body", f"Adaptation {adaptation_id} — {len(upstream_files)} file(s)."],
                    capture_output=True, text=True, check=True,
                )
                pr_url = result.stdout.strip()
            except (FileNotFoundError, subprocess.CalledProcessError) as e:
                rprint(f"[yellow]Failed to create upstream PR: {e}[/yellow]")
        else:
            rprint(f'[yellow]Could not find upstream repo for "{adaptation.source_repo}".[/yellow]')

    updated = adaptation.transition(AdaptationStatus.CONTRIBUTED)
    write_yaml(adp_path, updated.model_dump())

    if json:
        _output({"adaptation_id": adaptation_id, "status": "contributed", "upstream_files": upstream_files, "pr_url": pr_url}, as_json=True)
    else:
        rprint(f"[green]Contribution prepared for {adaptation_id}.[/green]")
        rprint(f"  Upstream files: {len(upstream_files)}")
        if pr_url:
            rprint(f"  PR: {pr_url}")
        rprint()
        if split:
            groups: dict[str, list[str]] = {}
            for f in upstream_files:
                parts = f.split("/")
                mod = parts[0] if len(parts) > 1 else "(root)"
                groups.setdefault(mod, []).append(f)
            for mod, files in groups.items():
                rprint(f"\n  Module: {mod} ({len(files)} file(s))")
                _output_table(["File"], [[f] for f in files])
        else:
            _output_table(["Upstream Files"], [[f] for f in upstream_files])


# ── status ───────────────────────────────────────────────────────────────────


@app.command()
def status(json: JSON_OPTION = False) -> None:
    """Show adaptation dashboard."""
    _require_init()

    repos = _load_repos()
    adaptations = _load_all_adaptations()
    observations = _load_all_observations()

    repo_data = []
    for r in repos:
        latest = None
        for obs in observations:
            if obs.repo_name == r.name:
                if not latest or obs.timestamp > latest.timestamp:
                    latest = obs
        changes = (len(latest.commits) + len(latest.pull_requests) + len(latest.releases)) if latest else 0
        repo_data.append({
            "name": r.name, "type": r.type,
            "last_observed": latest.timestamp if latest else None,
            "changes_found": changes,
        })

    by_status: dict[str, int] = {}
    for a in adaptations:
        by_status[a.status.value] = by_status.get(a.status.value, 0) + 1

    high_priority = [a for a in adaptations if a.relevance == RelevanceScore.HIGH and a.status in (AdaptationStatus.ASSESSED, AdaptationStatus.ANALYZED)]
    backlog = [a for a in adaptations if a.status == AdaptationStatus.VALIDATED]

    if json:
        _output({
            "repositories": repo_data,
            "adaptations": {"by_status": by_status, "total": len(adaptations)},
            "high_priority": [{"id": a.id, "source_ref": a.source_ref} for a in high_priority],
            "contribution_backlog": len(backlog),
        }, as_json=True)
        return

    rprint("\n[bold]Tracked Repositories[/bold]")
    if not repo_data:
        rprint('  [yellow]No repositories tracked.[/yellow]')
    else:
        _output_table(
            ["Name", "Type", "Last Observed", "Changes"],
            [[r["name"], r["type"], r["last_observed"] or "[dim]never[/dim]", str(r["changes_found"])] for r in repo_data],
        )

    rprint("\n[bold]Adaptations by Status[/bold]")
    if not adaptations:
        rprint("  [yellow]No adaptations found.[/yellow]")
    else:
        status_rows = [[s, str(c)] for s, c in by_status.items() if c > 0]
        if status_rows:
            _output_table(["Status", "Count"], status_rows)
        rprint(f"  Total: {len(adaptations)}")

    rprint("\n[bold]High Priority[/bold]")
    if not high_priority:
        rprint("  None")
    else:
        for a in high_priority:
            rprint(f"  [red]![/red] {a.id} — {a.source_ref} ({a.source_repo})")

    rprint("\n[bold]Contribution Backlog[/bold]")
    if not backlog:
        rprint("  No validated adaptations ready for contribution.")
    else:
        rprint(f"  {len(backlog)} adaptation(s) ready.")
        for a in backlog:
            rprint(f"    {a.id} — {a.source_ref}")
    rprint()


# ── sync ─────────────────────────────────────────────────────────────────────


@app.command()
def sync(
    repo_name: Annotated[Optional[str], typer.Argument(help="Repository name")] = None,
    cloud: bool = typer.Option(False, "--cloud", "-c", help="Push adaptations to the Pioneers cloud"),
    json: JSON_OPTION = False,
) -> None:
    """Show synchronization status. Use --cloud to push to the Pioneers platform."""
    _require_init()

    all_repos = _load_repos()
    if repo_name:
        repos = [r for r in all_repos if r.name == repo_name]
        if not repos:
            _error_exit(RepoNotFoundError(repo_name))
            return
    else:
        repos = [r for r in all_repos if r.type == "upstream"]

    if not repos:
        rprint('[yellow]No upstream repositories to sync.[/yellow]')
        return

    adaptations = _load_all_adaptations()
    observations = _load_all_observations()

    # Cloud sync: push adaptations to the Pioneers API
    if cloud:
        try:
            from pioneers_cli.cloud import require_cloud, sync_adaptation, CloudError
        except ImportError:
            rprint("[red]pioneers-cli is not installed.[/red]")
            rprint("Install it: [bold]pip install pioneers-cli[/bold]")
            raise typer.Exit(1)

        try:
            api_url, token = require_cloud()
        except CloudError as e:
            rprint(f"[red]{e}[/red]")
            raise typer.Exit(1)

        if not adaptations:
            rprint("[yellow]No adaptations to sync.[/yellow]")
            raise typer.Exit(0)

        rprint(f"\n[bold]Syncing {len(adaptations)} adaptation(s) to {api_url}...[/bold]\n")
        synced = 0
        errors = 0

        for adp in adaptations:
            try:
                sync_adaptation(
                    api_url, token,
                    source_repo=adp.source_repo,
                    source_ref=adp.source_ref,
                    status=adp.status.value,
                    classification=adp.relevance.value if adp.relevance else None,
                    relevance=adp.relevance.value if adp.relevance else None,
                    risk=adp.risk_score.value if adp.risk_score else None,
                    summary=None,
                    data={
                        "id": adp.id,
                        "source_ref_type": adp.source_ref_type,
                        "suggested_action": adp.suggested_action.value if adp.suggested_action else None,
                        "strategy": adp.strategy.value if adp.strategy else None,
                    },
                )
                synced += 1
                rprint(f"  [green]✓[/green] {adp.source_repo} ({adp.source_ref[:12]})")
            except CloudError as e:
                errors += 1
                rprint(f"  [red]✗[/red] {adp.source_repo}: {e}")
            except Exception as e:
                errors += 1
                rprint(f"  [red]✗[/red] {adp.source_repo}: {e}")

        rprint()
        if errors == 0:
            rprint(f"[green]Synced {synced} adaptation(s) to the cloud.[/green]")
        else:
            rprint(f"[yellow]Synced {synced}, failed {errors} adaptation(s).[/yellow]")
        return

    # Local sync status (default behavior)
    sync_data = []
    for r in repos:
        last_ts = None
        for obs in observations:
            if obs.repo_name == r.name:
                if not last_ts or obs.timestamp > last_ts:
                    last_ts = obs.timestamp
        days = None
        if last_ts:
            delta = datetime.now() - datetime.fromisoformat(last_ts)
            days = delta.days

        repo_adps = [a for a in adaptations if a.source_repo == r.name]
        open_count = sum(1 for a in repo_adps if a.status not in (AdaptationStatus.MERGED, AdaptationStatus.REJECTED))
        pending = sum(1 for a in repo_adps if a.status == AdaptationStatus.IMPLEMENTED)
        candidates = sum(1 for a in repo_adps if a.status == AdaptationStatus.VALIDATED)

        sync_data.append({
            "name": r.name, "last_observed": last_ts, "stale_days": days,
            "open_adaptations": open_count, "pending_validations": pending,
            "contribution_candidates": candidates,
        })

    if json:
        _output({"repos": sync_data}, as_json=True)
        return

    rprint("\n[bold]Sync Status[/bold]")

    def fmt_stale(d: int | None) -> str:
        if d is None:
            return "[dim]n/a[/dim]"
        if d < 3:
            return f"[green]{d}d ago[/green]"
        if d < 7:
            return f"[yellow]{d}d ago[/yellow]"
        return f"[red]{d}d ago[/red]"

    _output_table(
        ["Repository", "Last Observed", "Staleness", "Open", "Pending", "Candidates"],
        [[s["name"], s["last_observed"] or "[dim]never[/dim]", fmt_stale(s["stale_days"]),
          str(s["open_adaptations"]), str(s["pending_validations"]), str(s["contribution_candidates"])]
         for s in sync_data],
    )
    rprint()


# ── report ───────────────────────────────────────────────────────────────────

report_app = typer.Typer(help="Generate adaptation reports")
app.add_typer(report_app, name="report")


def _build_report_data(period: str, cutoff: datetime, filter_repo: str | None = None) -> dict:
    all_obs = _load_all_observations()
    all_adp = _load_all_adaptations()

    obs = [o for o in all_obs if datetime.fromisoformat(o.timestamp) >= cutoff]
    adps = [a for a in all_adp if datetime.fromisoformat(a.created_at) >= cutoff]
    if filter_repo:
        obs = [o for o in obs if o.repo_name == filter_repo]
        adps = [a for a in adps if a.source_repo == filter_repo]

    by_status: dict[str, int] = {}
    for a in adps:
        by_status[a.status.value] = by_status.get(a.status.value, 0) + 1

    completed = sum(1 for a in adps if a.status in (AdaptationStatus.MERGED, AdaptationStatus.CONTRIBUTED))
    rejected = sum(1 for a in adps if a.status == AdaptationStatus.REJECTED)
    in_progress = len(adps) - completed - rejected

    return {
        "period": period,
        "generated_at": datetime.now().isoformat(),
        "observations": {
            "total": len(obs),
            "repos": list({o.repo_name for o in obs}),
            "total_commits": sum(len(o.commits) for o in obs),
            "total_prs": sum(len(o.pull_requests) for o in obs),
            "total_releases": sum(len(o.releases) for o in obs),
        },
        "adaptations": {
            "total": len(adps), "completed": completed, "rejected": rejected,
            "in_progress": in_progress, "by_status": by_status,
        },
    }


def _display_report(data: dict) -> None:
    rprint(f"Adapt Report — {data['period']}")
    rprint("=" * 40)
    o = data["observations"]
    rprint(f"\nObservations: {o['total']} | Commits: {o['total_commits']} | PRs: {o['total_prs']} | Releases: {o['total_releases']}")
    a = data["adaptations"]
    rprint(f"Adaptations: {a['total']} | Completed: {a['completed']} | Rejected: {a['rejected']} | In Progress: {a['in_progress']}")


def _save_report(filename: str, data: dict) -> None:
    reports_dir = get_adapt_dir() / "reports"
    ensure_dir(reports_dir)
    lines = [f"# Adapt Report — {data['period']}", "", f"Generated: {data['generated_at']}", ""]
    o = data["observations"]
    lines += ["## Observations", f"- Total: {o['total']}", f"- Commits: {o['total_commits']}", f"- PRs: {o['total_prs']}", f"- Releases: {o['total_releases']}", ""]
    a = data["adaptations"]
    lines += ["## Adaptations", f"- Total: {a['total']}", f"- Completed: {a['completed']}", f"- Rejected: {a['rejected']}", f"- In Progress: {a['in_progress']}", ""]
    (reports_dir / filename).write_text("\n".join(lines), encoding="utf-8")


@report_app.command("weekly")
def report_weekly(json: JSON_OPTION = False) -> None:
    """Weekly activity report."""
    _require_init()
    from datetime import timedelta
    cutoff = datetime.now() - timedelta(days=7)
    week = datetime.now().isocalendar()[1]
    year = datetime.now().year
    period = f"Weekly — {year}-W{week:02d}"
    data = _build_report_data(period, cutoff)
    filename = f"weekly_{year}_{week:02d}.md"
    _save_report(filename, data)
    if json:
        _output(data, as_json=True)
    else:
        _display_report(data)
        rprint(f"\n[green]Report saved to .adapt/reports/{filename}[/green]")


@report_app.command("release")
def report_release(json: JSON_OPTION = False) -> None:
    """Activity since last release."""
    _require_init()
    from datetime import timedelta
    all_obs = _load_all_observations()
    release_obs = sorted(
        [o for o in all_obs if o.releases],
        key=lambda o: o.timestamp, reverse=True,
    )
    if release_obs:
        cutoff = datetime.fromisoformat(release_obs[0].timestamp)
        tag = release_obs[0].releases[0].tag
    else:
        cutoff = datetime.now() - timedelta(days=30)
        tag = "none"
    period = f"Since Release {tag}"
    data = _build_report_data(period, cutoff)
    safe_tag = re.sub(r"[^a-zA-Z0-9._-]", "_", tag)
    filename = f"release_{safe_tag}.md"
    _save_report(filename, data)
    if json:
        _output(data, as_json=True)
    else:
        _display_report(data)
        rprint(f"\n[green]Report saved to .adapt/reports/{filename}[/green]")


@report_app.command("upstream")
def report_upstream(
    repo_name: str,
    since: Annotated[str, typer.Option(help="Time window e.g. 7d, 2w, 1m")],
    json: JSON_OPTION = False,
) -> None:
    """Upstream-specific report."""
    _require_init()
    cutoff = parse_duration(since)
    period = f"Upstream: {repo_name} (since {since})"
    data = _build_report_data(period, cutoff, repo_name)
    safe_repo = re.sub(r"[^a-zA-Z0-9._-]", "_", repo_name)
    filename = f"upstream_{safe_repo}_{since}.md"
    _save_report(filename, data)
    if json:
        _output(data, as_json=True)
    else:
        _display_report(data)
        rprint(f"\n[green]Report saved to .adapt/reports/{filename}[/green]")


# ── learn ────────────────────────────────────────────────────────────────────

learn_app = typer.Typer(help="Record and review adaptation outcomes")
app.add_typer(learn_app, name="learn")


def _load_learnings() -> list[LearningRecord]:
    path = get_adapt_dir() / "reports" / "learnings.yaml"
    if not path.exists():
        return []
    data = read_yaml(path)
    return [LearningRecord(**r) for r in data] if data else []


def _save_learnings(records: list[LearningRecord]) -> None:
    path = get_adapt_dir() / "reports" / "learnings.yaml"
    ensure_dir(path.parent)
    write_yaml(path, [r.model_dump() for r in records])


@learn_app.command("record")
def learn_record(
    adaptation_id: str,
    accepted: Annotated[bool, typer.Option("--accepted")] = False,
    rejected: Annotated[bool, typer.Option("--rejected")] = False,
    reason: Annotated[Optional[str], typer.Option(help="Reason for outcome")] = None,
    json: JSON_OPTION = False,
) -> None:
    """Record adaptation outcome."""
    _require_init()

    if not accepted and not rejected:
        _error_exit(ValidationError("You must specify --accepted or --rejected."))
        return
    if accepted and rejected:
        _error_exit(ValidationError("Cannot specify both --accepted and --rejected."))
        return

    adp_path = get_adapt_dir() / "adaptations" / adaptation_id / "adaptation.yaml"
    if not adp_path.exists():
        _error_exit(AdaptationNotFoundError(adaptation_id))
        return

    adaptation = Adaptation(**read_yaml(adp_path))
    outcome = "accepted" if accepted else "rejected"
    record = LearningRecord(adaptation_id=adaptation_id, outcome=outcome, reason=reason)  # type: ignore[arg-type]

    learnings = _load_learnings()
    learnings.append(record)
    _save_learnings(learnings)

    target_status = AdaptationStatus.MERGED if outcome == "accepted" else AdaptationStatus.REJECTED
    updated = adaptation.transition(target_status)
    write_yaml(adp_path, updated.model_dump())

    if json:
        _output({"record": record.model_dump(), "adaptation": updated.model_dump()}, as_json=True)
    else:
        suffix = f" (reason: {record.reason})" if record.reason else ""
        rprint(f"[green]Learning recorded: {adaptation_id} → {outcome}{suffix}[/green]")
        rprint(f"  Status updated: {adaptation.status.value} → {updated.status.value}")


@learn_app.command("stats")
def learn_stats(json: JSON_OPTION = False) -> None:
    """Show learning statistics."""
    _require_init()

    learnings = _load_learnings()
    if not learnings:
        if json:
            _output({"total": 0, "accepted": 0, "rejected": 0, "acceptance_rate": 0}, as_json=True)
        else:
            rprint("No learning records found.")
        return

    total = len(learnings)
    acc = sum(1 for l in learnings if l.outcome == "accepted")
    rej = total - acc
    rate = (acc / total) * 100 if total else 0

    reason_counts: dict[str, int] = {}
    for l in learnings:
        if l.outcome == "rejected" and l.reason:
            reason_counts[l.reason] = reason_counts.get(l.reason, 0) + 1
    reasons_sorted = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)

    if json:
        _output({"total": total, "accepted": acc, "rejected": rej, "acceptance_rate": round(rate, 1), "rejection_reasons": reasons_sorted}, as_json=True)
    else:
        rprint("Learning Statistics")
        rprint("==================")
        _output_table(
            ["Metric", "Value"],
            [["Total", str(total)], ["Accepted", str(acc)], ["Rejected", str(rej)], ["Acceptance rate", f"{rate:.1f}%"]],
        )
        if reasons_sorted:
            rprint("\nTop Rejection Reasons")
            _output_table(["Reason", "Count"], [[r, str(c)] for r, c in reasons_sorted])


# ── policy ───────────────────────────────────────────────────────────────────

policy_app = typer.Typer(help="Manage adaptation policies")
app.add_typer(policy_app, name="policy")


@policy_app.command("init")
def policy_init(json: JSON_OPTION = False) -> None:
    """Initialize default policies."""
    _require_init()
    path = get_adapt_dir() / "policies.yaml"
    if path.exists():
        rprint("[yellow]Policy already initialized.[/yellow]")
        return
    write_yaml(path, Policy().model_dump())
    if json:
        _output({"initialized": True, "path": str(path)}, as_json=True)
    else:
        rprint(f"[green]Policy initialized at {path}[/green]")


@policy_app.command("list")
def policy_list(json: JSON_OPTION = False) -> None:
    """List current policy settings."""
    _require_init()
    path = get_adapt_dir() / "policies.yaml"
    if not path.exists():
        rprint('[yellow]No policies found. Run "code-adapt policy init" first.[/yellow]')
        return
    policy = Policy(**read_yaml(path))
    if json:
        _output(policy.model_dump(), as_json=True)
    else:
        rprint("\n[bold]Policy Settings[/bold]")
        _output_table(
            ["Setting", "Value"],
            [
                ["Relevant Modules", ", ".join(policy.relevant_modules) or "(none)"],
                ["Ignored Modules", ", ".join(policy.ignored_modules) or "(none)"],
                ["Critical Licenses", ", ".join(policy.critical_licenses) or "(none)"],
                ["Protected Paths", ", ".join(policy.protected_paths) or "(none)"],
                ["Contribution Enabled", str(policy.contribution_rules.enabled)],
                ["Require Review", str(policy.contribution_rules.require_review)],
                ["Auto-Assess Threshold", policy.auto_assess_threshold or "(none)"],
            ],
        )


@policy_app.command("edit")
def policy_edit(json: JSON_OPTION = False) -> None:
    """Edit policies file."""
    path = get_adapt_dir() / "policies.yaml"
    if json:
        _output({"path": str(path), "message": "Edit this file directly"}, as_json=True)
    else:
        rprint(f"Edit your policy file directly at:\n  [cyan]{path}[/cyan]")


@policy_app.command("validate")
def policy_validate(json: JSON_OPTION = False) -> None:
    """Validate policy configuration."""
    _require_init()
    path = get_adapt_dir() / "policies.yaml"
    if not path.exists():
        _error_exit(ValidationError('No policies file. Run "code-adapt policy init" first.'))
        return

    data = read_yaml(path)
    results: list[dict] = []

    def check_list(name: str, val: object) -> dict:
        if val is None:
            return {"section": name, "pass": True, "message": "Not set"}
        if not isinstance(val, list):
            return {"section": name, "pass": False, "message": f"Expected list, got {type(val).__name__}"}
        if not all(isinstance(v, str) for v in val):
            return {"section": name, "pass": False, "message": "Not all items are strings"}
        return {"section": name, "pass": True, "message": f"{len(val)} item(s)"}

    for field in ("relevant_modules", "ignored_modules", "critical_licenses", "protected_paths"):
        # Handle both snake_case and camelCase from YAML
        val = data.get(field) if data else None
        results.append(check_list(field, val))

    all_ok = all(r["pass"] for r in results)

    if json:
        _output({"valid": all_ok, "results": results}, as_json=True)
    else:
        rprint("\n[bold]Policy Validation[/bold]")
        _output_table(
            ["Section", "Status", "Details"],
            [[r["section"], "[green]PASS[/green]" if r["pass"] else "[red]FAIL[/red]", r["message"]] for r in results],
        )
        if all_ok:
            rprint("\n[green]All policy sections are valid.[/green]")
        else:
            rprint("\n[red]Some policy sections have issues.[/red]")


# ── profile ──────────────────────────────────────────────────────────────────

profile_app = typer.Typer(help="Manage project profiles")
app.add_typer(profile_app, name="profile")


@profile_app.command("create")
def profile_create(name: str, json: JSON_OPTION = False) -> None:
    """Create a new project profile."""
    _require_init()
    path = get_adapt_dir() / "profile.yaml"
    profile = Profile(name=name)
    write_yaml(path, profile.model_dump())
    if json:
        _output({"created": True, "path": str(path), "profile": profile.model_dump()}, as_json=True)
    else:
        rprint(f'[green]Profile "{name}" created at {path}[/green]')


@profile_app.command("inspect")
def profile_inspect(json: JSON_OPTION = False) -> None:
    """Inspect current profile."""
    _require_init()
    path = get_adapt_dir() / "profile.yaml"
    if not path.exists():
        rprint('[yellow]No profile found. Run "code-adapt profile create <name>" first.[/yellow]')
        return
    profile = Profile(**read_yaml(path))
    if json:
        _output(profile.model_dump(), as_json=True)
    else:
        rprint("\n[bold]Project Profile[/bold]")
        _output_table(
            ["Field", "Value"],
            [
                ["Name", profile.name],
                ["Stack", ", ".join(profile.stack) or "(none)"],
                ["Architecture", profile.architecture or "(not set)"],
                ["Conventions", ", ".join(profile.conventions) or "(none)"],
                ["Critical Modules", ", ".join(profile.critical_modules) or "(none)"],
                ["Priorities", ", ".join(profile.priorities) or "(none)"],
            ],
        )


@profile_app.command("import")
def profile_import(file: str, json: JSON_OPTION = False) -> None:
    """Import profile from YAML file."""
    _require_init()
    source = Path(file).resolve()
    if not source.exists():
        _error_exit(ValidationError(f"File not found: {source}"))
        return
    imported = read_yaml(source)
    if not isinstance(imported, dict) or "name" not in imported:
        _error_exit(ValidationError('Invalid profile: missing required "name" field.'))
        return
    path = get_adapt_dir() / "profile.yaml"
    write_yaml(path, imported)
    if json:
        _output({"imported": True, "source": str(source), "path": str(path)}, as_json=True)
    else:
        rprint(f"[green]Profile imported from {source} to {path}[/green]")


# ── Error handler wrapper ────────────────────────────────────────────────────


def _main() -> None:
    try:
        app()
    except AdaptError as e:
        rprint(f"[red]Error:[/red] {e}")
        sys.exit(e.code)


if __name__ == "__main__":
    _main()
