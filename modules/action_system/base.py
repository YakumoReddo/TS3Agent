from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class ActionResult:
    success: bool
    message: str = ""
    data: Any = None


class Action(ABC):
    name: str = ""
    description: str = ""
    parameters: Dict = {}

    @abstractmethod
    async def execute(self, **kwargs) -> ActionResult:
        pass
