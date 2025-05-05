"""
Prompt Engineering System

This module provides a system for managing and generating prompts
for different agents and use cases, ensuring consistency and quality.
"""

from typing import Dict, List, Optional, Any, Union
from enum import Enum
import json

from app.agents.protocol import AgentCapability
from app.logging_config import get_logger

logger = get_logger(__name__)

class PromptType(str, Enum):
    """Types of prompts that can be used"""
    SYSTEM = "system"                  # System prompt to set agent behavior
    USER = "user"                      # User message template
    ASSISTANT = "assistant"            # Assistant response template
    MEMORY_FORMAT = "memory_format"    # Format for storing memories
    ANALYSIS = "analysis"              # Analysis of user input
    SUMMARY = "summary"                # Summarization template
    ETHICAL_CHECK = "ethical_check"    # Ethical validation check

class PromptTemplate:
    """A template for a prompt with variable substitution"""
    
    def __init__(
        self,
        template: str,
        prompt_type: PromptType,
        description: Optional[str] = None,
        variables: Optional[List[str]] = None,
        examples: Optional[List[Dict[str, str]]] = None
    ):
        """
        Initialize a prompt template
        
        Args:
            template: The prompt template text with {variable} placeholders
            prompt_type: Type of prompt
            description: Description of the prompt's purpose
            variables: List of variable names used in the template
            examples: List of example variable values and their results
        """
        self.template = template
        self.prompt_type = prompt_type
        self.description = description or ""
        
        # Extract variables from template if not provided
        if variables is None:
            import re
            self.variables = re.findall(r'{([^}]+)}', template)
        else:
            self.variables = variables
            
        self.examples = examples or []
    
    def format(self, **kwargs) -> str:
        """
        Format the template with the provided variables
        
        Args:
            **kwargs: Variable values to substitute
            
        Returns:
            str: The formatted prompt
            
        Raises:
            ValueError: If a required variable is missing
        """
        # Check for missing variables
        missing = [var for var in self.variables if var not in kwargs]
        if missing:
            raise ValueError(f"Missing variables: {', '.join(missing)}")
        
        # Format the template
        return self.template.format(**kwargs)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the prompt template to a dictionary
        
        Returns:
            Dict[str, Any]: Dictionary representation of the template
        """
        return {
            "template": self.template,
            "prompt_type": self.prompt_type,
            "description": self.description,
            "variables": self.variables,
            "examples": self.examples
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PromptTemplate':
        """
        Create a prompt template from a dictionary
        
        Args:
            data: Dictionary representation of the template
            
        Returns:
            PromptTemplate: The created template
        """
        return cls(
            template=data["template"],
            prompt_type=data["prompt_type"],
            description=data.get("description", ""),
            variables=data.get("variables"),
            examples=data.get("examples", [])
        )

class PromptLibrary:
    """
    A library of prompt templates for different agents and use cases
    """
    
    # Agent system prompts
    AGENT_SYSTEM_PROMPTS = {
        "EchoMind": """You are EchoMind, a supportive and thoughtful AI companion. Your goal is to help users reflect on their experiences, understand their emotions, and grow from their challenges. You are conversational, warm, and focused on the user's well-being.

Guidelines:
- Listen actively and validate the user's feelings
- Ask thoughtful questions to deepen understanding
- Offer gentle guidance, not directives
- Focus on emotional awareness and personal growth
- When appropriate, help users reframe negative thoughts
- Maintain a supportive and non-judgmental tone
- Recognize when to suggest switching to a specialized agent

This conversation is private and focused on helping the user gain insight and clarity.""",

        "Therapist": """You are a supportive therapeutic assistant trained in various therapeutic approaches including CBT, ACT, and humanistic therapy. Your goal is to provide a safe space for the user to explore their thoughts, feelings, and behaviors.

Guidelines:
- Practice empathetic listening and validation
- Ask reflective and clarifying questions
- Help identify thought patterns and cognitive distortions
- Suggest evidence-based techniques when appropriate
- Focus on emotional awareness and psychological flexibility
- Never diagnose or replace professional mental health care
- Maintain professional boundaries while being warm and supportive

Remember that your role is to support therapeutic exploration, not to provide medical advice or formal therapy. Encourage professional help for serious concerns.""",

        "Coach": """You are a motivational coach focused on helping users achieve their personal and professional goals. Your approach is energetic, structured, and action-oriented.

Guidelines:
- Help users clarify their goals and values
- Break large goals into manageable steps
- Encourage accountability and consistent action
- Provide frameworks for overcoming obstacles
- Focus on strengths and progress rather than shortcomings
- Balance challenging users with maintaining motivation
- Use positive, energetic, and clear language

Your conversations should leave users feeling motivated, clear about their next steps, and empowered to take action.""",

        "Bridge": """You are Bridge, a communication facilitator designed to help improve understanding between people. Your primary role is to help translate messages, highlight misunderstandings, and suggest constructive ways to express thoughts and feelings.

Guidelines:
- Remain completely neutral between parties
- Clarify potential misunderstandings before they escalate
- Suggest alternative phrasings for emotionally charged messages
- Identify communication patterns that may cause friction
- Encourage the use of "I" statements and specific examples
- Suggest pauses when conversations become heated
- Focus on building mutual understanding, not determining who is right

Your goal is not to solve the underlying issues being discussed, but to help ensure that communication about those issues is clear, respectful, and productive."""
    }
    
    # Memory formatting prompts
    MEMORY_FORMAT_PROMPTS = {
        "emotional_summary": PromptTemplate(
            template="""Analyze the following conversation and create a brief emotional summary. Focus on the user's emotional state, key concerns, and any insights gained.

Conversation:
{conversation}

Your summary should include:
1. Primary emotional tones detected
2. Key topics or concerns
3. Any notable patterns or insights
4. Progress or shifts in perspective

Keep your response concise and focused on emotional content rather than factual details.""",
            prompt_type=PromptType.MEMORY_FORMAT,
            description="Creates an emotional summary of a conversation for memory storage",
            variables=["conversation"]
        ),
        
        "session_recap": PromptTemplate(
            template="""Based on this session history, provide a concise recap that could be shared with another agent.

Session:
{session_history}

Focus on:
- Key topics discussed
- Emotional themes
- Important insights or progress
- Current challenges
- Goals or next steps mentioned

Format your response as a brief, professional summary that would help another agent understand the current context.""",
            prompt_type=PromptType.SUMMARY,
            description="Creates a recap of a session to share with another agent during handoff",
            variables=["session_history"]
        )
    }
    
    # Analysis prompts
    ANALYSIS_PROMPTS = {
        "emotional_analysis": PromptTemplate(
            template="""Analyze the following user message for emotional content. Identify the primary and secondary emotions, their intensity, and confidence in your assessment.

User message:
{user_message}

Provide your analysis in JSON format:
```json
{{
  "primary_emotion": "",
  "primary_intensity": 0.0,
  "secondary_emotions": [],
  "confidence": 0.0,
  "reasoning": ""
}}
```

Where:
- primary_emotion is the main detected emotion
- primary_intensity is between 0.0 and 1.0
- secondary_emotions is an array of objects with emotion name and intensity
- confidence is your confidence in this assessment between 0.0 and 1.0
- reasoning explains why you made this assessment""",
            prompt_type=PromptType.ANALYSIS,
            description="Analyzes a user message for emotional content",
            variables=["user_message"]
        ),
        
        "topic_detection": PromptTemplate(
            template="""Analyze the following conversation to identify the main topics being discussed. Rank them by importance and relevance.

Conversation:
{conversation}

Provide your analysis in JSON format:
```json
{{
  "primary_topic": "",
  "all_topics": [],
  "therapeutic_areas": [],
  "potential_referral_needed": false,
  "reasoning": ""
}}
```

Where:
- primary_topic is the main topic of discussion
- all_topics is an array of all identified topics
- therapeutic_areas indicates areas of potential therapeutic focus
- potential_referral_needed is true if this might warrant a specialized agent
- reasoning explains your analysis""",
            prompt_type=PromptType.ANALYSIS,
            description="Detects topics in a conversation",
            variables=["conversation"]
        ),
        
        "agent_selection": PromptTemplate(
            template="""Based on the following information, determine which agent would be best suited to handle this conversation next.

User message: {user_message}
Current agent: {current_agent}
Emotional analysis: {emotional_analysis}
Topics detected: {topics}
Conversation history: {conversation_history}

Available agents:
- EchoMind: General support and reflection
- Therapist: Emotional support and therapeutic techniques
- Coach: Goal-setting and motivation
- Bridge: Communication facilitation
- Parent: Parenting advice and support

Provide your recommendation in JSON format:
```json
{{
  "recommended_agent": "",
  "confidence": 0.0,
  "reasoning": "",
  "handoff_message": ""
}}
```

Where:
- recommended_agent is the name of the recommended agent
- confidence is your confidence in this recommendation between 0.0 and 1.0
- reasoning explains why you made this recommendation
- handoff_message is a suggested message to transition to the new agent""",
            prompt_type=PromptType.ANALYSIS,
            description="Determines which agent is best suited for a conversation",
            variables=["user_message", "current_agent", "emotional_analysis", "topics", "conversation_history"]
        )
    }
    
    # User and assistant message templates for different agents
    AGENT_MESSAGE_TEMPLATES = {
        "Therapist": {
            "reflection": PromptTemplate(
                template="""I notice that you mentioned {key_point}. Could you tell me more about how that has been affecting you?""",
                prompt_type=PromptType.ASSISTANT,
                description="Therapist reflection prompt",
                variables=["key_point"]
            ),
            "validation": PromptTemplate(
                template="""It sounds like you're feeling {emotion} about {situation}, and that's completely valid. Many people would feel that way in your position.""",
                prompt_type=PromptType.ASSISTANT,
                description="Therapist validation response",
                variables=["emotion", "situation"]
            )
        },
        "Coach": {
            "goal_setting": PromptTemplate(
                template="""What would success look like for you with {goal}? Let's break this down into smaller, actionable steps.""",
                prompt_type=PromptType.ASSISTANT,
                description="Coach goal-setting prompt",
                variables=["goal"]
            ),
            "accountability": PromptTemplate(
                template="""Last time, we discussed your plan to {previous_plan}. How did that go? What did you learn from the experience?""",
                prompt_type=PromptType.ASSISTANT,
                description="Coach accountability check-in",
                variables=["previous_plan"]
            )
        },
        "Bridge": {
            "clarification": PromptTemplate(
                template="""I want to make sure I understand correctly. Are you saying that {interpretation}? Or did you mean something different?""",
                prompt_type=PromptType.ASSISTANT,
                description="Bridge clarification prompt",
                variables=["interpretation"]
            ),
            "reframing": PromptTemplate(
                template="""I notice you said \"{original_statement}\". Another way to express this might be: \"{reframed_statement}\". Does that capture what you're trying to communicate?""",
                prompt_type=PromptType.ASSISTANT,
                description="Bridge reframing suggestion",
                variables=["original_statement", "reframed_statement"]
            )
        }
    }
    
    # Ethical check prompts
    ETHICAL_CHECKS = {
        "content_safety": PromptTemplate(
            template="""Analyze the following response for any content that might be harmful, unethical, or inappropriate.

Proposed response:
{response}

Context:
{context}

Check for:
1. Medical or psychological advice that should come from professionals
2. Content that could be harmful to vulnerable individuals
3. Political, religious, or ideological bias
4. Privacy violations or personally identifiable information
5. Inappropriate therapeutic techniques or interventions

Provide your analysis in JSON format:
```json
{{
  "is_safe": true|false,
  "concerns": [],
  "reasoning": "",
  "suggested_revision": ""
}}
```

If the content is safe, set is_safe to true and leave the other fields empty.""",
            prompt_type=PromptType.ETHICAL_CHECK,
            description="Checks a response for potentially harmful content",
            variables=["response", "context"]
        )
    }
    
    @classmethod
    def get_system_prompt(cls, agent_name: str) -> str:
        """
        Get the system prompt for a specific agent
        
        Args:
            agent_name: Name of the agent
            
        Returns:
            str: System prompt for the agent
        """
        return cls.AGENT_SYSTEM_PROMPTS.get(agent_name, cls.AGENT_SYSTEM_PROMPTS["EchoMind"])
    
    @classmethod
    def get_prompt_template(
        cls,
        template_name: str,
        category: Optional[str] = None,
        agent_name: Optional[str] = None
    ) -> Optional[PromptTemplate]:
        """
        Get a prompt template by name
        
        Args:
            template_name: Name of the template
            category: Category of templates to search (e.g., MEMORY_FORMAT_PROMPTS)
            agent_name: Name of the agent (for agent-specific templates)
            
        Returns:
            Optional[PromptTemplate]: The prompt template, or None if not found
        """
        # Look in specific category if provided
        if category:
            category_dict = getattr(cls, category, {})
            if template_name in category_dict:
                return category_dict[template_name]
        
        # Look in agent-specific templates if agent provided
        if agent_name:
            agent_templates = cls.AGENT_MESSAGE_TEMPLATES.get(agent_name, {})
            if template_name in agent_templates:
                return agent_templates[template_name]
        
        # Look in all categories
        for category_name in ["MEMORY_FORMAT_PROMPTS", "ANALYSIS_PROMPTS", "ETHICAL_CHECKS"]:
            category_dict = getattr(cls, category_name, {})
            if template_name in category_dict:
                return category_dict[template_name]
        
        # Look in all agent templates
        for agent_templates in cls.AGENT_MESSAGE_TEMPLATES.values():
            if template_name in agent_templates:
                return agent_templates[template_name]
        
        return None
    
    @classmethod
    def format_prompt(
        cls,
        template_name: str,
        variables: Dict[str, Any],
        category: Optional[str] = None,
        agent_name: Optional[str] = None
    ) -> Optional[str]:
        """
        Format a prompt template with the provided variables
        
        Args:
            template_name: Name of the template
            variables: Dictionary of variable values
            category: Category of templates to search
            agent_name: Name of the agent
            
        Returns:
            Optional[str]: The formatted prompt, or None if template not found
        """
        template = cls.get_prompt_template(template_name, category, agent_name)
        if template:
            try:
                return template.format(**variables)
            except ValueError as e:
                logger.error(
                    f"Error formatting prompt template '{template_name}': {str(e)}",
                    extra={
                        "template_name": template_name,
                        "variables": variables,
                        "error": str(e)
                    }
                )
                return None
        else:
            logger.warning(
                f"Prompt template '{template_name}' not found",
                extra={
                    "template_name": template_name,
                    "category": category,
                    "agent_name": agent_name
                }
            )
            return None

class PromptManager:
    """
    Manager for dynamically building and optimizing prompts
    """
    
    def __init__(self, agent_name: str):
        """
        Initialize a prompt manager for a specific agent
        
        Args:
            agent_name: Name of the agent this manager is for
        """
        self.agent_name = agent_name
        self.logger = get_logger(__name__)
    
    def get_system_prompt(self) -> str:
        """
        Get the system prompt for this agent
        
        Returns:
            str: System prompt
        """
        return PromptLibrary.get_system_prompt(self.agent_name)
    
    def format_prompt(self, template_name: str, variables: Dict[str, Any]) -> Optional[str]:
        """
        Format a prompt template with the provided variables
        
        Args:
            template_name: Name of the template
            variables: Dictionary of variable values
            
        Returns:
            Optional[str]: The formatted prompt, or None if template not found
        """
        return PromptLibrary.format_prompt(template_name, variables, agent_name=self.agent_name)
    
    def build_message_sequence(
        self,
        user_message: str,
        memory_context: Dict[str, Any],
        conversation_history: List[Dict[str, str]],
        include_system_prompt: bool = True
    ) -> List[Dict[str, str]]:
        """
        Build a sequence of messages for a chat completion
        
        Args:
            user_message: The current user message
            memory_context: Context from the user's memory
            conversation_history: Previous messages in the conversation
            include_system_prompt: Whether to include the system prompt
            
        Returns:
            List[Dict[str, str]]: Sequence of messages for a chat completion
        """
        messages = []
        
        # Add system prompt if requested
        if include_system_prompt:
            system_prompt = self.get_system_prompt()
            messages.append({
                "role": "system",
                "content": system_prompt
            })
        
        # Add memory context as a system message
        if memory_context:
            context_str = "User context:\n"
            for key, value in memory_context.items():
                if isinstance(value, dict):
                    context_str += f"\n{key}:\n"
                    for sub_key, sub_value in value.items():
                        context_str += f"- {sub_key}: {sub_value}\n"
                elif isinstance(value, list):
                    context_str += f"\n{key}:\n"
                    for item in value:
                        context_str += f"- {item}\n"
                else:
                    context_str += f"\n{key}: {value}\n"
            
            messages.append({
                "role": "system",
                "content": context_str
            })
        
        # Add conversation history
        messages.extend(conversation_history)
        
        # Add current user message
        messages.append({
            "role": "user",
            "content": user_message
        })
        
        return messages
    
    def check_response_safety(self, response: str, context: str) -> Dict[str, Any]:
        """
        Check if a response is safe and appropriate
        
        Args:
            response: The proposed response
            context: The context of the conversation
            
        Returns:
            Dict[str, Any]: Safety check result
        """
        # Format the safety check prompt
        safety_prompt = PromptLibrary.format_prompt(
            "content_safety",
            {"response": response, "context": context},
            category="ETHICAL_CHECKS"
        )
        
        # In a real implementation, this would call the LLM to evaluate safety
        # For now, we'll return a placeholder result
        return {
            "is_safe": True,
            "concerns": [],
            "reasoning": "Response appears safe and appropriate.",
            "suggested_revision": ""
        }