"""
Agent Switching Logic

This module handles the logic for deciding when to switch between agents
and how to transfer context between them.
"""

from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from app.agents.protocol import (
    AgentMessage, 
    MessageType, 
    MessagePriority, 
    EmotionalState,
    AgentHandoff,
    AgentCapability,
    create_handoff_message
)
from app.logging_config import get_logger

logger = get_logger(__name__)

class SwitchingRules:
    """Rules that determine when agent switching should occur"""
    
    # Emotional thresholds that might trigger a switch
    EMOTIONAL_THRESHOLDS = {
        "distress": 0.7,       # High distress may require therapist
        "anxiety": 0.7,        # High anxiety may require therapist
        "anger": 0.8,          # High anger may require de-escalation specialist
        "confusion": 0.6,      # Confusion may require clearer explanations
        "joy": 0.9,            # Extreme joy might be celebrated by a different agent
        "grief": 0.6           # Grief may require specialized support
    }
    
    # Topic areas and the agents best suited to handle them
    TOPIC_SPECIALIZATION = {
        "parenting": ["Parent", "Family"],
        "relationships": ["Elora", "Bridge"],
        "emotional_support": ["Mirror", "Therapist"],
        "coaching": ["Coach", "Mentor"],
        "goal_setting": ["Coach", "Achiever"],
        "trauma": ["Therapist", "Healer"],
        "conflict": ["Mediator", "Bridge"],
        "communication": ["Bridge", "Communicator"],
        "technical": ["Technical", "Expert"]
    }
    
    # Agent capability definitions
    AGENT_CAPABILITIES = {
        "EchoMind": [AgentCapability.EMOTIONAL_SUPPORT, AgentCapability.COGNITIVE_REFRAMING],
        "Therapist": [AgentCapability.THERAPY, AgentCapability.EMOTIONAL_SUPPORT, AgentCapability.COGNITIVE_REFRAMING],
        "Coach": [AgentCapability.COACHING, AgentCapability.GOAL_SETTING],
        "Parent": [AgentCapability.PARENTING_ADVICE],
        "Bridge": [AgentCapability.BRIDGING, AgentCapability.CONFLICT_RESOLUTION],
        "Friend": [AgentCapability.FRIENDSHIP, AgentCapability.EMOTIONAL_SUPPORT]
    }
    
    @classmethod
    def get_best_agent_for_emotion(cls, emotion: str, intensity: float) -> Optional[str]:
        """Determine the best agent to handle a given emotional state"""
        if emotion not in cls.EMOTIONAL_THRESHOLDS:
            return None
            
        # If emotion is below threshold, no switch is needed
        if intensity < cls.EMOTIONAL_THRESHOLDS[emotion]:
            return None
            
        # Map emotions to appropriate agents
        emotion_map = {
            "distress": "Therapist",
            "anxiety": "Therapist",
            "anger": "Mediator",
            "confusion": "Teacher",
            "joy": "Friend",
            "grief": "Therapist"
        }
        
        return emotion_map.get(emotion)
    
    @classmethod
    def get_best_agent_for_topic(cls, topic: str) -> Optional[str]:
        """Determine the best agent to handle a given topic"""
        for area, agents in cls.TOPIC_SPECIALIZATION.items():
            if topic.lower() in area.lower() or area.lower() in topic.lower():
                return agents[0]  # Return the primary agent for this topic
        return None
    
    @classmethod
    def get_agents_with_capability(cls, capability: AgentCapability) -> List[str]:
        """Get a list of agents that have a specific capability"""
        agents = []
        for agent, capabilities in cls.AGENT_CAPABILITIES.items():
            if capability in capabilities:
                agents.append(agent)
        return agents

class SwitchingEngine:
    """Engine that evaluates conversation state and determines when to switch agents"""
    
    def __init__(self, default_agent: str = "EchoMind"):
        self.default_agent = default_agent
        self.logger = get_logger(__name__)
    
    def evaluate_emotional_state(self, emotional_state: EmotionalState) -> Optional[str]:
        """
        Evaluate the emotional state to determine if an agent switch is needed
        
        Args:
            emotional_state: Current emotional state assessment
            
        Returns:
            Optional[str]: Agent to switch to, or None if no switch is needed
        """
        # Check primary emotion
        recommended_agent = SwitchingRules.get_best_agent_for_emotion(
            emotional_state.primary, 
            emotional_state.intensity
        )
        
        if recommended_agent:
            self.logger.info(
                f"Emotional state indicates a switch to {recommended_agent} may be appropriate",
                extra={
                    "emotion": emotional_state.primary,
                    "intensity": emotional_state.intensity,
                    "confidence": emotional_state.confidence,
                    "recommended_agent": recommended_agent
                }
            )
            return recommended_agent
            
        # Check secondary emotions if they exist
        if emotional_state.secondary:
            for emotion_dict in emotional_state.secondary:
                for emotion, intensity in emotion_dict.items():
                    secondary_agent = SwitchingRules.get_best_agent_for_emotion(emotion, intensity)
                    if secondary_agent:
                        self.logger.info(
                            f"Secondary emotional state indicates a switch to {secondary_agent} may be appropriate",
                            extra={
                                "emotion": emotion,
                                "intensity": intensity,
                                "recommended_agent": secondary_agent
                            }
                        )
                        return secondary_agent
        
        return None
    
    def evaluate_topic(self, topics: List[str]) -> Optional[str]:
        """
        Evaluate conversation topics to determine if an agent switch is needed
        
        Args:
            topics: List of detected conversation topics
            
        Returns:
            Optional[str]: Agent to switch to, or None if no switch is needed
        """
        for topic in topics:
            recommended_agent = SwitchingRules.get_best_agent_for_topic(topic)
            if recommended_agent:
                self.logger.info(
                    f"Topic '{topic}' indicates a switch to {recommended_agent} may be appropriate",
                    extra={
                        "topic": topic,
                        "recommended_agent": recommended_agent
                    }
                )
                return recommended_agent
        
        return None
    
    def evaluate_capabilities_needed(self, capabilities_needed: List[AgentCapability]) -> Optional[str]:
        """
        Evaluate capabilities needed to determine if an agent switch is needed
        
        Args:
            capabilities_needed: List of capabilities needed for the current conversation
            
        Returns:
            Optional[str]: Agent to switch to, or None if no switch is needed
        """
        # For each capability, find agents that have it
        agents_with_capabilities = {}
        
        for capability in capabilities_needed:
            agents = SwitchingRules.get_agents_with_capability(capability)
            for agent in agents:
                if agent not in agents_with_capabilities:
                    agents_with_capabilities[agent] = 0
                agents_with_capabilities[agent] += 1
        
        # Find the agent with the most required capabilities
        if agents_with_capabilities:
            best_agent, count = max(agents_with_capabilities.items(), key=lambda x: x[1])
            
            # Only recommend a switch if the agent has at least half of the needed capabilities
            if count >= len(capabilities_needed) / 2:
                self.logger.info(
                    f"Required capabilities indicate a switch to {best_agent} may be appropriate",
                    extra={
                        "capabilities_needed": [c.value for c in capabilities_needed],
                        "recommended_agent": best_agent,
                        "capabilities_match_count": count
                    }
                )
                return best_agent
        
        return None
    
    def evaluate_switch(
        self, 
        current_agent: str,
        emotional_state: Optional[EmotionalState] = None,
        topics: Optional[List[str]] = None,
        capabilities_needed: Optional[List[AgentCapability]] = None,
        conversation_state: Optional[Dict[str, Any]] = None
    ) -> Tuple[bool, Optional[str], Optional[str]]:
        """
        Evaluate whether to switch agents based on conversation state
        
        Args:
            current_agent: Currently active agent
            emotional_state: Current emotional state assessment (optional)
            topics: List of detected conversation topics (optional)
            capabilities_needed: List of capabilities needed (optional)
            conversation_state: Additional conversation state data (optional)
            
        Returns:
            Tuple[bool, Optional[str], Optional[str]]: 
                - Whether to switch
                - Agent to switch to (if switching)
                - Reason for the switch (if switching)
        """
        recommended_agent = None
        reason = None
        
        # Check emotional state
        if emotional_state:
            emotional_agent = self.evaluate_emotional_state(emotional_state)
            if emotional_agent and emotional_agent != current_agent:
                recommended_agent = emotional_agent
                reason = f"Emotional state ({emotional_state.primary} at {emotional_state.intensity:.1f} intensity) requires {emotional_agent}"
        
        # Check topics
        if topics and not recommended_agent:
            topic_agent = self.evaluate_topic(topics)
            if topic_agent and topic_agent != current_agent:
                recommended_agent = topic_agent
                reason = f"Topic specialization in '{', '.join(topics)}' suggests {topic_agent}"
        
        # Check capabilities
        if capabilities_needed and not recommended_agent:
            capability_agent = self.evaluate_capabilities_needed(capabilities_needed)
            if capability_agent and capability_agent != current_agent:
                recommended_agent = capability_agent
                reason = f"Required capabilities {[c.value for c in capabilities_needed]} are best handled by {capability_agent}"
        
        # Determine if we should switch
        should_switch = recommended_agent is not None
        
        if should_switch:
            self.logger.info(
                f"Agent switch recommended: {current_agent} -> {recommended_agent}",
                extra={
                    "current_agent": current_agent,
                    "recommended_agent": recommended_agent,
                    "reason": reason
                }
            )
        
        return should_switch, recommended_agent, reason
    
    def create_switch_message(
        self,
        session_id: str,
        user_id: str,
        current_agent: str,
        target_agent: str,
        reason: str,
        conversation_state: Dict[str, Any],
        emotional_state: Optional[EmotionalState] = None,
        urgency: MessagePriority = MessagePriority.NORMAL
    ) -> AgentMessage:
        """
        Create a handoff message to switch agents
        
        Args:
            session_id: Current session ID
            user_id: Current user ID
            current_agent: Currently active agent
            target_agent: Agent to switch to
            reason: Reason for the switch
            conversation_state: Current conversation state
            emotional_state: Current emotional state (optional)
            urgency: Urgency of the switch (default NORMAL)
            
        Returns:
            AgentMessage: Handoff message for the agent switch
        """
        # Extract relevant context from the conversation state
        context = {
            "recent_topic": conversation_state.get("recent_topic", ""),
            "session_duration": conversation_state.get("session_duration", 0),
            "user_goals": conversation_state.get("user_goals", []),
            "previous_agents": conversation_state.get("previous_agents", []),
            "tone_preferences": conversation_state.get("tone_preferences", {})
        }
        
        # Create the handoff message
        handoff_message = create_handoff_message(
            sender=current_agent,
            target_agent=target_agent,
            reason=reason,
            context=context,
            conversation_state=conversation_state,
            session_id=session_id,
            user_id=user_id,
            emotional_state=emotional_state,
            urgency=urgency
        )
        
        self.logger.info(
            f"Created handoff message for switch from {current_agent} to {target_agent}",
            extra={
                "handoff_id": handoff_message.id,
                "session_id": session_id,
                "user_id": user_id,
                "reason": reason
            }
        )
        
        return handoff_message