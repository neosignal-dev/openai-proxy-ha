"""Pipeline orchestrator - coordinates all pipeline components"""

from typing import Dict, Any, Optional
import time
from app.services.pipeline.intent_analyzer import intent_analyzer
from app.services.pipeline.context_resolver import context_resolver
from app.services.pipeline.planner import planner
from app.services.pipeline.executor import executor
from app.services.pipeline.response_composer import response_composer
from app.services.memory import memory_service
from app.core.logging import get_logger

logger = get_logger(__name__)


class PipelineOrchestrator:
    """
    Orchestrates the complete command processing pipeline.
    
    Pipeline flow:
    1. IntentAnalyzer: Determine what user wants
    2. ContextResolver: Gather required context
    3. Planner: Generate action plan
    4. Executor: Execute actions safely
    5. ResponseComposer: Format response for output
    
    Each step is independent and testable.
    """

    def __init__(self):
        self.intent_analyzer = intent_analyzer
        self.context_resolver = context_resolver
        self.planner = planner
        self.executor = executor
        self.response_composer = response_composer

    async def initialize(self) -> None:
        """Initialize all pipeline components"""
        await self.planner.initialize()
        await self.response_composer.initialize()
        logger.info("Pipeline orchestrator initialized")

    async def shutdown(self) -> None:
        """Shutdown all pipeline components"""
        await self.planner.shutdown()
        await self.response_composer.shutdown()
        logger.info("Pipeline orchestrator shutdown")

    async def process(
        self,
        user_id: str,
        command: str,
        channel: str = "voice",
        confirmed: bool = False,
        dry_run: bool = False,
        include_audio: bool = True,
    ) -> Dict[str, Any]:
        """
        Process user command through complete pipeline
        
        Args:
            user_id: User identifier
            command: User command
            channel: Output channel (voice, text, telegram)
            confirmed: Whether action is confirmed
            dry_run: Simulate execution
            include_audio: Include TTS audio in response
            
        Returns:
            Complete response dictionary
        """
        start_time = time.time()

        logger.info(
            "Pipeline processing started",
            user_id=user_id,
            command=command[:50],
            channel=channel,
        )

        try:
            # Step 1: Analyze intent
            intent = await self.intent_analyzer.analyze(user_id, command)
            
            logger.info(
                "Intent analyzed",
                user_id=user_id,
                intent_type=intent["type"],
                confidence=intent.get("confidence", 0),
            )

            # Step 2: Resolve context
            context = await self.context_resolver.resolve(
                user_id=user_id,
                command=command,
                intent=intent,
                include_ha=self.intent_analyzer.should_use_ha(intent),
                include_memory=self.intent_analyzer.should_use_memory(intent),
            )

            # Step 3: Plan actions
            plan = await self.planner.plan(
                user_id=user_id,
                command=command,
                intent=intent,
                context=context,
            )

            logger.info(
                "Plan generated",
                user_id=user_id,
                plan_type=plan.get("type"),
            )

            # Step 4: Execute plan
            execution_result = await self.executor.execute(
                user_id=user_id,
                plan=plan,
                confirmed=confirmed,
                dry_run=dry_run,
            )

            logger.info(
                "Plan executed",
                user_id=user_id,
                success=execution_result.get("success", True),
            )

            # Step 5: Compose response
            response = await self.response_composer.compose(
                user_id=user_id,
                plan=plan,
                execution_result=execution_result,
                channel=channel,
                include_audio=include_audio,
            )

            # Save to memory
            await self._save_to_memory(user_id, command, response)

            # Add pipeline metrics
            response["pipeline"] = {
                "duration_ms": int((time.time() - start_time) * 1000),
                "intent": intent["type"],
                "confidence": intent.get("confidence", 0),
                "steps_completed": 5,
            }

            logger.info(
                "Pipeline processing completed",
                user_id=user_id,
                duration_ms=response["pipeline"]["duration_ms"],
            )

            return response

        except Exception as e:
            logger.error(
                "Pipeline processing failed",
                user_id=user_id,
                error=str(e),
            )
            
            # Return error response
            return {
                "type": "error_response",
                "intent": "unknown",
                "text": f"Произошла ошибка: {str(e)}",
                "error": str(e),
                "channel": channel,
                "pipeline": {
                    "duration_ms": int((time.time() - start_time) * 1000),
                    "error": str(e),
                },
            }

    async def process_confirmation(
        self,
        user_id: str,
        plan: Dict[str, Any],
        confirmed: bool,
        channel: str = "voice",
    ) -> Dict[str, Any]:
        """
        Process user confirmation for a plan
        
        Args:
            user_id: User identifier
            plan: Original plan requiring confirmation
            confirmed: User confirmation (yes/no)
            channel: Output channel
            
        Returns:
            Response after confirmation
        """
        logger.info(
            "Processing confirmation",
            user_id=user_id,
            confirmed=confirmed,
        )

        if not confirmed:
            # User declined
            return {
                "type": "text_response",
                "intent": plan.get("intent", "unknown"),
                "text": "Действие отменено",
                "channel": channel,
            }

        # Execute the plan
        execution_result = await self.executor.execute(
            user_id=user_id,
            plan=plan,
            confirmed=True,
        )

        # Compose response
        response = await self.response_composer.compose(
            user_id=user_id,
            plan=plan,
            execution_result=execution_result,
            channel=channel,
        )

        return response

    async def _save_to_memory(
        self,
        user_id: str,
        command: str,
        response: Dict[str, Any],
    ) -> None:
        """Save interaction to memory"""
        
        try:
            # Save user message
            await memory_service.add_to_short_term(
                user_id=user_id,
                role="user",
                content=command,
            )

            # Save assistant response
            response_text = response.get("text", "")
            if response_text:
                await memory_service.add_to_short_term(
                    user_id=user_id,
                    role="assistant",
                    content=response_text,
                    metadata={
                        "intent": response.get("intent"),
                        "channel": response.get("channel"),
                    },
                )

            logger.debug("Saved to memory", user_id=user_id)

        except Exception as e:
            logger.error("Failed to save to memory", error=str(e))

    async def health_check(self) -> Dict[str, Any]:
        """Check pipeline health"""
        
        # Check each component
        planner_health = await self.planner.text_agent.health_check()
        tts_health = await self.response_composer.tts.health_check()

        all_healthy = (
            planner_health.get("healthy", False) and
            tts_health.get("healthy", False)
        )

        return {
            "pipeline": "healthy" if all_healthy else "degraded",
            "components": {
                "intent_analyzer": "healthy",  # No external dependencies
                "context_resolver": "healthy",
                "planner": planner_health,
                "executor": "healthy",
                "response_composer": tts_health,
            },
        }


# Global instance
pipeline = PipelineOrchestrator()
