"""Per-job runtime context.

Nodes are bound to one of these; only serialisable data lives in the LangGraph
state, so checkpoints stay small and restorable.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.config import Settings
from app.graph.budget import BudgetedLLMProvider, ResearchBudget
from app.providers.base import LLMProvider
from app.providers.factory import ProviderBundle
from app.services.backend_client import BackendClient


@dataclass
class JobContext:
    job_id: str
    product_query: str
    demo_mode: bool
    settings: Settings
    providers: ProviderBundle
    backend: BackendClient
    budget: ResearchBudget
    llm: LLMProvider

    @classmethod
    def create(
        cls,
        *,
        job_id: str,
        product_query: str,
        demo_mode: bool,
        settings: Settings,
        providers: ProviderBundle,
        backend: BackendClient,
        budget: ResearchBudget | None = None,
    ) -> JobContext:
        research_budget = budget or ResearchBudget(settings)
        return cls(
            job_id=job_id,
            product_query=product_query,
            demo_mode=demo_mode,
            settings=settings,
            providers=providers,
            backend=backend,
            budget=research_budget,
            llm=BudgetedLLMProvider(providers.llm, research_budget),
        )
