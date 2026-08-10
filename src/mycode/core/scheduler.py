"""Scheduler module for MyCode - Cron jobs, loops, and reminders."""

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from croniter import croniter
from rich.console import Console

console = Console()


@dataclass
class ScheduledJob:
    """A scheduled job (cron, loop, or reminder)."""
    id: str
    name: str
    job_type: str  # "cron", "loop", "reminder"
    schedule: str  # cron expression, interval in seconds, or ISO datetime
    prompt: str
    enabled: bool = True
    created_at: datetime = field(default_factory=datetime.now)
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    run_count: int = 0
    max_runs: Optional[int] = None  # None = unlimited
    metadata: Dict[str, Any] = field(default_factory=dict)


class Scheduler:
    """Manages scheduled jobs (cron, loops, reminders)."""

    def __init__(self, config_path: Optional[Path] = None):
        self.config_path = config_path or Path.home() / ".mycode" / "scheduler.json"
        self.jobs: Dict[str, ScheduledJob] = {}
        self._running = False
        self._tasks: Dict[str, asyncio.Task] = {}
        self._load_config()

    def _load_config(self):
        """Load scheduler configuration from file."""
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    data = json.load(f)
                    for job_data in data.get('jobs', []):
                        job = ScheduledJob(
                            id=job_data['id'],
                            name=job_data['name'],
                            job_type=job_data['job_type'],
                            schedule=job_data['schedule'],
                            prompt=job_data['prompt'],
                            enabled=job_data.get('enabled', True),
                            created_at=datetime.fromisoformat(job_data['created_at']),
                            last_run=datetime.fromisoformat(job_data['last_run']) if job_data.get('last_run') else None,
                            next_run=datetime.fromisoformat(job_data['next_run']) if job_data.get('next_run') else None,
                            run_count=job_data.get('run_count', 0),
                            max_runs=job_data.get('max_runs'),
                            metadata=job_data.get('metadata', {})
                        )
                        self.jobs[job.id] = job
            except Exception as e:
                console.print(f"[yellow]Warning: Failed to load scheduler config: {e}[/yellow]")

    def save_config(self):
        """Save scheduler configuration to file."""
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'jobs': [
                {
                    'id': job.id,
                    'name': job.name,
                    'job_type': job.job_type,
                    'schedule': job.schedule,
                    'prompt': job.prompt,
                    'enabled': job.enabled,
                    'created_at': job.created_at.isoformat(),
                    'last_run': job.last_run.isoformat() if job.last_run else None,
                    'next_run': job.next_run.isoformat() if job.next_run else None,
                    'run_count': job.run_count,
                    'max_runs': job.max_runs,
                    'metadata': job.metadata
                }
                for job in self.jobs.values()
            ]
        }
        with open(self.config_path, 'w') as f:
            json.dump(data, f, indent=2)

    def add_job(self, name: str, job_type: str, schedule: str, prompt: str,
                max_runs: Optional[int] = None, metadata: Optional[Dict] = None) -> str:
        """Add a new scheduled job."""
        job_id = str(uuid.uuid4())[:8]
        job = ScheduledJob(
            id=job_id,
            name=name,
            job_type=job_type,
            schedule=schedule,
            prompt=prompt,
            max_runs=max_runs,
            metadata=metadata or {}
        )
        self._calculate_next_run(job)
        self.jobs[job.id] = job
        self.save_config()
        return job.id

    def remove_job(self, job_id: str) -> bool:
        """Remove a job by ID."""
        if job_id in self.jobs:
            if job_id in self._tasks:
                self._tasks[job_id].cancel()
                del self._tasks[job_id]
            del self.jobs[job_id]
            self.save_config()
            return True
        return False

    def get_job(self, job_id: str) -> Optional[ScheduledJob]:
        """Get a job by ID."""
        return self.jobs.get(job_id)

    def list_jobs(self) -> List[ScheduledJob]:
        """List all jobs."""
        return list(self.jobs.values())

    def enable_job(self, job_id: str) -> bool:
        """Enable a job."""
        if job_id in self.jobs:
            self.jobs[job_id].enabled = True
            self._calculate_next_run(self.jobs[job_id])
            self.save_config()
            return True
        return False

    def disable_job(self, job_id: str) -> bool:
        """Disable a job."""
        if job_id in self.jobs:
            self.jobs[job_id].enabled = False
            if job_id in self._tasks:
                self._tasks[job_id].cancel()
                del self._tasks[job_id]
            self.save_config()
            return True
        return False

    def _calculate_next_run(self, job: ScheduledJob):
        """Calculate the next run time for a job."""
        now = datetime.now()
        if job.job_type == "cron":
            try:
                cron = croniter(job.schedule, now)
                job.next_run = cron.get_next(datetime)
            except Exception:
                job.next_run = None
        elif job.job_type == "loop":
            try:
                interval = int(job.schedule)
                job.next_run = now + timedelta(seconds=interval)
            except ValueError:
                job.next_run = None
        elif job.job_type == "reminder":
            try:
                job.next_run = datetime.fromisoformat(job.schedule)
            except ValueError:
                job.next_run = None

    async def start(self):
        """Start the scheduler."""
        self._running = True
        # Start tasks for all enabled jobs
        for job in self.jobs.values():
            if job.enabled:
                self._start_job_task(job)

    async def stop(self):
        """Stop the scheduler."""
        self._running = False
        for task in self._tasks.values():
            task.cancel()
        self._tasks.clear()

    def _start_job_task(self, job: ScheduledJob):
        """Start a background task for a job."""
        if job.id in self._tasks:
            self._tasks[job.id].cancel()
        self._tasks[job.id] = asyncio.create_task(self._run_job_loop(job))

    async def _run_job_loop(self, job: ScheduledJob):
        """Run the job loop."""
        while self._running and job.enabled:
            if job.max_runs and job.run_count >= job.max_runs:
                self.disable_job(job.id)
                break

            if job.next_run and datetime.now() >= job.next_run:
                await self._execute_job(job)
                job.run_count += 1
                job.last_run = datetime.now()
                self._calculate_next_run(job)
                self.save_config()
            else:
                # Sleep until next run or check interval
                await asyncio.sleep(1)

    async def _execute_job(self, job: ScheduledJob):
        """Execute a scheduled job."""
        try:
            console.print(f"[dim]⏰ Running scheduled job: {job.name}[/dim]")
            # This would trigger the agent with the prompt
            # For now, just log it
            console.print(f"[dim]Scheduled prompt: {job.prompt[:100]}...[/dim]")
        except Exception as e:
            console.print(f"[red]Scheduled job failed: {e}[/red]")


# Global scheduler instance
_scheduler: Optional['Scheduler'] = None


def get_scheduler(config_path: Optional[Path] = None) -> 'Scheduler':
    """Get or create the global scheduler."""
    global _scheduler
    if _scheduler is None:
        _scheduler = Scheduler(config_path)
    return _scheduler


# CLI command functions for scheduler
def cron_create(name: str, schedule: str, prompt: str, max_runs: Optional[int] = None) -> str:
    """Create a cron job."""
    scheduler = get_scheduler()
    return scheduler.add_job(name, "cron", schedule, prompt, max_runs)


def cron_delete(job_id: str) -> bool:
    """Delete a cron job."""
    scheduler = get_scheduler()
    return scheduler.remove_job(job_id)


def cron_list() -> List[Dict]:
    """List all cron jobs."""
    scheduler = get_scheduler()
    return [
        {
            "id": job.id,
            "name": job.name,
            "schedule": job.schedule,
            "prompt": job.prompt[:50] + "..." if len(job.prompt) > 50 else job.prompt,
            "enabled": job.enabled,
            "next_run": job.next_run.isoformat() if job.next_run else "N/A",
            "run_count": job.run_count
        }
        for job in scheduler.list_jobs()
    ]


def loop_create(name: str, interval_seconds: int, prompt: str, max_runs: Optional[int] = None) -> str:
    """Create a loop job (run every N seconds)."""
    scheduler = get_scheduler()
    return scheduler.add_job(name, "loop", str(interval_seconds), prompt, max_runs)


def reminder_create(name: str, when: str, prompt: str) -> str:
    """Create a one-time reminder."""
    scheduler = get_scheduler()
    return scheduler.add_job(name, "reminder", when, prompt, max_runs=1)