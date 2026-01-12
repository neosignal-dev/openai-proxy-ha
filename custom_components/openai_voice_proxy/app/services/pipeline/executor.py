"""Executor - executes action plans safely"""

from typing import Dict, Any, List
from app.core.logging import get_logger
from app.core.database import ActionLog, async_session_maker
from app.integrations.homeassistant import ha_client
from app.services.memory import memory_service

logger = get_logger(__name__)


class ExecutionResult:
    """Result of action execution"""
    
    def __init__(self):
        self.success = True
        self.executed_actions: List[Dict[str, Any]] = []
        self.failed_actions: List[Dict[str, Any]] = []
        self.errors: List[str] = []

    def add_success(self, action: Dict[str, Any], result: Any = None):
        """Add successful action"""
        self.executed_actions.append({
            "action": action,
            "success": True,
            "result": result,
        })

    def add_failure(self, action: Dict[str, Any], error: str):
        """Add failed action"""
        self.failed_actions.append({
            "action": action,
            "success": False,
            "error": error,
        })
        self.errors.append(error)
        self.success = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return {
            "success": self.success,
            "executed": len(self.executed_actions),
            "failed": len(self.failed_actions),
            "actions": self.executed_actions + self.failed_actions,
            "errors": self.errors,
        }


class Executor:
    """
    Executes action plans safely.
    
    Responsibilities:
    - Execute HA service calls
    - Save user rules to memory
    - Validate actions before execution
    - Handle confirmations
    - Log all actions to audit log
    - Rollback on critical failures (if possible)
    """

    def __init__(self):
        pass

    async def execute(
        self,
        user_id: str,
        plan: Dict[str, Any],
        confirmed: bool = False,
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """
        Execute action plan
        
        Args:
            user_id: User identifier
            plan: Action plan from planner
            confirmed: Whether user confirmed execution
            dry_run: Simulate execution without actually doing it
            
        Returns:
            Execution result dictionary
        """
        plan_type = plan.get("type")
        intent = plan.get("intent", "unknown")

        logger.info(
            "Executing plan",
            user_id=user_id,
            plan_type=plan_type,
            intent=intent,
            dry_run=dry_run,
        )

        # Check confirmation requirement
        needs_confirmation = plan.get("needs_confirmation", False)
        if needs_confirmation and not confirmed:
            return {
                "success": False,
                "needs_confirmation": True,
                "message": "Это действие требует подтверждения",
                "plan": plan,
            }

        # Route to appropriate executor
        if plan_type == "action_plan":
            result = await self._execute_ha_actions(user_id, plan, dry_run)
        
        elif plan_type == "set_rule":
            result = await self._execute_set_rule(user_id, plan)
        
        else:
            # No execution needed (text responses, searches, etc.)
            result = {
                "success": True,
                "message": "No execution required",
            }

        # Log to audit
        await self._log_action(user_id, intent, plan, result, confirmed)

        return result

    async def _execute_ha_actions(
        self,
        user_id: str,
        plan: Dict[str, Any],
        dry_run: bool = False,
    ) -> Dict[str, Any]:
        """Execute Home Assistant actions"""
        
        actions = plan.get("actions", [])
        if not actions:
            return {
                "success": True,
                "message": "No actions to execute",
            }

        result = ExecutionResult()

        for action in actions:
            try:
                domain = action.get("domain")
                service = action.get("service")
                target = action.get("target", {})
                service_data = action.get("service_data", {})

                if not domain or not service:
                    result.add_failure(action, "Missing domain or service")
                    continue

                logger.info(
                    "Executing HA action",
                    domain=domain,
                    service=service,
                    dry_run=dry_run,
                )

                if dry_run:
                    # Simulate execution
                    result.add_success(action, {"dry_run": True})
                else:
                    # Execute via HA client
                    ha_result = await ha_client.call_service(
                        domain=domain,
                        service=service,
                        service_data=service_data,
                        target=target,
                    )
                    result.add_success(action, ha_result)

            except Exception as e:
                logger.error("Action execution failed", action=action, error=str(e))
                result.add_failure(action, str(e))

        return {
            "success": result.success,
            "executed": len(result.executed_actions),
            "failed": len(result.failed_actions),
            "results": result.executed_actions,
            "errors": result.errors,
            "message": self._format_execution_message(result),
        }

    async def _execute_set_rule(
        self,
        user_id: str,
        plan: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Execute set user rule"""
        
        try:
            rule_text = plan.get("rule_text", "")
            rule_type = plan.get("rule_type", "preference")

            if not rule_text:
                return {
                    "success": False,
                    "message": "Rule text is empty",
                }

            # Save to memory
            rule_id = await memory_service.add_user_rule(
                user_id=user_id,
                rule_text=rule_text,
                rule_type=rule_type,
            )

            logger.info(
                "User rule saved",
                user_id=user_id,
                rule_id=rule_id,
                rule_type=rule_type,
            )

            return {
                "success": True,
                "rule_id": rule_id,
                "message": f"Правило сохранено: {rule_text}",
            }

        except Exception as e:
            logger.error("Failed to save rule", error=str(e))
            return {
                "success": False,
                "error": str(e),
                "message": "Не удалось сохранить правило",
            }

    async def _log_action(
        self,
        user_id: str,
        intent: str,
        plan: Dict[str, Any],
        result: Dict[str, Any],
        confirmed: bool,
    ) -> None:
        """Log action to audit database"""
        
        try:
            async with async_session_maker() as session:
                log_entry = ActionLog(
                    user_id=user_id,
                    intent=intent,
                    actions=plan.get("actions", []),
                    confirmed=confirmed,
                    executed=True,
                    success=result.get("success", False),
                    error="; ".join(result.get("errors", [])) if result.get("errors") else None,
                )
                session.add(log_entry)
                await session.commit()

            logger.debug("Action logged to audit", user_id=user_id, intent=intent)

        except Exception as e:
            logger.error("Failed to log action", error=str(e))

    def _format_execution_message(self, result: ExecutionResult) -> str:
        """Format human-readable execution message"""
        
        if result.success:
            return f"Выполнено действий: {len(result.executed_actions)}"
        else:
            return (
                f"Выполнено: {len(result.executed_actions)}, "
                f"Ошибок: {len(result.failed_actions)}"
            )


# Global instance
executor = Executor()
